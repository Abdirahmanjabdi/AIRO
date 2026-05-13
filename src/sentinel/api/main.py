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
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinel.api.dependencies import initialize_runtime, require_api_key, shutdown_runtime
from sentinel.api.middleware import RequestIdMiddleware
from sentinel.api.routes.analysis import router as analysis_router
from sentinel.api.routes.health import router as health_router

logger = logging.getLogger(__name__)


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
        "Behavioral governance layer for traders. "
        "Stateless risk assessment with sub-50ms latency."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
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
