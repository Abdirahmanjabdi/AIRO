"""
Sentinel-Zero Domain Models
============================
Pydantic models defining the contracts used by the frontend, API,
bridge, and persistence boundaries.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Decision(str, Enum):
    """Risk engine output decision."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REDUCE_SIZE = "REDUCE_SIZE"


class OnboardingState(str, Enum):
    """Async onboarding job lifecycle."""

    PENDING = "pending"
    PULLING_HISTORY = "pulling_history"
    TRAINING = "training"
    BLANK_BASELINE = "blank_baseline"
    READY = "ready"
    FAILED = "failed"


class RiskMode(str, Enum):
    """Brain operating mode for audit trail and UI state."""

    NORMAL = "normal"
    RISK_OFF = "risk_off"
    BASELINE_PENDING = "baseline_pending"
    SHADOW = "shadow"
    BOOTSTRAP = "bootstrap"


class UserMaturity(str, Enum):
    """Cold-start maturity lane for a user's behavioral model."""

    MATURITY_0 = "maturity_0"
    MATURITY_1 = "maturity_1"
    MATURITY_2 = "maturity_2"


class TradingStyle(str, Enum):
    """Self-declared trading cadence captured during onboarding."""

    SCALPER = "scalper"
    INTRADAY = "intraday"
    SWING = "swing"


class TiltResponse(str, Enum):
    """Self-declared behavior after a loss."""

    WAIT_FOR_SETUP = "wait_for_setup"
    MIXED = "mixed"
    IMMEDIATE_REENTRY = "immediate_reentry"


class UserInitialParameters(BaseModel):
    """Risk DNA survey values used before enough trade history exists."""

    max_drawdown_pct: float = Field(default=3.0, ge=0.1, le=25.0)
    primary_instrument: str = Field(default="FX", min_length=1, max_length=32)
    trading_style: TradingStyle = Field(default=TradingStyle.INTRADAY)
    typical_daily_trades: int = Field(default=8, ge=1, le=500)
    typical_lot_size: float = Field(default=1.0, gt=0.0, le=500.0)
    average_win_hold_minutes: float = Field(default=60.0, gt=0.0, le=10080.0)
    tilt_response: TiltResponse = Field(default=TiltResponse.WAIT_FOR_SETUP)
    loss_review_threshold: int = Field(default=3, ge=1, le=20)
    max_lot_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)

    @field_validator("primary_instrument")
    @classmethod
    def normalize_instrument(cls, value: str) -> str:
        return value.strip().upper()


class TradeContext(BaseModel):
    """
    Trade telemetry sent from the Sentinel Pod bridge to the Brain API.
    """

    user_id: str = Field(..., min_length=1, description="Unique Sentinel user identifier")
    symbol: str = Field(default="UNKNOWN", min_length=1, description="Trading instrument")
    hour_decimal: float = Field(..., ge=0.0, le=23.99)
    losing_streak: int = Field(..., ge=0)
    drawdown_state: float = Field(..., ge=0.0)
    lot_deviation: float
    revenge_timer: float = Field(..., ge=0.0)
    lots: float = Field(..., gt=0.0)
    rr_ratio: float = Field(..., gt=0.0)
    realized_vol_20: float = Field(default=0.0, ge=0.0)
    trend_momentum: float = Field(default=0.0, ge=0.0)

    @field_validator("hour_decimal")
    @classmethod
    def validate_hour_range(cls, value: float) -> float:
        if not 0.0 <= value <= 23.99:
            raise ValueError(f"hour_decimal must be 0.0-23.99, got {value}")
        return round(value, 2)


class FeatureContribution(BaseModel):
    """Single SHAP explanation entry."""

    feature: str
    impact: float


class RiskAssessment(BaseModel):
    """Brain API response for POST /v1/analyze."""

    decision: Decision
    risk_score: float = Field(..., ge=0.0, le=1.0)
    is_anomaly: bool
    size_multiplier: float = Field(..., ge=0.0, le=1.0)
    explanation: list[FeatureContribution] = Field(default_factory=list)
    latency_ms: float = Field(..., ge=0.0)
    mode: RiskMode = Field(default=RiskMode.NORMAL)
    maturity_state: UserMaturity | None = None
    shadow_mode: bool = False


class UserBaseline(BaseModel):
    """Per-user model metadata returned to the frontend/API."""

    user_id: str
    broker_server: str | None = None
    account_id: str | None = None
    trade_count: int = Field(..., ge=0)
    model_s3_key: str | None = None
    trained_at: datetime | None = None
    is_baseline_ready: bool = False
    risk_threshold: float = 0.6537
    contamination: float = 0.0399
    maturity_state: UserMaturity = UserMaturity.MATURITY_0
    enforce_mode: bool = False
    initial_parameters: UserInitialParameters = Field(default_factory=UserInitialParameters)

    @field_validator("is_baseline_ready")
    @classmethod
    def validate_baseline(cls, value: bool, info: object) -> bool:
        data = getattr(info, "data", {})
        trade_count = data.get("trade_count", 0)
        if value and trade_count < 1:
            raise ValueError(
                f"Cannot be baseline_ready with only {trade_count} trades"
            )
        return value


class OnboardingRequest(BaseModel):
    """Public onboarding request body."""

    user_id: str = Field(..., min_length=1)
    broker_server: str = Field(..., min_length=1)
    account_id: str = Field(..., min_length=1)
    min_trades: int = Field(default=20, ge=1, le=500)
    initial_parameters: UserInitialParameters = Field(default_factory=UserInitialParameters)


class CredentialRequest(BaseModel):
    """Secure broker credential submission stored in Vault."""

    user_id: str = Field(..., min_length=1)
    broker_server: str = Field(..., min_length=1)
    account_id: str = Field(..., min_length=1)
    read_only_password: str = Field(..., min_length=1)


class CredentialResponse(BaseModel):
    """Response after secure credential storage."""

    user_id: str
    stored: bool
    vault_path: str


class WhopWebhookRequest(BaseModel):
    """Lifecycle webhook payload from Whop."""

    event: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    plan: str = Field(..., min_length=1)


class WhopWebhookResponse(BaseModel):
    """Provisioning response generated from a Whop event."""

    user_id: str
    api_key: str
    api_key_last4: str
    helm_release: str
    helm_command: str
    provisioning_state: str


class OnboardingStatus(BaseModel):
    """Async onboarding status response."""

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    state: OnboardingState = Field(default=OnboardingState.PENDING)
    trade_count: int = Field(default=0, ge=0)
    message: str = Field(default="Job queued")
    model_s3_key: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    api_key: str | None = None
    api_key_last4: str | None = None


class RiskAuditRecord(BaseModel):
    """Serialized risk audit entry for dashboard and analytics views."""

    audit_id: int | None = None
    user_id: str
    symbol: str
    decision: Decision
    risk_score: float = Field(..., ge=0.0, le=1.0)
    size_multiplier: float = Field(..., ge=0.0, le=1.0)
    mode: RiskMode = Field(default=RiskMode.NORMAL)
    is_anomaly: bool = False
    top_reason: str | None = None
    explanation: list[FeatureContribution] = Field(default_factory=list)
    latency_ms: float = Field(..., ge=0.0)
    cached: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WorkspaceSummary(BaseModel):
    """User-focused dashboard snapshot assembled from profile and audits."""

    user_id: str
    profile: UserBaseline
    recent_audits: list[RiskAuditRecord] = Field(default_factory=list)
    latest_assessment: RiskAuditRecord | None = None
    decision_counts: dict[str, int] = Field(default_factory=dict)
    average_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    average_latency_ms: float = Field(default=0.0, ge=0.0)
    protection_events: int = Field(default=0, ge=0)
    blank_baseline: bool = False


class AdminUserRecord(BaseModel):
    """Admin control-plane row for a single provisioned trader."""

    user_id: str
    broker_server: str | None = None
    account_id: str | None = None
    email: str | None = None
    plan: str | None = None
    provisioning_state: str | None = None
    helm_release: str | None = None
    trade_count: int = Field(default=0, ge=0)
    is_baseline_ready: bool = False
    model_s3_key: str | None = None
    trained_at: datetime | None = None
    latest_risk_score: float | None = Field(default=None, ge=0.0, le=1.0)
    latest_decision: Decision | None = None
    latest_mode: RiskMode | None = None
    last_audit_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HistoricalTrade(BaseModel):
    """Normalized historical trade sent by the MT5 bridge."""

    symbol: str = Field(..., min_length=1)
    open_time: datetime
    close_time: datetime
    pnl: float
    lots: float = Field(..., gt=0.0)
    open_price: float = Field(..., gt=0.0)
    close_price: float = Field(..., gt=0.0)
    rr_ratio: float = Field(default=1.0, gt=0.0)


class OnboardingDataSubmission(BaseModel):
    """Historical trade payload posted back by the MT5 bridge."""

    job_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    trades: list[HistoricalTrade] = Field(..., max_length=500)


class Intervention(BaseModel):
    """Audit log entry for a live intervention event."""

    intervention_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    symbol: str
    decision: Decision
    risk_score: float = Field(..., ge=0.0, le=1.0)
    size_multiplier: float = Field(..., ge=0.0, le=1.0)
    original_pnl: float
    adjusted_pnl: float
    capital_saved: float
    top_reason: str

    @field_validator("capital_saved")
    @classmethod
    def validate_capital_saved(cls, value: float, info: object) -> float:
        data = getattr(info, "data", {})
        original = data.get("original_pnl", 0.0)
        adjusted = data.get("adjusted_pnl", 0.0)
        expected = original - adjusted
        if abs(value - expected) > 0.01:
            raise ValueError(
                f"capital_saved ({value}) != original_pnl ({original}) - "
                f"adjusted_pnl ({adjusted}) = {expected}"
            )
        return value


class HealthResponse(BaseModel):
    """GET /healthz response."""

    status: Literal["ok", "degraded", "down"]
    version: str = Field(default="1.0.0")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReadinessResponse(BaseModel):
    """GET /readyz response."""

    status: Literal["ready", "not_ready"]
    model_loaded: bool = False
    redis_connected: bool = False
    db_connected: bool = False
    vault_connected: bool = False
    vault_required: bool = False
    details: dict[str, str] = Field(default_factory=dict)


class AdminOverview(BaseModel):
    """Aggregated fleet-level view for the admin dashboard."""

    total_users: int = Field(default=0, ge=0)
    baseline_ready_users: int = Field(default=0, ge=0)
    active_api_credentials: int = Field(default=0, ge=0)
    total_audits: int = Field(default=0, ge=0)
    blocked_decisions: int = Field(default=0, ge=0)
    reduced_decisions: int = Field(default=0, ge=0)
    average_risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    users: list[AdminUserRecord] = Field(default_factory=list)
    recent_jobs: list[OnboardingStatus] = Field(default_factory=list)
