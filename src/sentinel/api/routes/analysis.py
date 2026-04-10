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
    CredentialRequest,
    CredentialResponse,
    Decision,
    HistoricalTrade,
    OnboardingDataSubmission,
    OnboardingRequest,
    OnboardingState,
    OnboardingStatus,
    RiskAssessment,
    TradeContext,
    UserBaseline,
    WhopWebhookRequest,
    WhopWebhookResponse,
)
from sentinel.infra.db import (
    AsyncSessionLocal,
    create_onboarding_job,
    get_db,
    get_onboarding_job,
    get_user,
    record_risk_audit,
    upsert_api_credential,
    update_onboarding_job,
    upsert_user,
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

    assessment = await asyncio.to_thread(brain.assess_risk, context)

    try:
        await cache_manager.cache_risk_score(cache_key, assessment.model_dump(mode="json"))
    except Exception:
        logger.exception("Failed to cache risk assessment for %s", context.user_id)

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
            cached=False,
        )
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
    if len(submission.trades) < job.min_trades:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Expected at least {job.min_trades} trades, received {len(submission.trades)}.",
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
