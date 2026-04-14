"""
Sentinel-Zero Health Check Routes
=================================
Kubernetes liveness and readiness probes.
"""

from __future__ import annotations

from fastapi import APIRouter

from sentinel.api.dependencies import get_default_brain
from sentinel.brain.risk_engine import SentinelBrain
from sentinel.domain.models import HealthResponse, ReadinessResponse
from sentinel.infra.db import ping_db
from sentinel.infra.redis_cache import cache_manager
from sentinel.infra.vault_client import vault_manager

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Kubernetes liveness probe."""
    return HealthResponse(status="ok")


@router.get("/readyz", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    """
    Kubernetes readiness probe.
    Ready means:
      - the default model is loaded
      - Redis is reachable
      - Postgres is reachable
    """
    brain: SentinelBrain = get_default_brain()
    model_loaded = brain.is_trained
    redis_connected = await cache_manager.ping()
    db_connected = await ping_db()
    vault_required = vault_manager.require_vault_enabled()
    vault_connected = vault_manager.is_healthy()

    all_ready = model_loaded and redis_connected and db_connected and (vault_connected or not vault_required)

    details: dict[str, str] = {}
    if not model_loaded:
        details["model"] = "not_loaded"
    if not redis_connected:
        details["redis"] = "disconnected"
    if not db_connected:
        details["db"] = "disconnected"
    if vault_required and not vault_connected:
        details["vault"] = "required_but_unavailable"
    elif not vault_required and vault_manager.using_fallback():
        details["vault"] = "fallback_memory_store"

    return ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        model_loaded=model_loaded,
        redis_connected=redis_connected,
        db_connected=db_connected,
        vault_connected=vault_connected,
        vault_required=vault_required,
        details=details,
    )
