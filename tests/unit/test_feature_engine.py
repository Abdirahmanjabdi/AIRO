"""
Unit Tests — Feature Engine
=============================
Verifies feature engineering functions produce correct outputs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sentinel.brain.feature_engine import (
    compute_drawdown_state,
    compute_hour_decimal,
    compute_is_high_risk,
    compute_losing_streak,
    compute_lot_deviation,
    compute_realized_volatility,
    compute_revenge_timer,
    compute_trend_momentum,
    engineer_features,
    FEATURE_COLUMNS_V2,
)


class TestHourDecimal:
    def test_basic(self) -> None:
        times = pd.Series(pd.to_datetime(["2024-01-01 14:30", "2024-01-01 09:00"]))
        result = compute_hour_decimal(times)
        assert result.iloc[0] == 14.5
        assert result.iloc[1] == 9.0


class TestRevengeTimer:
    def test_first_trade_default(self) -> None:
        opens = pd.Series(pd.to_datetime(["2024-01-01 10:00", "2024-01-01 10:05"]))
        closes = pd.Series(pd.to_datetime(["2024-01-01 10:02", "2024-01-01 10:10"]))
        result = compute_revenge_timer(opens, closes)
        assert result.iloc[0] == 9999.0  # First trade

    def test_revenge_timer_calculation(self) -> None:
        opens = pd.Series(pd.to_datetime(["2024-01-01 10:00", "2024-01-01 10:05"]))
        closes = pd.Series(pd.to_datetime(["2024-01-01 10:02", "2024-01-01 10:10"]))
        result = compute_revenge_timer(opens, closes)
        assert result.iloc[1] == 3.0  # 10:05 - 10:02 = 3 minutes


class TestLosingStreak:
    def test_streak_counting(self) -> None:
        pnl = pd.Series([-10, -20, 30, -5])
        result = compute_losing_streak(pnl)
        assert list(result) == [1, 2, 0, 1]

    def test_no_losses(self) -> None:
        pnl = pd.Series([10, 20, 30])
        result = compute_losing_streak(pnl)
        assert list(result) == [0, 0, 0]


class TestDrawdownState:
    def test_drawdown(self) -> None:
        pnl = pd.Series([100, -50, -50, 200])
        result = compute_drawdown_state(pnl)
        # Equity: 100, 50, 0, 200
        # Peak:   100, 100, 100, 200
        # DD:     0, 50, 100, 0
        assert list(result) == [0, 50, 100, 0]


class TestLotDeviation:
    def test_returns_series(self) -> None:
        lots = pd.Series([1.0] * 25)
        result = compute_lot_deviation(lots)
        assert len(result) == 25
        # Constant lots → deviation should be 0 (or NaN filled to 0)


class TestRealizedVolatility:
    def test_returns_non_negative(self) -> None:
        opens = pd.Series(np.random.uniform(1.0, 1.1, 30))
        closes = opens + np.random.uniform(-0.01, 0.01, 30)
        result = compute_realized_volatility(opens, closes)
        assert (result >= 0).all()


class TestTrendMomentum:
    def test_returns_non_negative(self) -> None:
        prices = pd.Series(np.linspace(1.0, 1.5, 30))
        result = compute_trend_momentum(prices)
        assert (result >= 0).all()


class TestIsHighRisk:
    def test_loss_with_bad_behavior(self) -> None:
        result = compute_is_high_risk(
            pnl=pd.Series([-100]),
            drawdown_state=pd.Series([10.0]),
            losing_streak=pd.Series([5]),
            revenge_timer=pd.Series([5.0]),
        )
        assert result.iloc[0] == 1

    def test_win_never_high_risk(self) -> None:
        result = compute_is_high_risk(
            pnl=pd.Series([100]),
            drawdown_state=pd.Series([10.0]),
            losing_streak=pd.Series([5]),
            revenge_timer=pd.Series([5.0]),
        )
        assert result.iloc[0] == 0


class TestEngineerFeatures:
    def test_full_pipeline(self) -> None:
        """Test that the full pipeline produces all expected columns."""
        df = pd.DataFrame({
            "Open Time": pd.to_datetime(
                ["2024-01-01 10:00", "2024-01-01 10:30", "2024-01-01 11:00"]
            ),
            "Close Time": pd.to_datetime(
                ["2024-01-01 10:15", "2024-01-01 10:45", "2024-01-01 11:15"]
            ),
            "PnL": [100, -50, 75],
            "Lots": [1.0, 1.0, 1.5],
            "Open Price": [1.1000, 1.1010, 1.1005],
            "Close Price": [1.1020, 1.0990, 1.1025],
            "RR Ratio": [2.0, 1.5, 2.5],
            "Gain": ["1.0%", "-0.5%", "0.75%"],
            "Symbol": ["EURUSD", "EURUSD", "EURUSD"],
        })

        result = engineer_features(df)

        for col in FEATURE_COLUMNS_V2:
            assert col in result.columns, f"Missing column: {col}"

        assert "Is_High_Risk" in result.columns
        assert len(result) == 3
