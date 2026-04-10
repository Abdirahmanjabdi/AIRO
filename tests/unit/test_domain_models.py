"""
Unit Tests — Domain Models
===========================
Validates that Pydantic models accept/reject correct inputs.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sentinel.domain.models import (
    CredentialRequest,
    Decision,
    FeatureContribution,
    HealthResponse,
    Intervention,
    OnboardingRequest,
    OnboardingState,
    OnboardingStatus,
    RiskAssessment,
    RiskMode,
    TradeContext,
    UserBaseline,
)


class TestTradeContext:
    """Tests for the TradeContext input model."""

    def test_valid_trade_context(self) -> None:
        ctx = TradeContext(
            user_id="user-123",
            hour_decimal=14.5,
            losing_streak=2,
            drawdown_state=100.0,
            lot_deviation=0.5,
            revenge_timer=30.0,
            lots=1.0,
            rr_ratio=2.0,
            realized_vol_20=0.01,
            trend_momentum=0.005,
        )
        assert ctx.hour_decimal == 14.5
        assert ctx.losing_streak == 2
        assert ctx.lots == 1.0

    def test_context_defaults(self) -> None:
        """V2 features should default to 0.0."""
        ctx = TradeContext(
            user_id="user-123",
            hour_decimal=9.0,
            losing_streak=0,
            drawdown_state=0.0,
            lot_deviation=0.0,
            revenge_timer=9999.0,
            lots=0.1,
            rr_ratio=1.5,
        )
        assert ctx.realized_vol_20 == 0.0
        assert ctx.trend_momentum == 0.0

    def test_invalid_hour(self) -> None:
        with pytest.raises(ValidationError):
            TradeContext(
                user_id="user-123",
                hour_decimal=25.0,  # Invalid
                losing_streak=0,
                drawdown_state=0.0,
                lot_deviation=0.0,
                revenge_timer=60.0,
                lots=1.0,
                rr_ratio=2.0,
            )

    def test_negative_lots(self) -> None:
        with pytest.raises(ValidationError):
            TradeContext(
                user_id="user-123",
                hour_decimal=10.0,
                losing_streak=0,
                drawdown_state=0.0,
                lot_deviation=0.0,
                revenge_timer=60.0,
                lots=-1.0,  # Invalid
                rr_ratio=2.0,
            )

    def test_negative_losing_streak(self) -> None:
        with pytest.raises(ValidationError):
            TradeContext(
                user_id="user-123",
                hour_decimal=10.0,
                losing_streak=-1,  # Invalid
                drawdown_state=0.0,
                lot_deviation=0.0,
                revenge_timer=60.0,
                lots=1.0,
                rr_ratio=2.0,
            )


class TestRiskAssessment:
    """Tests for the RiskAssessment output model."""

    def test_valid_assessment(self) -> None:
        assessment = RiskAssessment(
            decision=Decision.ALLOW,
            risk_score=0.3,
            is_anomaly=False,
            size_multiplier=0.85,
            explanation=[
                FeatureContribution(feature="Losing_Streak", impact=0.15),
            ],
            latency_ms=4.2,
        )
        assert assessment.decision == Decision.ALLOW
        assert assessment.mode == RiskMode.NORMAL

    def test_risk_score_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RiskAssessment(
                decision=Decision.BLOCK,
                risk_score=1.5,  # Invalid: > 1.0
                is_anomaly=True,
                size_multiplier=0.0,
                latency_ms=1.0,
            )


class TestUserBaseline:
    """Tests for the UserBaseline model."""

    def test_valid_baseline(self) -> None:
        baseline = UserBaseline(
            user_id="user-123",
            trade_count=100,
            model_s3_key="models/user-123/brain_v5.joblib",
            is_baseline_ready=True,
            risk_threshold=0.6537,
        )
        assert baseline.is_baseline_ready is True
        assert baseline.model_s3_key is not None

    def test_baseline_not_ready_without_trades(self) -> None:
        with pytest.raises(ValidationError):
            UserBaseline(
                user_id="user-456",
                trade_count=10,  # < 50
                is_baseline_ready=True,  # Invalid
            )

    def test_baseline_pending(self) -> None:
        baseline = UserBaseline(
            user_id="user-789",
            trade_count=30,
            is_baseline_ready=False,
        )
        assert baseline.is_baseline_ready is False
        assert baseline.model_s3_key is None


class TestOnboardingStatus:
    """Tests for the async onboarding model."""

    def test_default_state(self) -> None:
        status = OnboardingStatus(user_id="user-123")
        assert status.state == OnboardingState.PENDING
        assert status.job_id  # UUID auto-generated
        assert status.completed_at is None

    def test_onboarding_request_min_trades(self) -> None:
        with pytest.raises(ValidationError):
            OnboardingRequest(
                user_id="user-123",
                broker_server="ICMarkets-Demo",
                account_id="12345678",
                min_trades=10,  # Invalid: < 50
            )


class TestCredentialRequest:
    def test_valid_credential_request(self) -> None:
        request = CredentialRequest(
            user_id="user-123",
            broker_server="ICMarkets-Demo",
            account_id="12345678",
            read_only_password="secret",
        )
        assert request.user_id == "user-123"


class TestIntervention:
    """Tests for the audit trail model."""

    def test_valid_intervention(self) -> None:
        iv = Intervention(
            user_id="user-123",
            symbol="EURUSD",
            decision=Decision.REDUCE_SIZE,
            risk_score=0.72,
            size_multiplier=0.3,
            original_pnl=-50.0,
            adjusted_pnl=-15.0,
            capital_saved=-35.0,
            top_reason="Losing_Streak (+0.28)",
        )
        assert iv.capital_saved == -35.0

    def test_capital_saved_consistency(self) -> None:
        with pytest.raises(ValidationError):
            Intervention(
                user_id="user-123",
                symbol="EURUSD",
                decision=Decision.BLOCK,
                risk_score=0.9,
                size_multiplier=0.0,
                original_pnl=-100.0,
                adjusted_pnl=0.0,
                capital_saved=-50.0,  # Should be -100.0 - 0.0 = -100.0
                top_reason="Anomaly",
            )
