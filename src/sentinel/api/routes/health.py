"""
Sentinel-Zero — Health Check Routes
=====================================
K8s liveness and readiness probes.

GET /healthz — 200 if the process is alive
GET /readyz  — 200 if model loaded + dependencies connected

Ref: ARCHITECTURE.md §2
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from sentinel.api.dependencies import get_brain
from sentinel.brain.risk_engine import SentinelBrain
from sentinel.domain.models import HealthResponse, ReadinessResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """K8s liveness probe — always 200 if process is running."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadinessResponse)
async def readiness(
    brain: SentinelBrain = Depends(get_brain),
) -> ReadinessResponse:
    """
    K8s readiness probe — 200 only if:
      - Model is loaded and trained
      - (Future) Redis and DB are connected
    """
    model_loaded = brain.is_trained

    # TODO: Add Redis and DB connectivity checks
    redis_connected = True   # Placeholder
    db_connected = True      # Placeholder

    all_ready = model_loaded and redis_connected and db_connected

    details: dict[str, str] = {}
    if not model_loaded:
        details["model"] = "not_loaded"
    if not redis_connected:
        details["redis"] = "disconnected"
    if not db_connected:
        details["db"] = "disconnected"

    return ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        model_loaded=model_loaded,
        redis_connected=redis_connected,
        db_connected=db_connected,
        details=details,
    )
