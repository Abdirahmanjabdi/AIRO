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

try:
    import mlflow
    import mlflow.sklearn
except ImportError:
    mlflow = None

from sentinel.domain.models import (
    Decision,
    FeatureContribution,
    RiskAssessment,
    RiskMode,
    TiltResponse,
    TradeContext,
    UserInitialParameters,
    UserMaturity,
)

logger = logging.getLogger(__name__)


def get_progression_level(trade_count: int) -> int:
    """10-Level progression map based on collected behavioral logs."""
    if trade_count < 20: return 1
    elif trade_count < 50: return 2
    elif trade_count < 100: return 3
    elif trade_count < 150: return 4
    elif trade_count < 200: return 5
    elif trade_count < 300: return 6
    elif trade_count < 400: return 7
    elif trade_count < 600: return 8
    elif trade_count < 1000: return 9
    return 10  # God Mode (1000+ trades)



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
        if y.nunique() < 2:
            synthetic = X.iloc[[0]].copy()
            synthetic["Losing_Streak"] = 5.0
            synthetic["Drawdown_State"] = max(float(X["Drawdown_State"].max()), 0.05)
            synthetic["Lot_Deviation"] = max(float(X["Lot_Deviation"].max()), 3.0)
            synthetic["Revenge_Timer"] = min(float(X["Revenge_Timer"].min()), 1.0)
            X = pd.concat([X, synthetic], ignore_index=True)
            y = pd.concat([y, pd.Series([1 - int(y.iloc[0])])], ignore_index=True)

        logger.info("Training SentinelBrain on %d trades...", len(df))

        # Train Watchdog (unsupervised)
        self.iso_forest.fit(X)

        # Train Analyst (supervised)
        self.classifier.fit(X, y)

        # Setup SHAP explainer
        self._explainer = shap.TreeExplainer(self.classifier)

        self._is_trained = True
        logger.info("SentinelBrain training complete.")

    def train_with_rlhf(
        self,
        df: pd.DataFrame,
        user_id: str,
        feedback_labels: list[str | None] | None = None,
    ) -> None:
        """
        Train both models with dynamic sample weighting based on RLHF.
        Log parameters, metrics, and model artifact locally to local SQLite MLflow tracking server.
        """
        X: pd.DataFrame = df[self._feature_columns].fillna(0)
        y: pd.Series = df["Is_High_Risk"]
        if y.nunique() < 2:
            synthetic = X.iloc[[0]].copy()
            synthetic["Losing_Streak"] = 5.0
            synthetic["Drawdown_State"] = max(float(X["Drawdown_State"].max()), 0.05)
            synthetic["Lot_Deviation"] = max(float(X["Lot_Deviation"].max()), 3.0)
            synthetic["Revenge_Timer"] = min(float(X["Revenge_Timer"].min()), 1.0)
            X = pd.concat([X, synthetic], ignore_index=True)
            y = pd.concat([y, pd.Series([1 - int(y.iloc[0])])], ignore_index=True)
            if feedback_labels is not None:
                feedback_labels = feedback_labels + [None]

        logger.info("Training SentinelBrain with RLHF for user %s on %d trades...", user_id, len(df))

        # Train Watchdog (unsupervised)
        self.iso_forest.fit(X)

        # Standard weight is 1.0. False Positive samples get slammed down to 0.05.
        sample_weights = []
        if feedback_labels is not None:
            # Pad or slice feedback labels to match the size of X
            padded_labels = list(feedback_labels)
            while len(padded_labels) < len(X):
                padded_labels.append(None)
            for label in padded_labels[:len(X)]:
                if label == "FALSE_POSITIVE":
                    sample_weights.append(0.05)  # Penalize that feature subspace
                else:
                    sample_weights.append(1.0)
        else:
            sample_weights = [1.0] * len(X)

        # Train Analyst with sample weights (supervised)
        self.classifier.fit(X, y, sample_weight=sample_weights)

        # Setup explainers
        self._explainer = shap.TreeExplainer(self.classifier)
        self._is_trained = True

        # Log parameters and model via MLflow if available
        if mlflow is not None:
            try:
                mlflow.set_tracking_uri("sqlite:///mlflow.db")
                mlflow.set_experiment(f"Experiment_{user_id}")
                with mlflow.start_run(run_name="level_progression_retrain") as active_run:
                    mlflow.log_param("risk_threshold", self.risk_threshold)
                    mlflow.log_param("n_estimators", self.classifier.n_estimators)
                    mlflow.log_metric("dataset_size", len(df))
                    mlflow.sklearn.log_model(self.classifier, "model")
                    
                    # Log feed score metrics
                    fp_count = sample_weights.count(0.05)
                    tp_count = len(sample_weights) - fp_count
                    feed_score = tp_count / len(sample_weights) if sample_weights else 1.0
                    mlflow.log_metric("user_feedback_score", feed_score)

                    # Register and transition model stage
                    model_uri = f"runs:/{active_run.info.run_id}/model"
                    model_name = f"Model_{user_id}"
                    model_version = mlflow.register_model(model_uri, model_name)
                    
                    client = mlflow.tracking.MlflowClient()
                    client.transition_model_version_stage(
                        name=model_name,
                        version=model_version.version,
                        stage="Production",
                        archive_existing_versions=True
                    )
                    client.set_model_version_tag(
                        name=model_name,
                        version=model_version.version,
                        key="model_level",
                        value=str(get_progression_level(len(df)))
                    )
            except Exception as e:
                logger.warning("MLflow logging/registration failed: %s", e)

        logger.info("SentinelBrain training complete for %s.", user_id)

    # =========================================================================
    # PREDICTION (with circuit breaker)
    # =========================================================================

    def assess_risk(self, context: TradeContext, skip_explanation: bool = True) -> RiskAssessment:
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
            result = self._predict(context, start_time, skip_explanation)
            self._reset_circuit_breaker()
            return result
        except Exception as exc:
            logger.error("Prediction failed: %s", exc, exc_info=True)
            self._record_failure()
            return self._risk_off_response(
                latency_ms=_elapsed_ms(start_time),
                mode=RiskMode.RISK_OFF,
            )

    def assess_bootstrap_risk(
        self,
        context: TradeContext,
        initial_parameters: UserInitialParameters,
        maturity_state: UserMaturity,
    ) -> RiskAssessment:
        """
        Cold-start scoring for users without a mature personalized model.

        Governed by a hardcoded 'Rule-Based Risk DNA Layer':
        - Max daily drawdown = 4%
        - Max lot deviation = 1.5x typical lot size
        """
        start_time = time.perf_counter()
        signals: list[FeatureContribution] = []
        decision = Decision.ALLOW
        size_multiplier = 1.0
        risk_score = 0.15

        # 1. Daily drawdown rule (4% cap)
        if context.drawdown_state > 0.04:
            decision = Decision.BLOCK
            size_multiplier = 0.0
            risk_score = 0.95
            signals.append(FeatureContribution(feature="drawdown_state", impact=0.95))
            logger.info("Rule-Based Risk DNA Block: drawdown_state %.4f exceeds 4%% cap", context.drawdown_state)

        # 2. Lot deviation rule (1.5x cap)
        typical = max(initial_parameters.typical_lot_size, 0.01)
        max_allowed_lots = typical * 1.5
        if context.lots > max_allowed_lots:
            risk_score = max(risk_score, 0.85)
            signals.append(FeatureContribution(feature="lot_deviation", impact=0.85))
            
            if context.lots > typical * 2.0:
                decision = Decision.BLOCK
                size_multiplier = 0.0
                risk_score = 0.95
                logger.info("Rule-Based Risk DNA Block: lots %.2f exceeds 2.0x baseline %.2f", context.lots, typical)
            else:
                if decision != Decision.BLOCK:
                    decision = Decision.REDUCE_SIZE
                    size_multiplier = max_allowed_lots / context.lots
                logger.info("Rule-Based Risk DNA Size Reduction: lots %.2f exceeds 1.5x baseline %.2f", context.lots, typical)

        if not signals:
            signals.append(FeatureContribution(feature="steady_baseline", impact=0.15))

        return RiskAssessment(
            decision=decision,
            risk_score=risk_score,
            is_anomaly=decision == Decision.BLOCK,
            size_multiplier=round(size_multiplier, 4),
            explanation=signals,
            latency_ms=_elapsed_ms(start_time),
            mode=RiskMode.BOOTSTRAP,
            maturity_state=maturity_state,
            shadow_mode=False,
        )

    def _predict(
        self,
        context: TradeContext,
        start_time: float,
        skip_explanation: bool = True,
    ) -> RiskAssessment:
        """Core prediction logic — no error handling (caller wraps)."""
        # Convert Pydantic model to feature vector using NumPy for O(1) inference speed
        X_input = self._context_to_numpy(context)

        # 1. Anomaly Detection (Watchdog)
        anomaly_score: int = int(self.iso_forest.predict(X_input)[0])
        is_anomaly: bool = anomaly_score == -1

        # 2. Risk Classification (Analyst)
        class_probs = self.classifier.predict_proba(X_input)[0]
        positive_indices = np.where(self.classifier.classes_ == 1)[0]
        risk_prob: float = (
            float(class_probs[int(positive_indices[0])])
            if len(positive_indices) > 0
            else 0.0
        )

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
        explanation = [] if skip_explanation else self._explain(X_input)

        return RiskAssessment(
            decision=decision,
            risk_score=round(risk_prob, 4),
            is_anomaly=is_anomaly,
            size_multiplier=round(size_multiplier, 4),
            explanation=explanation,
            latency_ms=_elapsed_ms(start_time),
            mode=RiskMode.NORMAL,
            maturity_state=UserMaturity.MATURITY_2,
        )

    # =========================================================================
    # EXPLAINABILITY (SHAP)
    # =========================================================================

    def _explain(
        self,
        X_input: np.ndarray | pd.DataFrame,
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

    def _context_to_numpy(self, context: TradeContext) -> np.ndarray:
        """Convert a TradeContext Pydantic model to a 1-row NumPy array for fast inference."""
        return np.array([[
            context.hour_decimal,
            float(context.losing_streak),
            context.drawdown_state,
            context.lot_deviation,
            context.revenge_timer,
            context.lots,
            context.rr_ratio,
            context.realized_vol_20,
            context.trend_momentum,
        ]])
        
    def _context_to_dataframe(self, context: TradeContext) -> pd.DataFrame:
        """Legacy helper for when feature names are required."""
        return pd.DataFrame(self._context_to_numpy(context), columns=self._feature_columns)

    def _bootstrap_signals(
        self,
        context: TradeContext,
        initial_parameters: UserInitialParameters,
    ) -> tuple[float, list[FeatureContribution]]:
        """Score cold-start risk from relative, style-aware signals."""
        signals: list[tuple[str, float]] = []

        drawdown_limit = initial_parameters.max_drawdown_pct / 100.0
        if context.drawdown_state > drawdown_limit:
            signals.append(
                (
                    "Drawdown_State",
                    min(1.0, context.drawdown_state / max(drawdown_limit, 0.001)),
                )
            )

        lot_z_score = self._relative_lot_z_score(context.lots, initial_parameters.typical_lot_size)
        if lot_z_score > 2.0:
            signals.append(("Lot_ZScore", min(1.0, lot_z_score / 3.0)))

        hard_lot_limit = initial_parameters.typical_lot_size * initial_parameters.max_lot_multiplier
        if context.lots > hard_lot_limit:
            signals.append(("Lot_Multiplier", min(1.0, context.lots / max(hard_lot_limit, 0.01))))

        loss_threshold = max(initial_parameters.loss_review_threshold, 1)
        if context.losing_streak >= loss_threshold:
            signals.append(
                (
                    "Loss_Review_Threshold",
                    min(1.0, context.losing_streak / max(float(loss_threshold + 2), 1.0)),
                )
            )

        revenge_threshold = {
            "scalper": 3.0,
            "intraday": 10.0,
            "swing": 60.0,
        }[initial_parameters.trading_style.value]
        if initial_parameters.tilt_response == TiltResponse.IMMEDIATE_REENTRY:
            revenge_threshold *= 1.5
        elif initial_parameters.tilt_response == TiltResponse.MIXED:
            revenge_threshold *= 1.2
        if 0.0 < context.revenge_timer < revenge_threshold:
            revenge_signal = min(1.0, 1.0 - (context.revenge_timer / revenge_threshold))
            if initial_parameters.tilt_response == TiltResponse.IMMEDIATE_REENTRY:
                revenge_signal = min(1.0, revenge_signal * 1.15)
            signals.append(("Tilt_Reentry_Timer", revenge_signal))

        if not signals:
            return 0.15, [
                FeatureContribution(feature="Risk_DNA", impact=0.15),
            ]

        signals.sort(key=lambda item: item[1], reverse=True)
        risk_score = min(1.0, 0.25 + sum(score for _, score in signals[:3]) / 2.5)
        explanation = [
            FeatureContribution(feature=name, impact=round(score, 4))
            for name, score in signals[:3]
        ]
        return round(risk_score, 4), explanation

    @staticmethod
    def _relative_lot_z_score(current_lots: float, average_lots: float) -> float:
        """
        Style-agnostic lot anomaly proxy for cold start.

        Until enough history exists for a real sigma, use a conservative 25%
        implied standard deviation around the declared average.
        """
        implied_sigma = max(average_lots * 0.25, 0.01)
        return max(0.0, (current_lots - average_lots) / implied_sigma)

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
