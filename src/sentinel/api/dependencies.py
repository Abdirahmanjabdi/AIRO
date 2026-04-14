"""
Sentinel-Zero API Dependencies
==============================
Shared runtime services and model-loading helpers.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from sentinel.brain.feature_engine import engineer_features
from sentinel.brain.risk_engine import SentinelBrain
from sentinel.infra.db import AsyncSessionLocal, get_user, init_db
from sentinel.infra.redis_cache import cache_manager
from sentinel.infra.s3 import model_store

logger = logging.getLogger(__name__)

_default_brain: SentinelBrain | None = None
_user_brain_cache: dict[str, tuple[str, SentinelBrain]] = {}


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
    try:
        await init_db()
    except Exception:
        logger.exception("Database initialization failed")

    asyncio.create_task(_ensure_model_store_background())

    load_default_model()
    try:
        await cache_manager.ping()
    except Exception:
        logger.exception("Redis connectivity check failed during startup")


async def shutdown_runtime() -> None:
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
