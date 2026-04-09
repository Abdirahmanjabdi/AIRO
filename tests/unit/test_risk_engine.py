"""
Unit Tests — Risk Engine (SentinelBrain)
==========================================
Tests prediction, circuit breaker, and serialization.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from sentinel.brain.feature_engine import engineer_features
from sentinel.brain.risk_engine import SentinelBrain
from sentinel.domain.models import Decision, RiskMode, TradeContext


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Minimal training dataset."""
    df = pd.DataFrame({
        "Open Time": pd.to_datetime(
            [f"2024-01-{d:02d} 10:00" for d in range(1, 31)]
        ),
        "Close Time": pd.to_datetime(
            [f"2024-01-{d:02d} 10:30" for d in range(1, 31)]
        ),
        "PnL": [100, -50, 75, -30, 200, -100, 50, -20, 150, -80] * 3,
        "Lots": [1.0, 1.0, 1.5, 2.0, 1.0, 1.0, 0.5, 1.0, 1.0, 3.0] * 3,
        "Open Price": [1.1 + i * 0.001 for i in range(30)],
        "Close Price": [1.1 + i * 0.001 + 0.002 for i in range(30)],
        "RR Ratio": [2.0] * 30,
        "Gain": ["1%"] * 30,
        "Symbol": ["EURUSD"] * 30,
    })
    return engineer_features(df)


@pytest.fixture
def trained_brain(sample_df: pd.DataFrame) -> SentinelBrain:
    """A brain trained on the sample dataset."""
    brain = SentinelBrain()
    brain.train(sample_df)
    return brain


@pytest.fixture
def sample_context() -> TradeContext:
    """A typical trade context for testing."""
    return TradeContext(
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


class TestSentinelBrainPrediction:
    """Test core prediction functionality."""

    def test_prediction_returns_assessment(
        self,
        trained_brain: SentinelBrain,
        sample_context: TradeContext,
    ) -> None:
        result = trained_brain.assess_risk(sample_context)
        assert result.decision in (Decision.ALLOW, Decision.BLOCK, Decision.REDUCE_SIZE)
        assert 0.0 <= result.risk_score <= 1.0
        assert 0.0 <= result.size_multiplier <= 1.0
        assert result.latency_ms > 0
        assert result.mode == RiskMode.NORMAL

    def test_prediction_has_explanation(
        self,
        trained_brain: SentinelBrain,
        sample_context: TradeContext,
    ) -> None:
        result = trained_brain.assess_risk(sample_context)
        # SHAP should return top-3 features
        assert len(result.explanation) <= 3

    def test_untrained_brain_returns_risk_off(
        self,
        sample_context: TradeContext,
    ) -> None:
        brain = SentinelBrain()
        result = brain.assess_risk(sample_context)
        assert result.decision == Decision.BLOCK
        assert result.mode == RiskMode.BASELINE_PENDING
        assert result.size_multiplier == 0.0


class TestCircuitBreaker:
    """Test circuit breaker behavior."""

    def test_circuit_opens_after_threshold(self) -> None:
        brain = SentinelBrain(circuit_breaker_threshold=3)
        brain._is_trained = True

        # Simulate 3 failures
        for _ in range(3):
            brain._record_failure()

        assert brain.is_circuit_open is True

    def test_circuit_reset(self) -> None:
        brain = SentinelBrain(circuit_breaker_threshold=3)
        for _ in range(3):
            brain._record_failure()
        assert brain.is_circuit_open is True

        brain.reset_circuit_breaker()
        assert brain.is_circuit_open is False

    def test_circuit_open_returns_risk_off(
        self,
        sample_context: TradeContext,
    ) -> None:
        brain = SentinelBrain(circuit_breaker_threshold=1)
        brain._is_trained = True
        brain._record_failure()  # Open circuit

        result = brain.assess_risk(sample_context)
        assert result.decision == Decision.BLOCK
        assert result.mode == RiskMode.RISK_OFF


class TestSerialization:
    """Test model save/load via joblib."""

    def test_save_and_load(
        self,
        trained_brain: SentinelBrain,
        sample_context: TradeContext,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "brain.joblib"

            # Save
            trained_brain.save(path)
            assert path.exists()

            # Load
            loaded = SentinelBrain.load(path)
            assert loaded.is_trained is True

            # Predictions should match
            r1 = trained_brain.assess_risk(sample_context)
            r2 = loaded.assess_risk(sample_context)
            assert r1.risk_score == r2.risk_score
            assert r1.decision == r2.decision

    def test_save_untrained_raises(self) -> None:
        brain = SentinelBrain()
        with pytest.raises(RuntimeError, match="Cannot save untrained"):
            brain.save(Path("/tmp/should_not_exist.joblib"))
