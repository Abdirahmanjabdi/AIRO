"""
Sentinel-Zero Risk Engine (SentinelBrain)
==========================================
Unified V5 risk engine combining:
  - V1: Hybrid IsolationForest + RandomForest
  - V2: Context-aware features (9 total)
  - V3: Bayesian-optimized hyperparameters
  - V4: Active position sizing (PI controller)

Refactored from: ai_risk_officer.py, ai_agent_v4.py, ai_ultimate.py
Ref: ARCHITECTURE.md §3, AI_CONTRACT.md §1

Rules:
  - Circuit-breaker on all predictions (AI_CONTRACT §1.3)
  - Fail-safe: Risk-Off on failure
  - Model serialization via joblib → S3 (FP adjustment #3)
  - No Any types
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import IsolationForest, RandomForestClassifier

from sentinel.domain.models import (
    Decision,
    FeatureContribution,
    RiskAssessment,
    RiskMode,
    TradeContext,
)

logger = logging.getLogger(__name__)


# =============================================================================
# OPTIMIZED HYPERPARAMETERS (V3 — Bayesian/Optuna)
# =============================================================================

DEFAULT_RISK_THRESHOLD: float = 0.6537
DEFAULT_CONTAMINATION: float = 0.0399
DEFAULT_N_ESTIMATORS: int = 151
DEFAULT_MAX_DEPTH: int = 10
DEFAULT_SENSITIVITY: float = 1.5
DEFAULT_GENTLE_SLOPE: float = 0.4

# Feature columns matching TradeContext fields
FEATURE_COLUMNS: list[str] = [
    "Hour_Decimal", "Losing_Streak", "Drawdown_State",
    "Lot_Deviation", "Revenge_Timer", "Lots", "RR Ratio",
    "Realized_Vol_20", "Trend_Momentum",
]


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open (too many consecutive failures)."""


class SentinelBrain:
    """
    The V5 Risk Engine — institutional-grade active intervention system.

    Encapsulates:
      - Anomaly Detection (Isolation Forest)
      - Risk Classification (Random Forest)
      - Active Position Sizing (PI Controller)
      - SHAP Explainability
      - Circuit Breaker (fail-safe to Risk-Off)
    """

    def __init__(
        self,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
        contamination: float = DEFAULT_CONTAMINATION,
        n_estimators: int = DEFAULT_N_ESTIMATORS,
        max_depth: int = DEFAULT_MAX_DEPTH,
        sensitivity: float = DEFAULT_SENSITIVITY,
        gentle_slope: float = DEFAULT_GENTLE_SLOPE,
        circuit_breaker_threshold: int = 5,
    ) -> None:
        self.risk_threshold = risk_threshold
        self.sensitivity = sensitivity
        self.gentle_slope = gentle_slope

        # --- Models ---
        self.iso_forest = IsolationForest(
            contamination=contamination, random_state=42,
        )
        self.classifier = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
        )

        # --- SHAP Explainer ---
        self._explainer: shap.TreeExplainer | None = None

        # --- Circuit Breaker State ---
        self._consecutive_failures: int = 0
        self._circuit_breaker_threshold = circuit_breaker_threshold
        self._circuit_open: bool = False

        # --- Training State ---
        self._is_trained: bool = False
        self._feature_columns: list[str] = FEATURE_COLUMNS

    # =========================================================================
    # TRAINING
    # =========================================================================

    def train(self, df: pd.DataFrame) -> None:
        """
        Train both models on historical trade data.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain columns matching FEATURE_COLUMNS and 'Is_High_Risk'.
        """
        X: pd.DataFrame = df[self._feature_columns].fillna(0)
        y: pd.Series = df["Is_High_Risk"]

        logger.info("Training SentinelBrain on %d trades...", len(df))

        # Train Watchdog (unsupervised)
        self.iso_forest.fit(X)

        # Train Analyst (supervised)
        self.classifier.fit(X, y)

        # Setup SHAP explainer
        self._explainer = shap.TreeExplainer(self.classifier)

        self._is_trained = True
        logger.info("SentinelBrain training complete.")

    # =========================================================================
    # PREDICTION (with circuit breaker)
    # =========================================================================

    def assess_risk(self, context: TradeContext) -> RiskAssessment:
        """
        Evaluate a trade and return a full RiskAssessment.

        If the circuit breaker is open → returns Risk-Off immediately.
        If prediction fails → increments failure count, returns Risk-Off.

        Parameters
        ----------
        context : TradeContext
            Incoming trade telemetry from the bridge.

        Returns
        -------
        RiskAssessment
            Intervention decision with explainability.
        """
        start_time = time.perf_counter()

        # Circuit breaker: if open, return Risk-Off immediately
        if self._circuit_open:
            return self._risk_off_response(
                latency_ms=_elapsed_ms(start_time),
                mode=RiskMode.RISK_OFF,
            )

        # Baseline check
        if not self._is_trained:
            return self._risk_off_response(
                latency_ms=_elapsed_ms(start_time),
                mode=RiskMode.BASELINE_PENDING,
            )

        try:
            result = self._predict(context, start_time)
            self._reset_circuit_breaker()
            return result
        except Exception as exc:
            logger.error("Prediction failed: %s", exc, exc_info=True)
            self._record_failure()
            return self._risk_off_response(
                latency_ms=_elapsed_ms(start_time),
                mode=RiskMode.RISK_OFF,
            )

    def _predict(
        self,
        context: TradeContext,
        start_time: float,
    ) -> RiskAssessment:
        """Core prediction logic — no error handling (caller wraps)."""
        # Convert Pydantic model to feature vector
        X_input = self._context_to_dataframe(context)

        # 1. Anomaly Detection (Watchdog)
        anomaly_score: int = int(self.iso_forest.predict(X_input)[0])
        is_anomaly: bool = anomaly_score == -1

        # 2. Risk Classification (Analyst)
        risk_prob: float = float(self.classifier.predict_proba(X_input)[0][1])

        # 3. Active Sizing (PI Controller — V4/V5 logic)
        size_multiplier: float
        decision: Decision

        if is_anomaly:
            # Hard Rule: anomaly = immediate block
            size_multiplier = 0.0
            decision = Decision.BLOCK
        elif risk_prob > self.risk_threshold:
            # Danger Zone: aggressive dampening
            size_multiplier = max(0.0, 1.0 - (risk_prob * self.sensitivity))
            decision = Decision.BLOCK if size_multiplier == 0.0 else Decision.REDUCE_SIZE
        else:
            # Safe Zone: gentle slope
            size_multiplier = 1.0 - (risk_prob * self.gentle_slope)
            size_multiplier = max(0.0, min(1.0, size_multiplier))
            decision = Decision.ALLOW if size_multiplier >= 0.95 else Decision.REDUCE_SIZE

        # 4. SHAP Explanation
        explanation = self._explain(X_input)

        return RiskAssessment(
            decision=decision,
            risk_score=round(risk_prob, 4),
            is_anomaly=is_anomaly,
            size_multiplier=round(size_multiplier, 4),
            explanation=explanation,
            latency_ms=_elapsed_ms(start_time),
            mode=RiskMode.NORMAL,
        )

    # =========================================================================
    # EXPLAINABILITY (SHAP)
    # =========================================================================

    def _explain(
        self,
        X_input: pd.DataFrame,
        top_n: int = 3,
    ) -> list[FeatureContribution]:
        """Get top-N SHAP feature contributions for the prediction."""
        if self._explainer is None:
            return []

        try:
            shap_values = self._explainer.shap_values(X_input)

            # Handle sklearn output formats
            if isinstance(shap_values, list):
                vals: np.ndarray = shap_values[1][0]
            elif len(shap_values.shape) == 3:
                vals = shap_values[0, :, 1]
            else:
                vals = shap_values[0]

            # Pair with feature names and sort by absolute impact
            contributions = list(zip(self._feature_columns, vals.tolist()))
            contributions.sort(key=lambda x: abs(x[1]), reverse=True)

            return [
                FeatureContribution(feature=name, impact=round(float(impact), 4))
                for name, impact in contributions[:top_n]
            ]
        except Exception as exc:
            logger.warning("SHAP explanation failed: %s", exc)
            return []

    # =========================================================================
    # CIRCUIT BREAKER
    # =========================================================================

    def _record_failure(self) -> None:
        """Increment failure count; open circuit if threshold exceeded."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_breaker_threshold:
            self._circuit_open = True
            logger.critical(
                "Circuit breaker OPEN after %d consecutive failures. "
                "All predictions will return Risk-Off.",
                self._consecutive_failures,
            )

    def _reset_circuit_breaker(self) -> None:
        """Reset on successful prediction."""
        if self._consecutive_failures > 0:
            logger.info("Circuit breaker reset (was at %d failures).", self._consecutive_failures)
        self._consecutive_failures = 0
        self._circuit_open = False

    def reset_circuit_breaker(self) -> None:
        """Public reset — for manual recovery or half-open retry."""
        self._reset_circuit_breaker()

    @staticmethod
    def _risk_off_response(
        latency_ms: float,
        mode: RiskMode,
    ) -> RiskAssessment:
        """Default Risk-Off response (block everything)."""
        return RiskAssessment(
            decision=Decision.BLOCK,
            risk_score=1.0,
            is_anomaly=False,
            size_multiplier=0.0,
            explanation=[],
            latency_ms=latency_ms,
            mode=mode,
        )

    # =========================================================================
    # SERIALIZATION (S3 model store)
    # =========================================================================

    def save(self, path: Path) -> None:
        """Serialize the trained brain to a .joblib file."""
        if not self._is_trained:
            raise RuntimeError("Cannot save untrained model.")

        state = {
            "iso_forest": self.iso_forest,
            "classifier": self.classifier,
            "risk_threshold": self.risk_threshold,
            "sensitivity": self.sensitivity,
            "gentle_slope": self.gentle_slope,
            "feature_columns": self._feature_columns,
        }
        joblib.dump(state, path)
        logger.info("Model saved to %s", path)

    @classmethod
    def load(cls, path: Path) -> SentinelBrain:
        """Deserialize a trained brain from a .joblib file."""
        state: dict[str, object] = joblib.load(path)

        brain = cls(
            risk_threshold=float(state["risk_threshold"]),  # type: ignore[arg-type]
            sensitivity=float(state["sensitivity"]),  # type: ignore[arg-type]
            gentle_slope=float(state["gentle_slope"]),  # type: ignore[arg-type]
        )
        brain.iso_forest = state["iso_forest"]  # type: ignore[assignment]
        brain.classifier = state["classifier"]  # type: ignore[assignment]
        brain._feature_columns = state["feature_columns"]  # type: ignore[assignment]
        brain._explainer = shap.TreeExplainer(brain.classifier)
        brain._is_trained = True

        logger.info("Model loaded from %s", path)
        return brain

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _context_to_dataframe(self, context: TradeContext) -> pd.DataFrame:
        """Convert a TradeContext Pydantic model to a 1-row DataFrame."""
        row: dict[str, float] = {
            "Hour_Decimal": context.hour_decimal,
            "Losing_Streak": float(context.losing_streak),
            "Drawdown_State": context.drawdown_state,
            "Lot_Deviation": context.lot_deviation,
            "Revenge_Timer": context.revenge_timer,
            "Lots": context.lots,
            "RR Ratio": context.rr_ratio,
            "Realized_Vol_20": context.realized_vol_20,
            "Trend_Momentum": context.trend_momentum,
        }
        return pd.DataFrame([row])[self._feature_columns]

    @property
    def is_trained(self) -> bool:
        """Whether the brain has been trained."""
        return self._is_trained

    @property
    def is_circuit_open(self) -> bool:
        """Whether the circuit breaker is currently open."""
        return self._circuit_open


# =============================================================================
# UTILITIES
# =============================================================================

def _elapsed_ms(start: float) -> float:
    """Calculate elapsed time in milliseconds."""
    return round((time.perf_counter() - start) * 1000, 2)
