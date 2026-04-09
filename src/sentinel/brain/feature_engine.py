"""
Sentinel-Zero Feature Engine
==============================
Stateless feature engineering functions. Transforms raw trade data
into the 9-feature vector consumed by the Risk Engine.

Refactored from: data_processor.py
Ref: ARCHITECTURE.md §3.2, AI_CONTRACT.md §1.1

Rules:
  - Pure functions (no side effects, no file I/O)
  - Full mypy type hints, no Any
  - Support both batch (DataFrame) and single-row (dict) modes
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


# =============================================================================
# BEHAVIORAL FEATURES (V1)
# =============================================================================

def compute_hour_decimal(open_time: pd.Series) -> pd.Series:
    """Convert datetime to decimal hour (14:30 → 14.5)."""
    return open_time.dt.hour + (open_time.dt.minute / 60)


def compute_revenge_timer(
    open_time: pd.Series,
    close_time: pd.Series,
) -> pd.Series:
    """
    Minutes between current trade open and previous trade close.
    First trade gets 9999.0 (no revenge possible).
    """
    last_close: pd.Series = close_time.shift(1)
    timer: pd.Series = (open_time - last_close).dt.total_seconds() / 60
    return timer.fillna(9999.0)


def compute_losing_streak(pnl: pd.Series) -> pd.Series:
    """
    Count consecutive losses. Resets on any win.
    [L, L, W, L] → [1, 2, 0, 1]
    """
    loss_mask: pd.Series = (pnl < 0).astype(int)
    groups: pd.Series = (loss_mask != loss_mask.shift()).cumsum()
    return loss_mask.groupby(groups).cumsum()


def compute_drawdown_state(pnl: pd.Series) -> pd.Series:
    """
    Distance from equity high-water mark.
    Drawdown = Peak_Equity - Current_Equity
    """
    equity_curve: pd.Series = pnl.cumsum()
    peak_equity: pd.Series = equity_curve.cummax()
    return peak_equity - equity_curve


def compute_lot_deviation(lots: pd.Series, window: int = 20) -> pd.Series:
    """
    Z-score of current lot size vs rolling mean.
    Detects "Fat Finger" or abnormal sizing.
    """
    rolling_mean: pd.Series = lots.rolling(window).mean()
    rolling_std: pd.Series = lots.rolling(window).std()
    deviation: pd.Series = (lots - rolling_mean) / rolling_std
    return deviation.fillna(0.0)


# =============================================================================
# CONTEXT FEATURES (V2)
# =============================================================================

def compute_realized_volatility(
    open_price: pd.Series,
    close_price: pd.Series,
    window: int = 20,
) -> pd.Series:
    """
    20-trade rolling StdDev of absolute trade ranges.
    High values → choppy/volatile market regime.
    """
    trade_range: pd.Series = (close_price - open_price).abs()
    return trade_range.rolling(window).std().fillna(0.0)


def compute_trend_momentum(
    open_price: pd.Series,
    window: int = 20,
) -> pd.Series:
    """
    Absolute 20-trade rolling mean of price changes.
    High values → strong directional trend.
    """
    price_change: pd.Series = open_price.diff()
    return price_change.rolling(window).mean().abs().fillna(0.0)


# =============================================================================
# TARGET LABEL
# =============================================================================

def compute_is_high_risk(
    pnl: pd.Series,
    drawdown_state: pd.Series,
    losing_streak: pd.Series,
    revenge_timer: pd.Series,
    drawdown_threshold: float = 5.0,
    streak_threshold: int = 3,
    revenge_threshold: float = 15.0,
) -> pd.Series:
    """
    Binary label: 1 if trade shows behavioral failure mode.
    Logic: Loss AND (High Drawdown OR High Streak OR Revenge Entry)
    """
    is_loss: pd.Series = pnl < 0
    bad_condition: pd.Series = (
        (drawdown_state > drawdown_threshold)
        | (losing_streak >= streak_threshold)
        | (revenge_timer < revenge_threshold)
    )
    return (is_loss & bad_condition).astype(int)


# =============================================================================
# BATCH PIPELINE (DataFrame → DataFrame)
# =============================================================================

# Column names expected in raw CSV / broker data
_REQUIRED_COLUMNS: list[str] = [
    "Open Time", "Close Time", "PnL", "Lots",
    "Open Price", "Close Price", "RR Ratio", "Gain",
]

# Engineered feature names (output columns)
FEATURE_COLUMNS_V1: list[str] = [
    "Hour_Decimal", "Losing_Streak", "Drawdown_State",
    "Lot_Deviation", "Revenge_Timer", "Lots", "RR Ratio",
]

FEATURE_COLUMNS_V2: list[str] = FEATURE_COLUMNS_V1 + [
    "Realized_Vol_20", "Trend_Momentum",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full feature engineering pipeline (V1 + V2 + target label).

    Parameters
    ----------
    df : pd.DataFrame
        Raw trade data with columns matching _REQUIRED_COLUMNS.

    Returns
    -------
    pd.DataFrame
        Original data plus all 9 engineered features and Is_High_Risk label.
    """
    result: pd.DataFrame = df.copy()

    # --- Clean dates ---
    result["Open Time"] = pd.to_datetime(result["Open Time"], errors="coerce")
    result["Close Time"] = pd.to_datetime(result["Close Time"], errors="coerce")
    result = result.dropna(subset=["Open Time", "Close Time"])
    result = result.sort_values("Open Time").reset_index(drop=True)

    # --- Clean Gain column ---
    if result["Gain"].dtype == object:
        result["Gain"] = (
            result["Gain"].str.replace("%", "", regex=False).astype(float)
        )

    # --- V1: Behavioral Features ---
    result["Hour_Decimal"] = compute_hour_decimal(result["Open Time"])
    result["Revenge_Timer"] = compute_revenge_timer(
        result["Open Time"], result["Close Time"]
    )
    result["Losing_Streak"] = compute_losing_streak(result["PnL"])
    result["Drawdown_State"] = compute_drawdown_state(result["PnL"])
    result["Lot_Deviation"] = compute_lot_deviation(result["Lots"])

    # --- V2: Context Features ---
    result["Realized_Vol_20"] = compute_realized_volatility(
        result["Open Price"], result["Close Price"]
    )
    result["Trend_Momentum"] = compute_trend_momentum(result["Open Price"])

    # --- Target Label ---
    result["Is_High_Risk"] = compute_is_high_risk(
        pnl=result["PnL"],
        drawdown_state=result["Drawdown_State"],
        losing_streak=result["Losing_Streak"],
        revenge_timer=result["Revenge_Timer"],
    )

    return result


# =============================================================================
# SINGLE-ROW FEATURE COMPUTATION (Real-time API)
# =============================================================================

def compute_single_trade_features(
    trade: dict[str, float | int],
    history: pd.DataFrame,
) -> dict[str, float]:
    """
    Compute features for a single incoming trade given recent history.

    Used by the Brain API for real-time /v1/analyze calls.
    The `history` DataFrame should contain the user's last ~20 trades
    (cached in Redis or fetched from PG).

    Parameters
    ----------
    trade : dict
        Raw trade data with keys matching TradeContext fields.
    history : pd.DataFrame
        Recent trade history (min 1 row, ideally 20+).

    Returns
    -------
    dict
        Feature dict ready for model inference.
    """
    # If history has pre-computed features, we can use them directly
    # Otherwise, re-compute from scratch
    if "Hour_Decimal" in history.columns:
        # History already engineered — just compute for new trade
        return {
            "Hour_Decimal": trade.get("hour_decimal", 0.0),
            "Losing_Streak": trade.get("losing_streak", 0),
            "Drawdown_State": trade.get("drawdown_state", 0.0),
            "Lot_Deviation": trade.get("lot_deviation", 0.0),
            "Revenge_Timer": trade.get("revenge_timer", 9999.0),
            "Lots": trade.get("lots", 1.0),
            "RR Ratio": trade.get("rr_ratio", 2.0),
            "Realized_Vol_20": trade.get("realized_vol_20", 0.0),
            "Trend_Momentum": trade.get("trend_momentum", 0.0),
        }

    # Fallback: append trade to history and re-engineer
    new_row = pd.DataFrame([trade])
    combined = pd.concat([history, new_row], ignore_index=True)
    engineered = engineer_features(combined)
    last_row = engineered.iloc[-1]

    return {col: float(last_row[col]) for col in FEATURE_COLUMNS_V2}
