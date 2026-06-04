"""
Sentinel-Zero Brain API — FastAPI Application
===============================================
Production ASGI app for the stateless risk assessment service.

Ref: ARCHITECTURE.md §2, AI_CONTRACT.md §1.2

Startup:
  uvicorn sentinel.api.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel.api.dependencies import initialize_runtime, require_api_key, shutdown_runtime
from sentinel.api.middleware import RequestIdMiddleware
from sentinel.api.routes.analysis import router as analysis_router
from sentinel.api.routes.health import router as health_router

logger = logging.getLogger(__name__)


def _production_mode_enabled() -> bool:
    return os.getenv("SENTINEL_ENV", os.getenv("ENVIRONMENT", "dev")).strip().lower() in {
        "prod",
        "production",
    }


def _configured_docs_url() -> str | None:
    if os.getenv("SENTINEL_ENABLE_DOCS", "false").strip().lower() in {"1", "true", "yes", "on"}:
        return "/docs"
    return None


def _configured_redoc_url() -> str | None:
    if os.getenv("SENTINEL_ENABLE_DOCS", "false").strip().lower() in {"1", "true", "yes", "on"}:
        return "/redoc"
    return None


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if _production_mode_enabled() and (not origins or "*" in origins):
        raise RuntimeError("CORS_ORIGINS must be explicitly set in production.")
    return origins or ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    - Startup: Initialize runtime services and load the default model.
    - Shutdown: Cleanup resources.
    """
    logger.info("Sentinel Brain API starting up...")
    await initialize_runtime()
    logger.info("Sentinel Brain API ready.")
    yield
    await shutdown_runtime()
    logger.info("Sentinel Brain API shutting down.")


app = FastAPI(
    title="Sentinel AIRO — Brain API",
    description=(
        "Behavioral governance layer for traders. Stateless risk assessment with sub-50ms latency."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=_configured_docs_url(),
    redoc_url=_configured_redoc_url(),
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Custom Middleware ---
app.add_middleware(RequestIdMiddleware)

# --- Routes ---
app.include_router(health_router, tags=["Health"])
app.include_router(
    analysis_router,
    prefix="/v1",
    tags=["Analysis"],
    dependencies=[Depends(require_api_key)],
)
