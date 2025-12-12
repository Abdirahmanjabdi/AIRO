from ai_agent_v4 import ActiveAgent
from sklearn.ensemble import IsolationForest, RandomForestClassifier

# ==============================================================================
# MODULE: AI ULTIMATE (The "Peak State")
# PURPOSE: Combines the best of V2 (Context), V3 (Optimization), and V4 (Sizing).
# ==============================================================================

class AIUltimate(ActiveAgent):
    def __init__(self):
        # 1. USE V2 FEATURE SET
        # We don't just use behavior; we use Market Context (Volatility/Trend)
        v2_features = ['Hour_Decimal', 'Losing_Streak', 'Drawdown_State', 
                       'Lot_Deviation', 'Revenge_Timer', 'Realized_Vol_20', 'Trend_Momentum']
        super().__init__(features=v2_features)
        
        # 2. INJECT V3 OPTIMIZED HYPERPARAMETERS
        # These numbers were found by the 'Optuna' Bayesian Search (V3).
        # We hardcode them here to specificy the "Perfect Configuration".
        
        self.optimized_threshold = 0.6537 # The exact line where risk becomes unacceptable
        self.contamination = 0.0399       # Optimal strictness for anomalies
        self.n_estimators = 151           # Optimal number of trees
        self.max_depth = 10               # Optimal tree complexity
        
        # Re-initialize the brains with these perfect settings
        self.iso_forest = IsolationForest(contamination=self.contamination, random_state=42)
        self.classifier = RandomForestClassifier(n_estimators=self.n_estimators, max_depth=self.max_depth, random_state=42)

    def get_position_sizer(self, trade_row):
        """
        The V4 Logic Engine ("The Evaluator").
        Instead of saying "NO", it says "How much?".
        
        Returns: Size Multiplier (0.0 to 1.0)
        """
        assessment = self.predict(trade_row)
        risk_prob = assessment['risk_prob']
        is_anomaly = assessment['is_anomaly']
        
        # HARD RULE: If it's an Anomaly (1-in-100 freak event), kill it.
        if is_anomaly:
            return 0.0, risk_prob
            
        # DYNAMIC SIZING LOGIC
        # We use the Optimized Threshold (0.6537) as the "Cliff".
        
        if risk_prob > self.optimized_threshold:
            # DANGER ZONE
            # If Risk (e.g. 0.70) is higher than Threshold (0.65)...
            # We want to reduce size aggressively.
            # Multiplier: 1.5x (Sensitivity)
            # Math: 1.0 - (0.70 * 1.5) = -0.05 -> Clamped to 0.0
            size = max(0.0, 1.0 - (risk_prob * 1.5))
        else:
            # SAFE ZONE
            # Even if safe, we reduce slightly as risk rises.
            # Multiplier: 0.4x (Gentle slope)
            # Math: 1.0 - (0.20 * 0.4) = 0.92 size.
            size = 1.0 - (risk_prob * 0.4)
            
        # Ensure result is between 0.0 and 1.0
        return max(0.0, min(1.0, size)), risk_prob
