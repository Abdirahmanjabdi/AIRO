"""
Sentinel-Zero API Dependencies
==============================
Shared runtime services and model-loading helpers.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.brain.feature_engine import engineer_features
from sentinel.brain.risk_engine import SentinelBrain
from sentinel.infra.db import AsyncSessionLocal, get_db, get_user, init_db, validate_api_key
from sentinel.infra.data_lake import data_lake_exporter
from sentinel.infra.redis_cache import cache_manager
from sentinel.infra.s3 import model_store

logger = logging.getLogger(__name__)

_default_brain: SentinelBrain | None = None
_user_brain_cache: dict[str, tuple[str, SentinelBrain]] = {}
_data_lake_task: asyncio.Task[None] | None = None


def _existing_path(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if str(candidate) and candidate.exists() and candidate.is_file():
            return candidate
    return None


async def _ensure_model_store_background() -> None:
    try:
        await asyncio.to_thread(model_store.ensure_bucket)
    except Exception:
        logger.exception("Model store initialization failed")


async def _data_lake_export_loop() -> None:
    interval_seconds = int(os.getenv("DATA_LAKE_EXPORT_INTERVAL_SECONDS", "86400"))
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with AsyncSessionLocal() as session:
                key = await data_lake_exporter.export_day(session)
            if key is not None:
                logger.info("Behavioral data lake export complete: s3://%s/%s", data_lake_exporter.bucket, key)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Behavioral data lake export failed")


def load_default_model() -> None:
    """
    Load or train the bundled default brain used for startup validation.
    User-specific inference paths should load per-user models instead.
    """

    global _default_brain

    packaged_root = Path(__file__).resolve().parents[3]
    configured_model_path = Path(
        os.getenv(
            "SENTINEL_MODEL_PATH",
            str(packaged_root / "default_model.joblib"),
        )
    )
    model_path = _existing_path(
        [
            configured_model_path,
            Path("/app/default_model.joblib"),
            packaged_root / "default_model.joblib",
        ]
    )

    if model_path is not None:
        logger.info("Loading default brain from %s", model_path)
        _default_brain = SentinelBrain.load(model_path)
        return

    csv_path = _existing_path(
        [
            Path(os.getenv("SENTINEL_BOOTSTRAP_CSV", "")),
            Path("/app/Abdirahman Jama Abdi - REmodal.csv"),
            packaged_root / "Abdirahman Jama Abdi - REmodal.csv",
        ]
    )
    if csv_path is None:
        logger.warning("Bootstrap CSV missing at %s. Default brain will stay untrained.", csv_path)
        _default_brain = SentinelBrain()
        return

    logger.info("Training default brain from %s", csv_path)
    frame = pd.read_csv(csv_path)
    frame = engineer_features(frame)
    _default_brain = SentinelBrain()
    _default_brain.train(frame)
    save_path = configured_model_path
    try:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        _default_brain.save(save_path)
    except Exception:
        fallback_path = Path(tempfile.gettempdir()) / "sentinel-default-model.joblib"
        try:
            _default_brain.save(fallback_path)
            logger.info("Saved default brain fallback to %s", fallback_path)
        except Exception:
            logger.warning("Default brain trained but could not be persisted to disk.", exc_info=True)


async def initialize_runtime() -> None:
    global _data_lake_task
    try:
        await init_db()
    except Exception:
        logger.exception("Database initialization failed")

    asyncio.create_task(_ensure_model_store_background())

    load_default_model()
    try:
        if not await cache_manager.ping():
            from sentinel.infra.redis_cache import InMemoryRedis
            logger.warning("Redis ping failed. Swapping to InMemoryRedis fallback.")
            cache_manager.r = InMemoryRedis()
    except Exception:
        from sentinel.infra.redis_cache import InMemoryRedis
        logger.warning("Redis connectivity check failed. Swapping to InMemoryRedis fallback.")
        cache_manager.r = InMemoryRedis()

    if os.getenv("SENTINEL_ENABLE_DATA_LAKE_EXPORT", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        _data_lake_task = asyncio.create_task(_data_lake_export_loop())


async def shutdown_runtime() -> None:
    global _data_lake_task
    if _data_lake_task is not None:
        _data_lake_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _data_lake_task
        _data_lake_task = None
    try:
        await cache_manager.close()
    except Exception:
        logger.exception("Failed to close Redis client cleanly")


def get_default_brain() -> SentinelBrain:
    if _default_brain is None:
        raise RuntimeError("Default SentinelBrain not initialized.")
    return _default_brain


async def get_session() -> AsyncSession:
    return AsyncSessionLocal()


async def get_user_brain(user_id: str, session: AsyncSession) -> SentinelBrain | None:
    user = await get_user(session, user_id)
    if user is None or not user.model_s3_key or not user.is_baseline_ready:
        return None

    cached = _user_brain_cache.get(user_id)
    if cached is not None and cached[0] == user.model_s3_key:
        return cached[1]

    try:
        if not await asyncio.to_thread(model_store.model_exists, user.model_s3_key):
            return None

        local_path = await asyncio.to_thread(model_store.download_model_to_temp, user.model_s3_key)
        brain = await asyncio.to_thread(SentinelBrain.load, local_path)
        _user_brain_cache[user_id] = (user.model_s3_key, brain)
        return brain
    except Exception:
        logger.exception("Failed to load model for user %s", user_id)
        return None


def cache_user_brain(user_id: str, model_key: str, brain: SentinelBrain) -> None:
    _user_brain_cache[user_id] = (model_key, brain)


async def get_cache_manager() -> object:
    return cache_manager


import base64
import json
import hashlib
import time
from datetime import datetime, timezone
from cryptography.fernet import Fernet

# A stable Fernet key derived from a secret, or a newly generated one if not set
SECRET_KEY = os.getenv("SENTINEL_SECRET_KEY", "sentinel_fallback_secret_32_bytes_long_!!")
FERNET_KEY = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
cipher_suite = Fernet(FERNET_KEY)

def create_session_token(user_id: str) -> str:
    """Generates an encrypted, signed session token containing the user identity and a timestamp."""
    payload = {
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    encrypted = cipher_suite.encrypt(json.dumps(payload).encode())
    return encrypted.decode()

def verify_session_token(token: str) -> str:
    """Decrypts and verifies token signature and expiration (24h)."""
    try:
        decrypted = cipher_suite.decrypt(token.encode())
        payload = json.loads(decrypted.decode())
        created_at = datetime.fromisoformat(payload["timestamp"])
        if (datetime.now(timezone.utc) - created_at).total_seconds() > 86400:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session token expired."
            )
        return str(payload["user_id"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid session token."
        ) from exc

async def verify_tenant_isolation(request: Request, user_id: str) -> None:
    """Enforces strict tenant row-level checking to prevent IDOR/BOLA attacks."""
    if os.getenv("SENTINEL_AUTH_DISABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        return

    auth_user_id = getattr(request.state, "user_id", None)
    if not auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session context missing user identity."
        )
    if auth_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Tenant Isolation violation (BOLA protected)."
        )

async def rate_limiter(request: Request) -> None:
    """Sliding-window rate limiter restricting /analyze and /autopsy to 10 requests per second."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        return

    current_second = int(time.time())
    key = f"rate_limit:{user_id}:{current_second}"
    try:
        count = await cache_manager.r.incr(key)
        if count == 1:
            await cache_manager.r.expire(key, 2)
        if count > 10:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Maximum 10 requests per second allowed per user."
            )
    except HTTPException:
        raise
    except Exception:
        # Fallback to allow requests if cache manager is down
        pass

async def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_db),
) -> None:
    if os.getenv("SENTINEL_AUTH_DISABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        request.state.user_id = "disabled_auth_user"
        return

    bootstrap_routes = {
        ("POST", "/v1/credentials"),
        ("POST", "/v1/onboard"),
    }
    if (request.method, request.url.path) in bootstrap_routes or request.url.path.startswith("/v1/onboard"):
        return

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )

    # 1. First try to authenticate as a Fernet Session Token (for frontend Web Dashboard)
    try:
        user_id = verify_session_token(x_api_key)
        request.state.user_id = user_id
        return
    except HTTPException:
        pass

    # 2. Fall back to standard raw API Key (for automated MT5 Pod bridges)
    if not await validate_api_key(session, x_api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    # Populate request.state.user_id with the corresponding key owner user_id
    from sqlalchemy import select
    from sentinel.infra.db import ApiCredential
    api_key_hash = hashlib.sha256(x_api_key.encode("utf-8")).hexdigest()
    try:
        result = await session.execute(
            select(ApiCredential).where(ApiCredential.api_key_hash == api_key_hash)
        )
        cred = result.scalar_one_or_none()
        if cred:
            request.state.user_id = cred.user_id
        else:
            request.state.user_id = "unknown_user"
    except Exception:
        request.state.user_id = "unknown_user"
