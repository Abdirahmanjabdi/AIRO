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
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.api.dependencies import cache_user_brain, get_user_brain
from sentinel.brain.feature_engine import engineer_features
from sentinel.brain.risk_engine import SentinelBrain
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
    WorkspaceSummary,
    WhopWebhookRequest,
    WhopWebhookResponse,
)
from sentinel.infra.db import (
    AsyncSessionLocal,
    create_onboarding_job,
    get_db,
    get_onboarding_job,
    get_user,
    list_api_credentials,
    list_onboarding_jobs,
    list_risk_audits,
    list_users,
    record_risk_audit,
    upsert_api_credential,
    update_onboarding_job,
    upsert_user,
    update_risk_audit_explanation,
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
    return UserBaseline(
        user_id=str(getattr(user, "user_id")),
        broker_server=getattr(user, "broker_server"),
        account_id=getattr(user, "account_id"),
        trade_count=int(getattr(user, "trade_count") or 0),
        model_s3_key=getattr(user, "model_s3_key"),
        trained_at=getattr(user, "trained_at"),
        is_baseline_ready=bool(getattr(user, "is_baseline_ready")),
    )


def _audit_to_record(audit: object) -> RiskAuditRecord:
    return RiskAuditRecord(
        audit_id=getattr(audit, "id", None),
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
            brain = SentinelBrain()
            await asyncio.to_thread(brain.train, feature_frame)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".joblib") as handle:
                model_path = Path(handle.name)

            await asyncio.to_thread(brain.save, model_path)
            model_key = await asyncio.to_thread(model_store.upload_model, submission.user_id, model_path)
            model_path.unlink(missing_ok=True)

            trade_count = len(submission.trades)
            trained_at = datetime.now(timezone.utc)
            await upsert_user(
                session,
                submission.user_id,
                model_s3_key=model_key,
                trade_count=trade_count,
                is_baseline_ready=trade_count >= job.min_trades,
                trained_at=trained_at,
            )
            await update_onboarding_job(
                session,
                submission.job_id,
                state=OnboardingState.READY.value,
                message="Baseline ready. Personalized model persisted.",
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
    session: AsyncSession = Depends(get_db),
) -> RiskAssessment:
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

    if brain is None:
        brain = SentinelBrain()

    assessment = await asyncio.to_thread(brain.assess_risk, context, skip_explanation=True)

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
        if context.revenge_timer > 300:
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
    await upsert_user(
        session,
        request.user_id,
        broker_server=request.broker_server,
        account_id=request.account_id,
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

    async def publish_onboarding_command() -> None:
        command = {
            "job_id": job_id,
            "user_id": request.user_id,
            "broker_server": request.broker_server,
            "account_id": request.account_id,
            "min_trades": request.min_trades,
            "callback_url": f"{os.getenv('PUBLIC_API_BASE_URL', '').rstrip('/')}/v1/onboard/data",
        }
        await cache_manager.enqueue_onboarding_job(command)
        async with AsyncSessionLocal() as publish_session:
            await update_onboarding_job(
                publish_session,
                job_id,
                state=OnboardingState.PULLING_HISTORY.value,
                message="MT5 bridge command queued. Waiting for historical trades.",
            )

    background_tasks.add_task(publish_onboarding_command)
    return _job_to_status(job)


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
    if job is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Job update failed.")
    return _job_to_status(job)


@router.get(
    "/user/{user_id}/profile",
    response_model=UserBaseline,
    summary="Get user baseline profile",
)
async def get_user_profile(
    user_id: str,
    session: AsyncSession = Depends(get_db),
) -> UserBaseline:
    user = await get_user(session, user_id)
    if user is None:
        return UserBaseline(user_id=user_id, trade_count=0, is_baseline_ready=False)
    return _user_to_profile(user)


@router.get(
    "/user/{user_id}/audits",
    response_model=list[RiskAuditRecord],
    summary="List recent risk audits for a user",
)
async def get_user_audits(
    user_id: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
) -> list[RiskAuditRecord]:
    safe_limit = min(max(limit, 1), 200)
    audits = await list_risk_audits(session, user_id=user_id, limit=safe_limit)
    return [_audit_to_record(audit) for audit in audits]


@router.get(
    "/user/{user_id}/dashboard",
    response_model=WorkspaceSummary,
    summary="Get dashboard workspace data for a user",
)
async def get_user_dashboard(
    user_id: str,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
) -> WorkspaceSummary:
    user = await get_user(session, user_id)
    profile = (
        _user_to_profile(user)
        if user is not None
        else UserBaseline(user_id=user_id, trade_count=0, is_baseline_ready=False)
    )

    audits = await list_risk_audits(session, user_id=user_id, limit=min(max(limit, 1), 200))
    records = [_audit_to_record(audit) for audit in audits]

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

    return WorkspaceSummary(
        user_id=user_id,
        profile=profile,
        recent_audits=records,
        latest_assessment=records[0] if records else None,
        decision_counts=decision_counts,
        average_risk_score=average_risk_score,
        average_latency_ms=average_latency_ms,
        protection_events=protection_events,
        blank_baseline=(not profile.is_baseline_ready and profile.trade_count == 0),
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
