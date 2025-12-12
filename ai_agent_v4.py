from ai_risk_officer import AIRiskOfficer
import pandas as pd
import numpy as np

class ActiveAgent(AIRiskOfficer):
    def __init__(self, features=None):
        super().__init__(features)
        
    def get_position_sizer(self, trade_row):
        """
        Returns a position sizing multiplier (0.0 to 1.0) instead of binary Block/Allow.
        
        Logic: Use the Probability of Failure as a dampener.
        Sizing = 1.0 - (Risk_Prob ^ Sensitivity)
        """
        assessment = self.predict(trade_row)
        risk_prob = assessment['risk_prob']
        is_anomaly = assessment['is_anomaly']
        
        # Hard Rule: If Anomaly (Fat Finger), cut size to 0 immediately (or 10% for test)
        if is_anomaly:
            return 0.0, risk_prob
            
        # Soft Rule: Continuous Sizing
        # We want: 
        # Risk 0.0 -> Size 1.0
        # Risk 0.5 -> Size 0.5
        # Risk 1.0 -> Size 0.0
        # Formula: Size = 1.0 - Risk
        
        # However, we want to be aggressive on low risk. Let's use a non-linear curve.
        # If Risk < 0.5, we want near full size.
        # If Risk > 0.7, we want rapid drop off.
        
        # Let's use the Optimized Threshold (0.65) as the "Cliff".
        # If risk > 0.65, we strictly limit to max 0.2 size.
        # If risk < 0.65, we scale linearly.
        
        if risk_prob > 0.65:
            # High Risk Zone: Dampen aggressively
            size = max(0.0, 1.0 - (risk_prob * 1.5)) # e.g. 0.7 * 1.5 = 1.05 -> Size 0.
        else:
            # Low Risk Zone: Slight dampener
            size = 1.0 - (risk_prob * 0.5) # e.g. 0.2 * 0.5 = 0.1 -> Size 0.9
            
        return max(0.0, min(1.0, size)), risk_prob
