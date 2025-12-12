import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
import shap

# ==============================================================================
# MODULE: AI RISK OFFICER (The "Brain")
# PURPOSE: Uses Machine Learning to predict if a trade is 'High Risk' before it happens.
# ARCHITECTURE: Hybrid System (Unsupervised Watchdog + Supervised Analyst)
# ==============================================================================

class AIRiskOfficer:
    def __init__(self, features=None):
        # 1. SYSTEM 1: The Watchdog (Isolation Forest)
        # Purpose: Detect Anomalies (e.g., Fat Finger, Freak Market events).
        # It is "Unsupervised" - it doesn't need to know what a loss looks like, just what "Weird" looks like.
        # contamination=0.05: We assume 5% of trades are weird outliers.
        self.iso_forest = IsolationForest(contamination=0.05, random_state=42)
        
        # 2. SYSTEM 2: The Analyst (Random Forest Classifier)
        # Purpose: Classify trades as 'Safe' (0) or 'Risky' (1) based on history.
        # It is "Supervised" - it learns from the 'Is_High_Risk' label we created in DataProcessor.
        # n_estimators=100: It creates 100 'Decision Trees' and takes the majority vote.
        # max_depth=5: Keeps trees simple to prevent 'memorizing' the past (Overfitting).
        self.classifier = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        
        # FEATURE SELECTION
        # These are the inputs the brain looks at.
        self.features = features if features else ['Hour_Decimal', 'Losing_Streak', 'Drawdown_State', 
                                                   'Lot_Deviation', 'Revenge_Timer', 'Lots', 'RR Ratio']
        
        # SHAP EXPLAINER (The "Why?")
        # Placeholder for the tool that explains the model's decisions.
        self.explainer = None

    def train(self, df):
        """Trains the models on the provided history."""
        # Prepare inputs (X) and answers (y)
        X = df[self.features].fillna(0)
        y = df['Is_High_Risk']

        # Train Watchdog: "Learn what normal looks like"
        self.iso_forest.fit(X)

        # Train Analyst: "Learn the difference between Safe and Risky trades"
        self.classifier.fit(X, y)
        
        # Setup SHAP: "Study the trained Analyst so you can explain it later"
        self.explainer = shap.TreeExplainer(self.classifier)
        
        print("AIRO Training Complete.")

    def predict(self, trade_row):
        """
        Evaluates a NEW trade.
        Returns: {risk_prob, is_anomaly, decision}
        """
        # Convert single row to DataFrame format for the model
        if isinstance(trade_row, (pd.Series, dict)):
             X_input = pd.DataFrame([trade_row])[self.features].fillna(0)
        else:
             X_input = trade_row[self.features].fillna(0)

        # 1. Ask Watchdog: Is this weird?
        # Returns -1 for Anomaly, 1 for Normal
        anomaly_score = self.iso_forest.predict(X_input)[0]
        is_anomaly = True if anomaly_score == -1 else False

        # 2. Ask Analyst: What is the probability of failure?
        # .predict_proba returns [[prob_safe, prob_risk]]
        # We want [0][1] aka the Risk Probability.
        risk_prob = self.classifier.predict_proba(X_input)[0][1]
        
        # 3. The Decision Gate (V1 Logic)
        # If Risk is > 70% OR it's an Anomaly -> BLOCK
        decision = "BLOCK" if (risk_prob > 0.70 or is_anomaly) else "ALLOW"
        
        return {
            'risk_prob': float(risk_prob),
            'is_anomaly': is_anomaly,
            'decision': decision
        }

    def get_explanation(self, trade_row):
        """
        Returns the TOP reason for the risk score.
        Uses SHAP values (Game Theory).
        """
        X_input = pd.DataFrame([trade_row])[self.features].fillna(0)
             
        # Ask SHAP: "How much did each feature contribute to the score?"
        shap_values = self.explainer.shap_values(X_input)
        
        # Handling Scikit-Learn Output formats (Technical cleanup)
        # We extract the values for Class 1 (Risk)
        if isinstance(shap_values, list): vals = shap_values[1][0]
        else: vals = shap_values[0, :, 1] if len(shap_values.shape) == 3 else shap_values[0]
        
        # Map values to their feature names
        feature_contributions = dict(zip(self.features, vals))
        
        # Sort so the biggest contributor is first
        sorted_features = sorted(feature_contributions.items(), key=lambda x: abs(x[1]), reverse=True)
        
        return sorted_features[:3] # Return Top 3 inputs
