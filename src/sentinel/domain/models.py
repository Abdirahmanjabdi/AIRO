"""
Sentinel-Zero Domain Models
============================
Pydantic models defining the data contracts for the entire system.
Referenced by: ARCHITECTURE.md §4, AI_CONTRACT.md §4

Rules:
  - No `Any` types (AI_CONTRACT §1.1)
  - All API boundaries use these models
  - V5 logic NEVER references bridge-side code (AI_CONTRACT §3)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# ENUMS
# =============================================================================

class Decision(str, Enum):
    """Risk engine output decision. Maps to MT5 bridge actions."""
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REDUCE_SIZE = "REDUCE_SIZE"


class OnboardingState(str, Enum):
    """Async onboarding job lifecycle (FP: never synchronous)."""
    PENDING = "pending"
    PULLING_HISTORY = "pulling_history"
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"


class RiskMode(str, Enum):
    """Brain operating mode for audit trail."""
    NORMAL = "normal"
    RISK_OFF = "risk_off"          # Circuit-breaker tripped
    BASELINE_PENDING = "baseline_pending"  # < 50 trades


# =============================================================================
# INPUT MODELS
# =============================================================================

class TradeContext(BaseModel):
    """
    Trade telemetry sent from the Sentinel Pod bridge to the Brain API.
    9 features: 7 behavioral + 2 context (V2).

    Ref: ARCHITECTURE.md §3.2
    """
    # --- Behavioral Features (V1) ---
    hour_decimal: float = Field(
        ..., ge=0.0, le=23.99,
        description="Trading hour as decimal (14:30 → 14.5)",
    )
    losing_streak: int = Field(
        ..., ge=0,
        description="Consecutive losses count",
    )
    drawdown_state: float = Field(
        ..., ge=0.0,
        description="Distance from equity high-water mark ($)",
    )
    lot_deviation: float = Field(
        ...,
        description="Z-score of current lot size vs 20-trade rolling mean",
    )
    revenge_timer: float = Field(
        ..., ge=0.0,
        description="Minutes since previous trade closed",
    )
    lots: float = Field(
        ..., gt=0.0,
        description="Position size in lots",
    )
    rr_ratio: float = Field(
        ..., gt=0.0,
        description="Risk-Reward ratio",
    )

    # --- Context Features (V2) ---
    realized_vol_20: float = Field(
        default=0.0, ge=0.0,
        description="20-trade rolling volatility of trade ranges",
    )
    trend_momentum: float = Field(
        default=0.0, ge=0.0,
        description="Absolute 20-trade rolling mean of price changes",
    )

    @field_validator("hour_decimal")
    @classmethod
    def validate_hour_range(cls, v: float) -> float:
        if not 0.0 <= v <= 23.99:
            raise ValueError(f"hour_decimal must be 0.0-23.99, got {v}")
        return round(v, 2)


# =============================================================================
# OUTPUT MODELS
# =============================================================================

class FeatureContribution(BaseModel):
    """Single SHAP explanation entry."""
    feature: str = Field(..., description="Feature name")
    impact: float = Field(..., description="SHAP value (+/- contribution)")


class RiskAssessment(BaseModel):
    """
    Brain API response for POST /v1/analyze.
    Contains the intervention decision and explainability data.

    Ref: AI_CONTRACT.md §4.2
    """
    decision: Decision
    risk_score: float = Field(..., ge=0.0, le=1.0)
    is_anomaly: bool
    size_multiplier: float = Field(..., ge=0.0, le=1.0)
    explanation: list[FeatureContribution] = Field(
        default_factory=list,
        description="Top-3 SHAP feature contributions",
    )
    latency_ms: float = Field(
        ..., ge=0.0,
        description="End-to-end inference latency in milliseconds",
    )
    mode: RiskMode = Field(
        default=RiskMode.NORMAL,
        description="Current brain operating mode",
    )


# =============================================================================
# USER & ONBOARDING MODELS
# =============================================================================

class UserBaseline(BaseModel):
    """
    Per-user model metadata. Weights stored in S3, not PG.

    Ref: ARCHITECTURE.md §4.3 (FP adjustment #3)
    """
    user_id: str = Field(..., description="Unique user identifier")
    trade_count: int = Field(..., ge=0)
    model_s3_key: str | None = Field(
        default=None,
        description="S3 object key for the .joblib model file",
    )
    trained_at: datetime | None = Field(
        default=None,
        description="Timestamp of last model training",
    )
    is_baseline_ready: bool = Field(
        default=False,
        description="True when trade_count >= 50 and model is trained",
    )
    risk_threshold: float = Field(
        default=0.6537,
        description="Bayesian-optimized risk threshold for this user",
    )
    contamination: float = Field(
        default=0.0399,
        description="Isolation Forest contamination parameter",
    )

    @field_validator("is_baseline_ready")
    @classmethod
    def validate_baseline(cls, v: bool, info: object) -> bool:
        """Baseline cannot be ready if trade_count < 50."""
        # Access other field values through info.data
        data = getattr(info, "data", {})
        trade_count = data.get("trade_count", 0)
        if v and trade_count < 50:
            raise ValueError(
                f"Cannot be baseline_ready with only {trade_count} trades (min 50)"
            )
        return v


class OnboardingRequest(BaseModel):
    """POST /v1/onboard request body."""
    user_id: str = Field(..., min_length=1)
    broker_server: str = Field(..., description="MT5 broker server name")
    account_id: str = Field(..., description="MT5 account number")
    # Credentials are NOT passed here — they go through Vault
    min_trades: int = Field(default=50, ge=50, le=500)


class OnboardingStatus(BaseModel):
    """
    GET /v1/onboard/{job_id} response.
    Async pattern: POST returns 202 + job_id, client polls this.

    Ref: FP adjustment #2
    """
    job_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique async job identifier",
    )
    user_id: str
    state: OnboardingState = Field(default=OnboardingState.PENDING)
    trade_count: int = Field(default=0, ge=0)
    message: str = Field(default="Job queued")
    model_s3_key: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)


# =============================================================================
# AUDIT MODELS
# =============================================================================

class Intervention(BaseModel):
    """
    Audit log entry for every intervention event.
    Stored in PostgreSQL for compliance and ROM reporting.
    """
    intervention_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    symbol: str = Field(..., description="Trading instrument (e.g. EURUSD)")
    decision: Decision
    risk_score: float = Field(..., ge=0.0, le=1.0)
    size_multiplier: float = Field(..., ge=0.0, le=1.0)
    original_pnl: float = Field(
        ..., description="PnL if trade executed at full size",
    )
    adjusted_pnl: float = Field(
        ..., description="PnL after AIRO intervention",
    )
    capital_saved: float = Field(
        ..., description="original_pnl - adjusted_pnl (positive = saved)",
    )
    top_reason: str = Field(
        ..., description="Primary SHAP feature driving the decision",
    )

    @field_validator("capital_saved")
    @classmethod
    def validate_capital_saved(cls, v: float, info: object) -> float:
        """Capital saved should be consistent with PnL values."""
        data = getattr(info, "data", {})
        original = data.get("original_pnl", 0.0)
        adjusted = data.get("adjusted_pnl", 0.0)
        expected = original - adjusted
        if abs(v - expected) > 0.01:
            raise ValueError(
                f"capital_saved ({v}) != original_pnl ({original}) - "
                f"adjusted_pnl ({adjusted}) = {expected}"
            )
        return v


# =============================================================================
# HEALTH CHECK MODELS
# =============================================================================

class HealthResponse(BaseModel):
    """GET /healthz response."""
    status: Literal["ok", "degraded", "down"]
    version: str = Field(default="1.0.0")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReadinessResponse(BaseModel):
    """GET /readyz response."""
    status: Literal["ready", "not_ready"]
    model_loaded: bool = Field(default=False)
    redis_connected: bool = Field(default=False)
    db_connected: bool = Field(default=False)
    details: dict[str, str] = Field(default_factory=dict)
