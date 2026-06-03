"""
Sentinel-Zero Analysis Routes
=============================
Identity-aware risk assessment, secure credential storage, onboarding,
and personalized model training.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.api.dependencies import cache_user_brain, get_user_brain, verify_tenant_isolation, rate_limiter
from sentinel.brain.feature_engine import FEATURE_COLUMNS_V2, engineer_features
from sentinel.brain.risk_engine import SentinelBrain, get_progression_level
from sentinel.domain.models import (
    AdminOverview,
    AdminUserRecord,
    CredentialRequest,
    CredentialResponse,
    Decision,
    HistoricalTrade,
    OnboardingDataSubmission,
    OnboardingRequest,
    OnboardingState,
    OnboardingStatus,
    RiskAuditRecord,
    RiskAssessment,
    TradeContext,
    UserBaseline,
    UserInitialParameters,
    UserMaturity,
    WorkspaceSummary,
    WhopWebhookRequest,
    WhopWebhookResponse,
    FeedbackSubmission,
)
from sentinel.infra.db import (
    AsyncSessionLocal,
    create_onboarding_job,
    get_db,
    get_onboarding_job,
    get_user,
    list_api_credentials,
    list_behavioral_logs,
    list_onboarding_jobs,
    list_risk_audits,
    list_users,
    record_behavioral_log,
    record_risk_audit,
    upsert_api_credential,
    update_onboarding_job,
    upsert_user,
    update_risk_audit_explanation,
    BehavioralLog,
)
from sentinel.infra.redis_cache import cache_manager
from sentinel.infra.s3 import model_store
from sentinel.infra.vault_client import vault_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _sanitize_release_name(user_id: str) -> str:
    safe = re.sub(r"[^a-z0-9-]+", "-", user_id.lower()).strip("-")
    return safe[:40] or "user"


def _build_helm_release(user_id: str) -> str:
    return f"sentinel-pod-{_sanitize_release_name(user_id)}"


def _build_helm_command(user_id: str, plan: str, release_name: str) -> str:
    namespace = os.getenv("SENTINEL_USER_NAMESPACE", "sentinel-users")
    chart_path = os.getenv("SENTINEL_POD_HELM_CHART", "infra/helm/sentinel-pod")
    return (
        f"helm upgrade --install {release_name} {chart_path} "
        f"--namespace {namespace} --create-namespace "
        f"--set-string env.SENTINEL_USER_ID={user_id} "
        f"--set-string userLabels.entries.sentinel-user-id={user_id} "
        f"--set-string userLabels.entries.plan={plan}"
    )


def duplicate_mt5_directory(user_id: str) -> str:
    """Duplicate C:\\Sentinel\\Master_MT5 into user-specific folder for isolated Portable Mode."""
    import shutil
    source_dir = "C:\\Sentinel\\Master_MT5"
    target_dir = f"C:\\Sentinel\\Users\\{user_id}"
    
    if not os.path.exists(target_dir):
        logger.info("Dynamically copying Master MT5 template to isolated target: %s", target_dir)
        try:
            os.makedirs(os.path.dirname(target_dir), exist_ok=True)
            if os.path.exists(source_dir):
                shutil.copytree(source_dir, target_dir)
            else:
                os.makedirs(target_dir, exist_ok=True)
                with open(os.path.join(target_dir, "terminal64.exe"), "w") as f:
                    f.write("mock-terminal")
        except Exception as e:
            logger.error("Failed to copy MT5 portable folder for user %s: %s", user_id, e)
    return os.path.join(target_dir, "terminal64.exe")


def _job_to_status(job: object) -> OnboardingStatus:
    job_state = getattr(job, "state")
    return OnboardingStatus(
        job_id=str(getattr(job, "job_id")),
        user_id=str(getattr(job, "user_id")),
        state=OnboardingState(str(job_state)),
        trade_count=int(getattr(job, "trade_count") or 0),
        message=str(getattr(job, "message") or "Job queued"),
        model_s3_key=getattr(job, "model_s3_key"),
        created_at=getattr(job, "created_at") or datetime.utcnow(),
        completed_at=getattr(job, "completed_at"),
    )


def _user_to_profile(user: object) -> UserBaseline:
    initial_raw = getattr(user, "initial_parameters", None) or {}
    return UserBaseline(
        user_id=str(getattr(user, "user_id")),
        broker_server=getattr(user, "broker_server"),
        account_id=getattr(user, "account_id"),
        trade_count=int(getattr(user, "trade_count") or 0),
        model_s3_key=getattr(user, "model_s3_key"),
        trained_at=getattr(user, "trained_at"),
        is_baseline_ready=bool(getattr(user, "is_baseline_ready")),
        maturity_state=UserMaturity(str(getattr(user, "maturity_state", UserMaturity.MATURITY_0.value))),
        enforce_mode=bool(getattr(user, "enforce_mode", False)),
        model_level=int(getattr(user, "model_level", 1) or 1),
        initial_parameters=UserInitialParameters.model_validate(initial_raw),
    )


def _audit_to_record(audit: object, submitted_audit_ids: set[int] | None = None) -> RiskAuditRecord:
    audit_id = getattr(audit, "id", None)
    submitted = (audit_id in submitted_audit_ids) if (submitted_audit_ids is not None and audit_id is not None) else False
    return RiskAuditRecord(
        audit_id=audit_id,
        user_id=str(getattr(audit, "user_id")),
        symbol=str(getattr(audit, "symbol") or "UNKNOWN"),
        decision=Decision(str(getattr(audit, "decision"))),
        risk_score=float(getattr(audit, "risk_score") or 0.0),
        size_multiplier=float(getattr(audit, "size_multiplier") or 0.0),
        mode=str(getattr(audit, "mode") or "normal"),
        is_anomaly=bool(getattr(audit, "is_anomaly")),
        top_reason=getattr(audit, "top_reason"),
        explanation=getattr(audit, "explanation", []) or [],
        latency_ms=float(getattr(audit, "latency_ms") or 0.0),
        cached=bool(getattr(audit, "cached")),
        autopsy_submitted=submitted,
        created_at=getattr(audit, "created_at") or datetime.utcnow(),
    )


def _trades_to_frame(trades: list[HistoricalTrade]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for trade in trades:
        price_gain = ((trade.close_price - trade.open_price) / trade.open_price) * 100
        rows.append(
            {
                "Symbol": trade.symbol,
                "Open Time": trade.open_time,
                "Close Time": trade.close_time,
                "PnL": trade.pnl,
                "Lots": trade.lots,
                "Open Price": trade.open_price,
                "Close Price": trade.close_price,
                "RR Ratio": trade.rr_ratio,
                "Gain": f"{price_gain:.4f}%",
            }
        )
    return pd.DataFrame(rows)


def _behavioral_logs_to_training_frame(logs: list[object]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for log in reversed(logs):
        decision = str(getattr(log, "decision", Decision.ALLOW.value))
        risk_score = float(getattr(log, "risk_score", 0.0) or 0.0)
        rows.append(
            {
                "Hour_Decimal": float(getattr(log, "hour_decimal", 0.0) or 0.0),
                "Losing_Streak": int(getattr(log, "losing_streak", 0) or 0),
                "Drawdown_State": float(getattr(log, "drawdown_state", 0.0) or 0.0),
                "Lot_Deviation": float(getattr(log, "lot_deviation", 0.0) or 0.0),
                "Revenge_Timer": float(getattr(log, "revenge_timer", 9999.0) or 9999.0),
                "Lots": float(getattr(log, "lots", 1.0) or 1.0),
                "RR Ratio": float(getattr(log, "rr_ratio", 1.0) or 1.0),
                "Realized_Vol_20": float(getattr(log, "realized_vol_20", 0.0) or 0.0),
                "Trend_Momentum": float(getattr(log, "trend_momentum", 0.0) or 0.0),
                "Is_High_Risk": int(
                    bool(getattr(log, "is_anomaly", False))
                    or decision in {Decision.BLOCK.value, Decision.REDUCE_SIZE.value}
                    or risk_score >= 0.85
                ),
            }
        )
    return pd.DataFrame(rows)


def _risk_dna_minimum_history(job_min_trades: int) -> int:
    """Risk DNA allows activation from 10 history trades instead of a hard 20."""
    _ = job_min_trades
    return 10


def _seed_feature_frame_with_risk_dna(
    feature_frame: pd.DataFrame,
    initial_parameters: UserInitialParameters,
) -> pd.DataFrame:
    """
    Prime the cold-start model with survey priors before fitting.

    IsolationForest has no partial_fit API, so we add a small set of synthetic
    safe/risk anchors and run a normal fit with the user's MT5 history.
    """
    lot_mean = initial_parameters.typical_lot_size
    lot_sigma = max(lot_mean * 0.25, 0.01)
    hard_lot_limit = lot_mean * initial_parameters.max_lot_multiplier
    drawdown_limit = initial_parameters.max_drawdown_pct / 100.0
    loss_threshold = initial_parameters.loss_review_threshold
    revenge_threshold = {
        "scalper": 3.0,
        "intraday": 10.0,
        "swing": 60.0,
    }[initial_parameters.trading_style.value]

    safe_anchor = {
        "Hour_Decimal": 10.0,
        "Losing_Streak": 0,
        "Drawdown_State": drawdown_limit * 0.25,
        "Lot_Deviation": 0.0,
        "Revenge_Timer": max(revenge_threshold * 3.0, initial_parameters.average_win_hold_minutes),
        "Lots": lot_mean,
        "RR Ratio": 2.0,
        "Realized_Vol_20": 0.0,
        "Trend_Momentum": 0.0,
        "Is_High_Risk": 0,
    }
    style_anchor = {
        **safe_anchor,
        "Hour_Decimal": 14.0,
        "Losing_Streak": max(loss_threshold - 1, 0),
        "Lot_Deviation": 1.0,
        "Revenge_Timer": max(revenge_threshold * 1.5, 5.0),
        "Lots": max(lot_mean + lot_sigma, 0.01),
    }
    risk_anchor = {
        **safe_anchor,
        "Losing_Streak": loss_threshold + 1,
        "Drawdown_State": drawdown_limit * 1.2,
        "Lot_Deviation": 3.25,
        "Revenge_Timer": max(min(revenge_threshold * 0.25, 5.0), 0.5),
        "Lots": max(hard_lot_limit * 1.1, lot_mean + (3.25 * lot_sigma)),
        "RR Ratio": 0.5,
        "Is_High_Risk": 1,
    }

    priors = pd.DataFrame([safe_anchor, style_anchor, risk_anchor])
    for column in FEATURE_COLUMNS_V2 + ["Is_High_Risk"]:
        if column not in feature_frame.columns:
            feature_frame[column] = 0.0
    return pd.concat([feature_frame, priors], ignore_index=True)


async def _retrain_user_model_from_behavioral_logs(user_id: str) -> None:
    if not await cache_manager.acquire_retraining_lock(user_id):
        logger.info("Retraining already active for %s; skipping duplicate trigger.", user_id)
        return

    async with AsyncSessionLocal() as session:
        try:
            logs = await list_behavioral_logs(session, user_id=user_id, limit=500)
            if len(logs) < 20:
                logger.info("Skipping retrain for %s: only %d behavioral logs.", user_id, len(logs))
                return

            feedback_labels = [getattr(log, "user_feedback_label", None) for log in logs]
            training_frame = _behavioral_logs_to_training_frame(logs)
            brain = SentinelBrain()
            await asyncio.to_thread(brain.train_with_rlhf, training_frame, user_id, feedback_labels)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".joblib") as handle:
                model_path = Path(handle.name)

            await asyncio.to_thread(brain.save, model_path)
            model_key = await asyncio.to_thread(model_store.upload_model, user_id, model_path)
            model_path.unlink(missing_ok=True)

            from sentinel.brain.risk_engine import get_progression_level
            next_level = get_progression_level(len(logs))

            trained_at = datetime.now(timezone.utc)
            await upsert_user(
                session,
                user_id,
                model_s3_key=model_key,
                trade_count=len(logs),
                is_baseline_ready=True,
                trained_at=trained_at,
                maturity_state=UserMaturity.MATURITY_2.value,
                model_level=next_level,
            )
            cache_user_brain(user_id, model_key, brain)
            logger.info("Retrained personalized model for %s (Level %d) from %d behavioral logs.", user_id, next_level, len(logs))
        except Exception:
            logger.exception("Behavioral-log retraining failed for %s", user_id)


def _maturity_for_trade_count(trade_count: int, baseline_ready: bool) -> UserMaturity:
    if baseline_ready:
        return UserMaturity.MATURITY_2
    if trade_count > 0:
        return UserMaturity.MATURITY_1
    return UserMaturity.MATURITY_0


def _next_live_maturity(profile: UserBaseline, brain_loaded: bool, next_trade_count: int) -> UserMaturity:
    return _maturity_for_trade_count(
        next_trade_count,
        profile.is_baseline_ready and brain_loaded,
    )


async def _compute_shap_background(
    context: TradeContext,
    user_id: str,
    audit_id: int,
) -> None:
    try:
        from sentinel.infra.db import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            brain = await get_user_brain(user_id, session)
            if brain is None:
                brain = SentinelBrain()
            
            X_input = brain._context_to_dataframe(context)
            explanation = await asyncio.to_thread(brain._explain, X_input)
            
            exp_list = [e.model_dump(mode="json") for e in explanation] if hasattr(explanation[0], "model_dump") else [e for e in explanation] if explanation else []
            top_reason = exp_list[0]["feature"] if exp_list else None
            
            await update_risk_audit_explanation(session, audit_id, exp_list, top_reason)
    except Exception:
        logger.exception("Background SHAP calculation failed for %s", user_id)


async def _train_and_persist_user_model(
    submission: OnboardingDataSubmission,
) -> None:
    async with AsyncSessionLocal() as session:
        job = await get_onboarding_job(session, submission.job_id)
        if job is None:
            logger.error("Onboarding data received for unknown job %s", submission.job_id)
            return

        try:
            if len(submission.trades) == 0:
                await upsert_user(
                    session,
                    submission.user_id,
                    trade_count=0,
                    is_baseline_ready=False,
                    trained_at=None,
                    maturity_state=UserMaturity.MATURITY_0.value,
                    model_level=1,
                )
                await update_onboarding_job(
                    session,
                    submission.job_id,
                    state=OnboardingState.BLANK_BASELINE.value,
                    message=(
                        "Blank baseline created. No MT5 trade history was found yet. "
                        "The account can continue trading until enough history exists to train."
                    ),
                    trade_count=0,
                    model_s3_key=None,
                    completed_at=datetime.now(timezone.utc),
                )
                logger.info("Blank baseline recorded for user %s", submission.user_id)
                return

            raw_frame = _trades_to_frame(submission.trades)
            feature_frame = await asyncio.to_thread(engineer_features, raw_frame)
            user = await get_user(session, submission.user_id)
            initial_parameters = UserInitialParameters.model_validate(
                getattr(user, "initial_parameters", None) or {}
            )
            feature_frame = _seed_feature_frame_with_risk_dna(feature_frame, initial_parameters)
            trade_count = len(submission.trades)
            if trade_count < 20:
                trained_at = datetime.now(timezone.utc)
                await upsert_user(
                    session,
                    submission.user_id,
                    model_s3_key=None,
                    trade_count=trade_count,
                    is_baseline_ready=False,
                    trained_at=trained_at,
                    maturity_state=UserMaturity.MATURITY_1.value,
                    model_level=1,
                )
                await update_onboarding_job(
                    session,
                    submission.job_id,
                    state=OnboardingState.READY.value,
                    message=(
                        f"Rule-Based Risk DNA Layer active. Captured {trade_count} trades. "
                        "Governed by safe baseline limits until trade history matures."
                    ),
                    trade_count=trade_count,
                    model_s3_key=None,
                    completed_at=trained_at,
                )
                logger.info("Cold-start Rule-Based Risk DNA Layer activated for user %s with %d trades.", submission.user_id, trade_count)
                return

            brain = SentinelBrain()
            await asyncio.to_thread(brain.train, feature_frame)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".joblib") as handle:
                model_path = Path(handle.name)

            await asyncio.to_thread(brain.save, model_path)
            model_key = await asyncio.to_thread(model_store.upload_model, submission.user_id, model_path)
            model_path.unlink(missing_ok=True)

            trade_count = len(submission.trades)
            required_trade_count = _risk_dna_minimum_history(int(job.min_trades))
            baseline_ready = trade_count >= required_trade_count
            trained_at = datetime.now(timezone.utc)
            await upsert_user(
                session,
                submission.user_id,
                model_s3_key=model_key,
                trade_count=trade_count,
                is_baseline_ready=baseline_ready,
                trained_at=trained_at,
                maturity_state=_maturity_for_trade_count(
                    trade_count,
                    baseline_ready,
                ).value,
                model_level=get_progression_level(trade_count),
            )
            await update_onboarding_job(
                session,
                submission.job_id,
                state=OnboardingState.READY.value,
                message=(
                    "Risk DNA baseline ready. Personalized model persisted."
                    if baseline_ready
                    else (
                        "Partial Risk DNA baseline persisted. Sentinel will shadow-watch "
                        f"until {required_trade_count} trades are available."
                    )
                ),
                trade_count=trade_count,
                model_s3_key=model_key,
                completed_at=trained_at,
            )
            cache_user_brain(submission.user_id, model_key, brain)
            logger.info("Onboarding complete for user %s", submission.user_id)
        except Exception as exc:
            logger.error("Failed to train onboarding job %s: %s", submission.job_id, exc, exc_info=True)
            await update_onboarding_job(
                session,
                submission.job_id,
                state=OnboardingState.FAILED.value,
                message=f"Onboarding failed: {exc}",
                error_detail=str(exc),
            )


@router.post(
    "/credentials",
    response_model=CredentialResponse,
    summary="Store broker credentials securely",
)
async def store_broker_credentials(
    request: CredentialRequest,
    session: AsyncSession = Depends(get_db),
) -> CredentialResponse:
    try:
        vault_manager.store_broker_credentials(
            user_id=request.user_id,
            server=request.broker_server,
            login_id=int(request.account_id),
            password_readonly=request.read_only_password,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to store broker credentials securely: {exc}",
        ) from exc

    vault_path = vault_manager.get_vault_path(request.user_id)
    await upsert_user(
        session,
        request.user_id,
        broker_server=request.broker_server,
        account_id=request.account_id,
        vault_path=vault_path,
    )
    return CredentialResponse(
        user_id=request.user_id,
        stored=True,
        vault_path=vault_path,
    )


@router.post(
    "/webhooks/whop",
    response_model=WhopWebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Provision a trader from a Whop activation event",
)
async def whop_webhook(
    request: WhopWebhookRequest,
    session: AsyncSession = Depends(get_db),
) -> WhopWebhookResponse:
    await upsert_user(session, request.user_id)

    raw_api_key = f"sz_live_{secrets.token_urlsafe(24)}"
    helm_release = _build_helm_release(request.user_id)
    helm_command = _build_helm_command(request.user_id, request.plan, helm_release)

    await upsert_api_credential(
        session,
        user_id=request.user_id,
        email=request.email,
        plan=request.plan,
        raw_api_key=raw_api_key,
        helm_release=helm_release,
        helm_command=helm_command,
        provisioning_state="helm_command_prepared",
    )

    logger.info(
        "Prepared Whop provisioning for user %s with release %s",
        request.user_id,
        helm_release,
    )

    return WhopWebhookResponse(
        user_id=request.user_id,
        api_key=raw_api_key,
        api_key_last4=raw_api_key[-4:],
        helm_release=helm_release,
        helm_command=helm_command,
        provisioning_state="helm_command_prepared",
    )


@router.post(
    "/analyze",
    response_model=RiskAssessment,
    summary="Analyze trade risk",
    description="Identity-aware risk assessment backed by a per-user model.",
)
async def analyze_trade(
    context: TradeContext,
    background_tasks: BackgroundTasks,
    request: Request,
    session: AsyncSession = Depends(get_db),
    _rate = Depends(rate_limiter),
) -> RiskAssessment:
    auth_user_id = getattr(request.state, "user_id", None)
    if not os.getenv("SENTINEL_AUTH_DISABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        if not auth_user_id or auth_user_id != context.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Tenant Isolation violation."
            )
    logger.info("analyze_trade received position_id: %s for user %s (symbol=%s, lots=%.2f)", context.position_id, context.user_id, context.symbol, context.lots)
    payload = context.model_dump(mode="json")
    cache_key = cache_manager.build_risk_cache_key(context.user_id, payload)

    try:
        cached = await cache_manager.get_cached_risk(cache_key)
    except Exception:
        cached = None

    if cached is not None:
        assessment = RiskAssessment.model_validate(cached)
        try:
            await record_risk_audit(
                session,
                user_id=context.user_id,
                symbol=context.symbol,
                decision=assessment.decision.value,
                risk_score=assessment.risk_score,
                size_multiplier=assessment.size_multiplier,
                mode=assessment.mode.value,
                is_anomaly=assessment.is_anomaly,
                top_reason=assessment.explanation[0].feature if assessment.explanation else None,
                explanation=assessment.model_dump(mode="json")["explanation"],
                latency_ms=assessment.latency_ms,
                cached=True,
            )
        except Exception:
            logger.exception("Failed to persist cached risk audit for %s", context.user_id)
        return assessment

    try:
        brain = await get_user_brain(context.user_id, session)
    except Exception:
        logger.exception("Failed to load user brain for %s", context.user_id)
        brain = None

    user = await get_user(session, context.user_id)
    profile = (
        _user_to_profile(user)
        if user is not None
        else UserBaseline(user_id=context.user_id, trade_count=0, is_baseline_ready=False)
    )
    initial_profile = profile.initial_parameters
    try:
        await cache_manager.cache_behavioral_profile(
            context.user_id,
            {
                **profile.model_dump(mode="json"),
                "avg_lots": initial_profile.typical_lot_size,
                "std_lots": max(initial_profile.typical_lot_size * 0.25, 0.01),
                "typical_daily_trades": initial_profile.typical_daily_trades,
                "average_win_hold_minutes": initial_profile.average_win_hold_minutes,
                "tilt_response": initial_profile.tilt_response.value,
                "loss_review_threshold": initial_profile.loss_review_threshold,
            },
        )
    except Exception:
        logger.exception("Failed to cache behavioral profile for %s", context.user_id)
    maturity_state = _maturity_for_trade_count(
        profile.trade_count,
        profile.is_baseline_ready and brain is not None,
    )

    if brain is None:
        brain = SentinelBrain()

    if maturity_state in {UserMaturity.MATURITY_0, UserMaturity.MATURITY_1}:
        assessment = await asyncio.to_thread(
            brain.assess_bootstrap_risk,
            context,
            profile.initial_parameters,
            maturity_state,
        )
    else:
        # Check if the user has breached losing_streak >= 2 in the last 12 hours.
        losing_streak_breached_12h = False
        if context.losing_streak >= 2:
            losing_streak_breached_12h = True
        else:
            from datetime import timedelta, timezone
            cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
            from sentinel.infra.db import DB_AVAILABLE, _memory_behavioral_logs, hash_user_id
            if not DB_AVAILABLE:
                user_hash = hash_user_id(context.user_id)
                for log in _memory_behavioral_logs:
                    log_created = getattr(log, "created_at", None)
                    if log_created and getattr(log, "user_hash", None) == user_hash:
                        if log_created >= cutoff and getattr(log, "losing_streak", 0) >= 2:
                            losing_streak_breached_12h = True
                            break
            else:
                try:
                    from sqlalchemy import select
                    from sentinel.infra.db import BehavioralLog
                    res = await session.execute(
                        select(BehavioralLog.losing_streak)
                        .where(BehavioralLog.user_hash == hash_user_id(context.user_id))
                        .where(BehavioralLog.created_at >= cutoff)
                        .where(BehavioralLog.losing_streak >= 2)
                        .limit(1)
                    )
                    if res.scalar() is not None:
                        losing_streak_breached_12h = True
                except Exception:
                    user_hash = hash_user_id(context.user_id)
                    for log in _memory_behavioral_logs:
                        log_created = getattr(log, "created_at", None)
                        if log_created and getattr(log, "user_hash", None) == user_hash:
                            if log_created >= cutoff and getattr(log, "losing_streak", 0) >= 2:
                                losing_streak_breached_12h = True
                                break

        assessment = await asyncio.to_thread(
            brain.assess_risk,
            context,
            skip_explanation=True,
            losing_streak_breached_12h=losing_streak_breached_12h,
        )

    try:
        await cache_manager.cache_risk_score(cache_key, assessment.model_dump(mode="json"))
    except Exception:
        logger.exception("Failed to cache risk assessment for %s", context.user_id)

    # Build a fallback rule-based explanation when no baseline model is trained yet
    fallback_explanation: list[dict] = []
    fallback_top_reason: str | None = None

    mode_val = assessment.mode.value if hasattr(assessment.mode, "value") else str(assessment.mode)
    if mode_val in ("baseline_pending", "normal") and assessment.risk_score >= 0.9:
        # Derive which feature drove the block based on the raw context values
        signals: list[tuple[str, float, str]] = []
        if context.drawdown_state > 0.03:
            signals.append(("drawdown_state", context.drawdown_state, "Account drawdown exceeds 3% threshold"))
        if context.losing_streak >= 3:
            signals.append(("losing_streak", float(context.losing_streak), f"{context.losing_streak} consecutive losses detected"))
        if 0 < context.revenge_timer < 300:
            signals.append(("revenge_timer", context.revenge_timer, "Position opened <5 min after a loss — revenge pattern"))
        if context.lot_deviation > 1.5:
            signals.append(("lot_deviation", context.lot_deviation, "Lot size deviates significantly from baseline"))
        if not signals:
            signals.append(("baseline_pending", 1.0, "No trade baseline established — conservative block until model trains"))

        signals.sort(key=lambda s: s[1], reverse=True)
        fallback_explanation = [
            {"feature": feat, "impact": round(val * 0.3, 4)}
            for feat, val, desc in signals
        ]
        fallback_top_reason = signals[0][0]

    try:
        audit_record = await record_risk_audit(
            session,
            user_id=context.user_id,
            symbol=context.symbol,
            decision=assessment.decision.value,
            risk_score=assessment.risk_score,
            size_multiplier=assessment.size_multiplier,
            mode=assessment.mode.value,
            is_anomaly=assessment.is_anomaly,
            top_reason=fallback_top_reason,
            explanation=fallback_explanation,
            latency_ms=assessment.latency_ms,
            cached=False,
        )
        # Check if this is a new position ticket to prevent double-counting 20Hz live telemetry ticks
        is_new_trade = True
        if context.position_id:
            cache_key = f"last_pos:{context.user_id}:{context.position_id}"
            if await cache_manager.r.get(cache_key) is not None:
                is_new_trade = False
            else:
                await cache_manager.r.set(cache_key, "1", ex=7200)

        if is_new_trade:
            await record_behavioral_log(
                session,
                user_id=context.user_id,
                audit_id=getattr(audit_record, "id", None),
                symbol=context.symbol,
                hour_decimal=context.hour_decimal,
                losing_streak=context.losing_streak,
                drawdown_state=context.drawdown_state,
                lot_deviation=context.lot_deviation,
                revenge_timer=context.revenge_timer,
                lots=context.lots,
                rr_ratio=context.rr_ratio,
                realized_vol_20=context.realized_vol_20,
                trend_momentum=context.trend_momentum,
                decision=assessment.decision.value,
                risk_score=assessment.risk_score,
                size_multiplier=assessment.size_multiplier,
                is_anomaly=assessment.is_anomaly,
            )
            next_trade_count = profile.trade_count + 1
            next_maturity = _next_live_maturity(profile, brain is not None and brain.is_trained, next_trade_count)
            next_level = get_progression_level(next_trade_count)
            await upsert_user(
                session,
                context.user_id,
                trade_count=next_trade_count,
                maturity_state=next_maturity.value,
                is_baseline_ready=profile.is_baseline_ready and brain is not None and brain.is_trained,
                model_level=next_level,
            )
            recent_logs = await list_behavioral_logs(session, user_id=context.user_id, limit=500)
            if recent_logs:
                lot_values = pd.Series([float(getattr(log, "lots", 0.0) or 0.0) for log in recent_logs])
                await cache_manager.cache_behavioral_profile(
                    context.user_id,
                    {
                        **profile.model_dump(mode="json"),
                        "trade_count": next_trade_count,
                        "maturity_state": next_maturity.value,
                        "model_level": next_level,
                        "avg_lots": round(float(lot_values.mean()), 6),
                        "std_lots": round(max(float(lot_values.std(ddof=0) or 0.0), 0.01), 6),
                        "typical_daily_trades": initial_profile.typical_daily_trades,
                        "average_win_hold_minutes": initial_profile.average_win_hold_minutes,
                        "tilt_response": initial_profile.tilt_response.value,
                        "loss_review_threshold": initial_profile.loss_review_threshold,
                        "last_trade_count": next_trade_count,
                    },
                )
            if next_trade_count >= 20 and next_trade_count % 20 == 0:
                background_tasks.add_task(_retrain_user_model_from_behavioral_logs, context.user_id)

        # Only schedule SHAP if user has a real trained model
        if getattr(audit_record, "id", None) is not None and not fallback_explanation:
            background_tasks.add_task(_compute_shap_background, context, context.user_id, audit_record.id)
    except Exception:
        logger.exception("Failed to persist risk audit for %s", context.user_id)

    return assessment


@router.post(
    "/onboard",
    response_model=OnboardingStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start user onboarding",
)
async def start_onboarding(
    request: OnboardingRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    # Dynamically setup Portable Mode directory on the EC2 host
    duplicate_mt5_directory(request.user_id)

    await upsert_user(
        session,
        request.user_id,
        broker_server=request.broker_server,
        account_id=request.account_id,
        initial_parameters=request.initial_parameters.model_dump(mode="json"),
        maturity_state=UserMaturity.MATURITY_0.value,
        enforce_mode=False,
        model_level=1,
        feedback_score=1.0,
        capital_protected=0.0,
    )

    job_id = str(uuid.uuid4())
    job = await create_onboarding_job(
        session,
        job_id=job_id,
        user_id=request.user_id,
        broker_server=request.broker_server,
        account_id=request.account_id,
        min_trades=request.min_trades,
        state=OnboardingState.PENDING.value,
        message="Onboarding accepted. Waiting for MT5 bridge verification.",
    )
    raw_api_key = f"sz_live_{secrets.token_urlsafe(24)}"
    helm_release = _build_helm_release(request.user_id)
    helm_command = _build_helm_command(request.user_id, "direct", helm_release)
    await upsert_api_credential(
        session,
        user_id=request.user_id,
        email=f"{request.user_id}@direct.sentinel.local",
        plan="direct",
        raw_api_key=raw_api_key,
        helm_release=helm_release,
        helm_command=helm_command,
        provisioning_state="onboarding_key_issued",
    )

    async def publish_onboarding_command() -> None:
        print(f"[BG] publish_onboarding_command started for user_id={request.user_id}, job_id={job_id}")
        command = {
            "job_id": job_id,
            "user_id": request.user_id,
            "broker_server": request.broker_server,
            "account_id": request.account_id,
            "min_trades": request.min_trades,
            "callback_url": f"{os.getenv('PUBLIC_API_BASE_URL', '').rstrip('/')}/v1/onboard/data",
        }
        try:
            print(f"[BG] Enqueuing onboarding job to cache. r = {cache_manager.r}")
            await cache_manager.enqueue_onboarding_job(command)
            print("[BG] Successfully enqueued onboarding job to cache")
        except Exception as e:
            print(f"[BG] ERROR: Failed to enqueue onboarding job: {e}")
            import traceback
            traceback.print_exc()

        try:
            async with AsyncSessionLocal() as publish_session:
                await update_onboarding_job(
                    publish_session,
                    job_id,
                    state=OnboardingState.PULLING_HISTORY.value,
                    message="MT5 bridge command queued. Waiting for historical trades.",
                )
            print("[BG] Successfully updated onboarding job state to pulling_history")
        except Exception as e:
            print(f"[BG] ERROR: Failed to update onboarding job state in DB: {e}")
            import traceback
            traceback.print_exc()

    background_tasks.add_task(publish_onboarding_command)
    status_response = _job_to_status(job)
    status_response.api_key = raw_api_key
    status_response.api_key_last4 = raw_api_key[-4:]
    return status_response


@router.get(
    "/onboard/{job_id}",
    response_model=OnboardingStatus,
    summary="Check onboarding status",
)
async def check_onboarding(
    job_id: str,
    session: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    job = await get_onboarding_job(session, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding job {job_id} not found.",
        )
    return _job_to_status(job)


@router.post(
    "/onboard/data",
    response_model=OnboardingStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Receive MT5 history for onboarding",
)
async def receive_onboarding_data(
    submission: OnboardingDataSubmission,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    job = await get_onboarding_job(session, submission.job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding job {submission.job_id} not found.",
        )
    if job.user_id != submission.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission user_id does not match onboarding job.",
        )
    if len(submission.trades) == 0:
        job = await update_onboarding_job(
            session,
            submission.job_id,
            state=OnboardingState.BLANK_BASELINE.value,
            message=(
                "No historical MT5 deals were found. A blank baseline will be created and "
                "the account will remain baseline-pending until enough trades accumulate."
            ),
            trade_count=0,
        )
        background_tasks.add_task(_train_and_persist_user_model, submission)
        if job is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Job update failed.")
        return _job_to_status(job)
    # Accept whatever history exists — new accounts simply get a partial baseline
    logger.info(
        "Received %d trades for job %s (min_trades=%d). Training with available history.",
        len(submission.trades),
        submission.job_id,
        job.min_trades,
    )

    job = await update_onboarding_job(
        session,
        submission.job_id,
        state=OnboardingState.TRAINING.value,
        message="Historical trades received. Training personalized model.",
        trade_count=len(submission.trades),
    )
    background_tasks.add_task(_train_and_persist_user_model, submission)





@router.get(
    "/user/{user_id}/profile",
    response_model=UserBaseline,
    summary="Get user baseline profile",
)
async def get_user_profile(
    user_id: str,
    session: AsyncSession = Depends(get_db),
    _auth = Depends(verify_tenant_isolation),
) -> UserBaseline:
    user = await get_user(session, user_id)
    if user is None:
        return UserBaseline(user_id=user_id, trade_count=0, is_baseline_ready=False)
    return _user_to_profile(user)


@router.get(
    "/user/{user_id}/audits",
    response_model=list[RiskAuditRecord],
    summary="Get user risk audit history",
)
async def get_user_audits(
    user_id: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
    _auth = Depends(verify_tenant_isolation),
) -> list[RiskAuditRecord]:
    safe_limit = min(max(limit, 1), 200)
    audits = await list_risk_audits(session, user_id=user_id, limit=safe_limit)
    from sentinel.infra.db import DB_AVAILABLE, _memory_behavioral_logs, hash_user_id
    if not DB_AVAILABLE:
        submitted_ids = {
            log.audit_id for log in _memory_behavioral_logs
            if log.user_hash == hash_user_id(user_id) and log.user_feedback_label is not None and log.audit_id is not None
        }
    else:
        try:
            from sqlalchemy import select
            res = await session.execute(
                select(BehavioralLog.audit_id)
                .where(BehavioralLog.user_hash == hash_user_id(user_id))
                .where(BehavioralLog.user_feedback_label.is_not(None))
            )
            submitted_ids = set(res.scalars().all())
        except Exception:
            submitted_ids = {
                log.audit_id for log in _memory_behavioral_logs
                if log.user_hash == hash_user_id(user_id) and log.user_feedback_label is not None and log.audit_id is not None
            }
    return [_audit_to_record(audit, submitted_ids) for audit in audits]



@router.get(
    "/user/{user_id}/dashboard",
    response_model=WorkspaceSummary,
    summary="Get dashboard workspace data for a user",
)
async def get_user_dashboard(
    user_id: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
    _auth = Depends(verify_tenant_isolation),
) -> WorkspaceSummary:
    user = await get_user(session, user_id)
    profile = (
        _user_to_profile(user)
        if user is not None
        else UserBaseline(user_id=user_id, trade_count=0, is_baseline_ready=False)
    )

    audits = await list_risk_audits(session, user_id=user_id, limit=min(max(limit, 1), 200))
    from sentinel.infra.db import DB_AVAILABLE, _memory_behavioral_logs, hash_user_id
    if not DB_AVAILABLE:
        submitted_ids = {
            log.audit_id for log in _memory_behavioral_logs
            if log.user_hash == hash_user_id(user_id) and log.user_feedback_label is not None and log.audit_id is not None
        }
    else:
        try:
            from sqlalchemy import select
            res = await session.execute(
                select(BehavioralLog.audit_id)
                .where(BehavioralLog.user_hash == hash_user_id(user_id))
                .where(BehavioralLog.user_feedback_label.is_not(None))
            )
            submitted_ids = set(res.scalars().all())
        except Exception:
            submitted_ids = {
                log.audit_id for log in _memory_behavioral_logs
                if log.user_hash == hash_user_id(user_id) and log.user_feedback_label is not None and log.audit_id is not None
            }
    records = [_audit_to_record(audit, submitted_ids) for audit in audits]

    decision_counts = {decision.value: 0 for decision in Decision}
    for record in records:
        decision_counts[record.decision.value] += 1

    average_risk_score = (
        sum(record.risk_score for record in records) / len(records)
        if records
        else 0.0
    )
    average_latency_ms = (
        sum(record.latency_ms for record in records) / len(records)
        if records
        else 0.0
    )
    protection_events = sum(
        1 for record in records if record.decision in {Decision.BLOCK, Decision.REDUCE_SIZE}
    )

    # 1. Calculate top reason
    latest_record = records[0] if records else None
    top_reason_str = latest_record.top_reason if latest_record else "MONITORING SYSTEM STEADY"
    if latest_record and not top_reason_str and latest_record.explanation:
        top_reason_str = latest_record.explanation[0].feature

    # 2. Calculate discipline streak
    discipline_streak = 0
    for record in records:
        if record.decision == Decision.ALLOW:
            discipline_streak += 1
        else:
            break

    # 3. Calculate active capital at risk
    if latest_record:
        active_capital_at_risk = round(profile.initial_parameters.typical_lot_size * latest_record.size_multiplier * 5000.0, 2)
    else:
        active_capital_at_risk = round(profile.initial_parameters.typical_lot_size * 5000.0, 2)

    # 4. Calculate circadian risk profile
    circadian_risk_profile = {9: 0.15, 14: 0.22, 16: 0.18, 21: 0.12}
    if records:
        hour_buckets = {9: [], 14: [], 16: [], 21: []}
        for record in records:
            h_utc = record.created_at.hour
            if 8 <= h_utc < 12:
                hour_buckets[9].append(record.risk_score)
            elif 12 <= h_utc < 16:
                hour_buckets[14].append(record.risk_score)
            elif 16 <= h_utc < 20:
                hour_buckets[16].append(record.risk_score)
            else:
                hour_buckets[21].append(record.risk_score)
        for h, scores in hour_buckets.items():
            if scores:
                circadian_risk_profile[h] = round(sum(scores) / len(scores), 4)

    # Calculate 12-hour losing streak breach state
    losing_streak_breached_12h = False
    from datetime import timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    if not DB_AVAILABLE:
        user_hash = hash_user_id(user_id)
        for log in _memory_behavioral_logs:
            log_created = getattr(log, "created_at", None)
            if log_created and getattr(log, "user_hash", None) == user_hash:
                if log_created >= cutoff and getattr(log, "losing_streak", 0) >= 2:
                    losing_streak_breached_12h = True
                    break
    else:
        try:
            from sqlalchemy import select
            from sentinel.infra.db import BehavioralLog
            res = await session.execute(
                select(BehavioralLog.losing_streak)
                .where(BehavioralLog.user_hash == hash_user_id(user_id))
                .where(BehavioralLog.created_at >= cutoff)
                .where(BehavioralLog.losing_streak >= 2)
                .limit(1)
            )
            if res.scalar() is not None:
                losing_streak_breached_12h = True
        except Exception:
            user_hash = hash_user_id(user_id)
            for log in _memory_behavioral_logs:
                log_created = getattr(log, "created_at", None)
                if log_created and getattr(log, "user_hash", None) == user_hash:
                    if log_created >= cutoff and getattr(log, "losing_streak", 0) >= 2:
                        losing_streak_breached_12h = True
                        break

    return WorkspaceSummary(
        user_id=user_id,
        profile=profile,
        recent_audits=records,
        latest_assessment=latest_record,
        decision_counts=decision_counts,
        average_risk_score=average_risk_score,
        average_latency_ms=average_latency_ms,
        protection_events=protection_events,
        blank_baseline=(not profile.is_baseline_ready and profile.trade_count == 0),
        top_reason=top_reason_str,
        discipline_streak=discipline_streak,
        active_capital_at_risk=active_capital_at_risk,
        circadian_risk_profile=circadian_risk_profile,
        losing_streak_breached_12h=losing_streak_breached_12h,
    )


@router.get(
    "/admin/overview",
    response_model=AdminOverview,
    summary="Get fleet-wide admin overview",
)
async def get_admin_overview(
    session: AsyncSession = Depends(get_db),
) -> AdminOverview:
    users = await list_users(session, limit=250)
    credentials = await list_api_credentials(session, limit=250)
    audits = await list_risk_audits(session, limit=500)
    jobs = await list_onboarding_jobs(session, limit=50)

    credentials_by_user = {credential.user_id: credential for credential in credentials}
    latest_audit_by_user: dict[str, RiskAuditRecord] = {}
    for audit in audits:
        if audit.user_id not in latest_audit_by_user:
            latest_audit_by_user[audit.user_id] = _audit_to_record(audit)

    user_rows: list[AdminUserRecord] = []
    for user in users:
        credential = credentials_by_user.get(user.user_id)
        latest = latest_audit_by_user.get(user.user_id)
        user_rows.append(
            AdminUserRecord(
                user_id=user.user_id,
                broker_server=user.broker_server,
                account_id=user.account_id,
                email=getattr(credential, "email", None),
                plan=getattr(credential, "plan", None),
                provisioning_state=getattr(credential, "provisioning_state", None),
                helm_release=getattr(credential, "helm_release", None),
                trade_count=user.trade_count or 0,
                is_baseline_ready=bool(user.is_baseline_ready),
                model_s3_key=user.model_s3_key,
                trained_at=user.trained_at,
                latest_risk_score=latest.risk_score if latest is not None else None,
                latest_decision=latest.decision if latest is not None else None,
                latest_mode=latest.mode if latest is not None else None,
                last_audit_at=latest.created_at if latest is not None else None,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )

    total_audits = len(audits)
    blocked_decisions = sum(1 for audit in audits if getattr(audit, "decision", "") == Decision.BLOCK.value)
    reduced_decisions = sum(
        1 for audit in audits if getattr(audit, "decision", "") == Decision.REDUCE_SIZE.value
    )
    average_risk_score = (
        sum(float(getattr(audit, "risk_score", 0.0) or 0.0) for audit in audits) / total_audits
        if total_audits
        else 0.0
    )

    return AdminOverview(
        total_users=len(users),
        baseline_ready_users=sum(1 for user in users if user.is_baseline_ready),
        active_api_credentials=len(credentials_by_user),
        total_audits=total_audits,
        blocked_decisions=blocked_decisions,
        reduced_decisions=reduced_decisions,
        average_risk_score=average_risk_score,
        users=user_rows,
        recent_jobs=[_job_to_status(job) for job in jobs],
    )


@router.post(
    "/user/{user_id}/autopsy",
    summary="Submit post-tilt autopsy feedback",
)
async def submit_autopsy_feedback(
    user_id: str,
    feedback: FeedbackSubmission,
    session: AsyncSession = Depends(get_db),
    _rate = Depends(rate_limiter),
    _auth = Depends(verify_tenant_isolation),
) -> dict:
    """Ingest post-tilt autopsy feedback and update rolling performance scores."""
    from sqlalchemy import select
    result = await session.execute(
        select(BehavioralLog).where(BehavioralLog.audit_id == feedback.audit_id)
    )
    log_record = result.scalar_one_or_none()
    if log_record:
        log_record.user_feedback_label = feedback.feedback_label
        
    # 2. Update user rolling score and capital protected metric
    user = await get_user(session, user_id)
    if user:
        if feedback.feedback_label == "VALID_INTERCEPT":
            user.capital_protected += feedback.estimated_capital_saved
            user.feedback_score = round((user.feedback_score * 0.9) + 0.1, 4)
        else:
            user.feedback_score = round(user.feedback_score * 0.9, 4)  # Hit to precision
            
        await session.commit()
        
    return {"status": "success", "message": "Feedback integrated into model training loop"}


async def global_flywheel_retrain(session: AsyncSession) -> dict:
    """
    Nightly background task that aggregates all anonymized 'BehavioralLog' data across ALL users,
    applies the RLHF weights (Valid Intercept = 1.5x boost, False Positive = 0.05x penalty),
    retrains the global Isolation Forest and RandomForest classifier, and overwrites default_model.joblib.
    Additionally, exports the dataset as a secure Parquet file to a simulated S3 data lake.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq
    import time
    from pathlib import Path
    from sentinel.infra.db import hash_user_id
    from sentinel.infra.s3 import model_store
    
    logger.info("[Flywheel] Starting nightly global flywheel retraining...")
    try:
        from sqlalchemy import select
        result = await session.execute(select(BehavioralLog))
        logs = result.scalars().all()
    except Exception as e:
        logger.exception("Failed to query behavioral logs for global flywheel")
        return {"status": "failed", "reason": str(e)}

    if len(logs) < 20:
        logger.warning("Insufficient logs for global flywheel retrain (got %d, need >= 20)", len(logs))
        return {"status": "skipped", "reason": "insufficient_data"}

    rows = []
    sample_weights = []
    y_labels = []

    for log in logs:
        rows.append({
            "Hour_Decimal": float(log.hour_decimal),
            "Losing_Streak": int(log.losing_streak),
            "Drawdown_State": float(log.drawdown_state),
            "Lot_Deviation": float(log.lot_deviation),
            "Revenge_Timer": float(log.revenge_timer),
            "Lots": float(log.lots),
            "RR Ratio": float(log.rr_ratio),
            "Realized_Vol_20": float(log.realized_vol_20),
            "Trend_Momentum": float(log.trend_momentum),
        })

        is_anomaly = bool(log.is_anomaly)
        y_labels.append(1 if is_anomaly or log.decision in {"BLOCK", "REDUCE_SIZE"} else 0)

        # RLHF weights: Valid Intercept = 1.5x boost, False Positive = 0.05x penalty, default = 1.0
        weight = 1.0
        if log.user_feedback_label == "VALID_INTERCEPT":
            weight = 1.5
        elif log.user_feedback_label == "FALSE_POSITIVE":
            weight = 0.05
        sample_weights.append(weight)

    df = pd.DataFrame(rows)
    X = df.fillna(0)
    y = pd.Series(y_labels)

    if y.nunique() < 2:
        # Guarantee class diversity to prevent RandomForest crashes
        X_extra = X.iloc[[0]].copy()
        X_extra["Losing_Streak"] = 5.0
        X_extra["Drawdown_State"] = 0.05
        X = pd.concat([X, X_extra], ignore_index=True)
        y = pd.concat([y, pd.Series([1 - int(y.iloc[0])])], ignore_index=True)
        sample_weights.append(1.0)

    new_brain = SentinelBrain()
    try:
        await asyncio.to_thread(new_brain.iso_forest.fit, X, sample_weight=sample_weights)
        await asyncio.to_thread(new_brain.classifier.fit, X, y, sample_weight=sample_weights)
        new_brain._is_trained = True
    except Exception as e:
        logger.exception("Failed to train core global models")
        return {"status": "failed", "reason": f"Model fit failed: {e}"}

    # Save & overwrite default baseline
    packaged_root = Path(__file__).resolve().parents[4]
    configured_model_path = Path(os.getenv("SENTINEL_MODEL_PATH", str(packaged_root / "default_model.joblib")))
    try:
        configured_model_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(new_brain.save, configured_model_path)
    except Exception as e:
        logger.warning("Failed to save default_model.joblib: %s", e)

    # Secure dataset export to S3 Data Lake (Parquet)
    df["Is_High_Risk"] = y.iloc[:len(df)].values
    df["Sample_Weight"] = sample_weights[:len(df)]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as tmp:
        parquet_path = Path(tmp.name)

    try:
        table = pa.Table.from_pandas(df)
        pq.write_table(table, parquet_path)
        s3_key = f"datasets/global_flywheel_retrain_{int(time.time())}.parquet"
        await asyncio.to_thread(model_store.upload_dataset, s3_key, parquet_path)
    except Exception as e:
        logger.warning("Failed to export/upload Parquet dataset: %s", e)
        s3_key = None
    finally:
        parquet_path.unlink(missing_ok=True)

    logger.info("[Flywheel] Global flywheel retraining complete. baseline upgraded successfully.")
    return {"status": "success", "s3_key": s3_key}


@router.post(
    "/admin/flywheel/retrain",
    summary="Trigger the global flywheel model retraining",
)
async def trigger_global_flywheel(
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> dict:
    background_tasks.add_task(global_flywheel_retrain, session)
    return {"status": "accepted", "message": "Global flywheel retraining started in background."}
