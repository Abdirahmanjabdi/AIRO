"""
Sentinel-Zero — Analysis Routes
=================================
Core Brain API endpoints for risk assessment and onboarding.

POST /v1/analyze            → Sub-50ms risk assessment
POST /v1/onboard            → 202 Accepted + async baseline training
GET  /v1/onboard/{job_id}   → Poll onboarding status
GET  /v1/user/{user_id}/profile → User baseline summary

Ref: ARCHITECTURE.md §6, AI_CONTRACT.md §4
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from sentinel.api.dependencies import get_brain, get_onboarding_store
from sentinel.brain.risk_engine import SentinelBrain
from sentinel.domain.models import (
    Decision,
    OnboardingRequest,
    OnboardingState,
    OnboardingStatus,
    RiskAssessment,
    TradeContext,
    UserBaseline,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# POST /v1/analyze — Real-time risk assessment
# =============================================================================

@router.post(
    "/analyze",
    response_model=RiskAssessment,
    summary="Analyze trade risk",
    description="Stateless risk assessment. Target latency: <50ms.",
)
async def analyze_trade(
    context: TradeContext,
    brain: SentinelBrain = Depends(get_brain),
) -> RiskAssessment:
    """
    Receives trade telemetry from the Sentinel Pod bridge.
    Returns intervention decision with SHAP explanation.

    Route handler follows AI_CONTRACT §1.4:
    validate → delegate → respond (max 10 lines).
    """
    # ML prediction is CPU-bound — run in thread pool to avoid blocking
    result: RiskAssessment = await asyncio.to_thread(
        brain.assess_risk, context,
    )
    return result


# =============================================================================
# POST /v1/onboard — Async baseline training (FP adjustment #2)
# =============================================================================

@router.post(
    "/onboard",
    response_model=OnboardingStatus,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start user onboarding",
    description=(
        "Initiates async baseline training. Returns 202 + job_id immediately. "
        "Poll GET /v1/onboard/{job_id} for status."
    ),
)
async def start_onboarding(
    request: OnboardingRequest,
    background_tasks: BackgroundTasks,
    store: dict[str, dict[str, object]] = Depends(get_onboarding_store),
) -> OnboardingStatus:
    """
    FP Rule: NEVER synchronous. Returns 202 and fires background task.
    In production, this would be a Celery task with Redis broker.
    """
    job_id = str(uuid.uuid4())

    job_status = OnboardingStatus(
        job_id=job_id,
        user_id=request.user_id,
        state=OnboardingState.PENDING,
        message="Onboarding job queued. Pulling trade history...",
    )

    # Store job state (in-memory for dev, Redis in prod)
    store[job_id] = job_status.model_dump()

    # Fire background task
    background_tasks.add_task(
        _run_onboarding,
        job_id=job_id,
        request=request,
        store=store,
    )

    return job_status


@router.get(
    "/onboard/{job_id}",
    response_model=OnboardingStatus,
    summary="Check onboarding status",
)
async def check_onboarding(
    job_id: str,
    store: dict[str, dict[str, object]] = Depends(get_onboarding_store),
) -> OnboardingStatus:
    """Poll for async onboarding job status."""
    job_data = store.get(job_id)
    if job_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Onboarding job {job_id} not found.",
        )
    return OnboardingStatus(**job_data)


# =============================================================================
# GET /v1/user/{user_id}/profile — User baseline summary
# =============================================================================

@router.get(
    "/user/{user_id}/profile",
    response_model=UserBaseline,
    summary="Get user baseline profile",
)
async def get_user_profile(user_id: str) -> UserBaseline:
    """
    Returns the user's baseline configuration.
    In production, this reads from PostgreSQL.
    """
    # TODO: Replace with PG query
    # For now, return a default profile
    return UserBaseline(
        user_id=user_id,
        trade_count=0,
        is_baseline_ready=False,
    )


# =============================================================================
# BACKGROUND TASK: Onboarding Pipeline
# =============================================================================

async def _run_onboarding(
    job_id: str,
    request: OnboardingRequest,
    store: dict[str, dict[str, object]],
) -> None:
    """
    Async onboarding pipeline:
      1. Pull trade history from broker (simulated)
      2. Engineer features
      3. Train per-user SentinelBrain
      4. Serialize model → local (S3 in prod)
      5. Update job status
    """
    try:
        # --- Step 1: Pull history ---
        _update_job(store, job_id, OnboardingState.PULLING_HISTORY, "Pulling trade history...")
        # TODO: Real broker API integration (MT5 history pull)
        await asyncio.sleep(1)  # Simulate broker latency

        # --- Step 2/3: Train ---
        _update_job(store, job_id, OnboardingState.TRAINING, "Training baseline model...")
        # TODO: Use real trade data from broker
        # For now, simulate with bundled CSV
        await asyncio.sleep(2)  # Simulate training time

        # --- Step 4: Store model ---
        model_s3_key = f"models/{request.user_id}/brain_v5.joblib"
        # TODO: Upload to S3 via model_store.py

        # --- Step 5: Complete ---
        store[job_id].update({
            "state": OnboardingState.READY.value,
            "message": "Baseline ready. AIRO intervention activated.",
            "trade_count": request.min_trades,
            "model_s3_key": model_s3_key,
            "completed_at": datetime.utcnow().isoformat(),
        })
        logger.info("Onboarding complete for user %s (job %s)", request.user_id, job_id)

    except Exception as exc:
        logger.error("Onboarding failed for job %s: %s", job_id, exc, exc_info=True)
        store[job_id].update({
            "state": OnboardingState.FAILED.value,
            "message": f"Onboarding failed: {exc}",
        })


def _update_job(
    store: dict[str, dict[str, object]],
    job_id: str,
    state: OnboardingState,
    message: str,
) -> None:
    """Update job state in the store."""
    if job_id in store:
        store[job_id]["state"] = state.value
        store[job_id]["message"] = message
