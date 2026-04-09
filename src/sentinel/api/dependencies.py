"""
Sentinel-Zero — API Dependencies (Dependency Injection)
=========================================================
Shared singletons and factories for route handlers.

Ref: AI_CONTRACT.md §1.4 — Logic in services, not route handlers.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd

from sentinel.brain.feature_engine import engineer_features
from sentinel.brain.risk_engine import SentinelBrain

logger = logging.getLogger(__name__)

# =============================================================================
# SINGLETON: Default SentinelBrain
# =============================================================================

_default_brain: SentinelBrain | None = None
_onboarding_jobs: dict[str, dict[str, object]] = {}


def load_default_model() -> None:
    """
    Load or train the default SentinelBrain on startup.
    Uses the bundled CSV for bootstrap; in production, each user
    gets a per-user model from S3.
    """
    global _default_brain

    model_path = Path(os.getenv(
        "SENTINEL_MODEL_PATH",
        str(Path(__file__).resolve().parents[3] / "default_model.joblib"),
    ))

    if model_path.exists():
        logger.info("Loading pre-trained model from %s", model_path)
        _default_brain = SentinelBrain.load(model_path)
        return

    # Fallback: train on bundled CSV
    csv_path = Path(__file__).resolve().parents[3] / "Abdirahman Jama Abdi - REmodal.csv"
    if not csv_path.exists():
        logger.warning("No CSV found at %s — starting with untrained brain.", csv_path)
        _default_brain = SentinelBrain()
        return

    logger.info("Training default model from %s ...", csv_path)
    df = pd.read_csv(csv_path)
    df = engineer_features(df)
    _default_brain = SentinelBrain()
    _default_brain.train(df)

    # Cache the trained model for next startup
    _default_brain.save(model_path)
    logger.info("Default model trained and cached at %s", model_path)


def get_brain() -> SentinelBrain:
    """FastAPI dependency — returns the loaded SentinelBrain singleton."""
    if _default_brain is None:
        raise RuntimeError("SentinelBrain not initialized. Check startup logs.")
    return _default_brain


def get_onboarding_store() -> dict[str, dict[str, object]]:
    """In-memory onboarding job store. Redis-backed in production."""
    return _onboarding_jobs
