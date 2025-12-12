import optuna
import pandas as pd
import numpy as np
from data_processor import DataLoader
from ai_risk_officer import AIRiskOfficer
from sklearn.ensemble import IsolationForest, RandomForestClassifier

# Suppress warnings for cleaner output
import warnings
warnings.filterwarnings("ignore")

def objective(trial):
    # 1. Define Hyperparameter Search Space
    risk_threshold = trial.suggest_float("risk_threshold", 0.50, 0.95)
    contamination = trial.suggest_float("contamination", 0.01, 0.10)
    n_estimators = trial.suggest_int("n_estimators", 50, 200)
    max_depth = trial.suggest_int("max_depth", 3, 10)
    
    # 2. Load Data (V2 Context Features)
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    loader = DataLoader(filepath)
    loader.load_data()
    df = loader.engineer_features()
    df = loader.engineer_context_features()
    
    # 3. Initialize & Train Model with trial params
    # Note: We need to manually inject params into AIRiskOfficer or subclass it.
    # For speed, let's just use the classes directly here or Modify AIRiskOfficer to accept them.
    # It's cleaner to instantiate logic here for the optimization loop.
    
    features = ['Hour_Decimal', 'Losing_Streak', 'Drawdown_State', 
                'Lot_Deviation', 'Revenge_Timer', 'Realized_Vol_20', 'Trend_Momentum']
    
    X = df[features].fillna(0)
    y = df['Is_High_Risk']
    
    # Train IsoForest
    iso = IsolationForest(contamination=contamination, random_state=42)
    iso.fit(X)
    
    # Train Classifier
    # Note: In a real optimization, we must use time-series split validation to avoid overfitting.
    # But since we are optimizing the *simulation* result on this specific "Post-Test" dataset as requested,
    # we fit on the full set to see "How optimal could we have been?".
    clf = RandomForestClassifier(n_estimators=n_estimators, max_depth=max_depth, random_state=42)
    clf.fit(X, y)
    
    # 4. Run Fast Simulation (Vectorized or simplified loop)
    # Predicting all at once is faster than looping
    risk_probs = clf.predict_proba(X)[:, 1]
    anomalies = iso.predict(X) # -1 is anomaly
    
    # Decision Logic
    # Block if Risk > Threshold OR Anomaly == -1
    # We want to find the Threshold that maximizes Equity
    
    decisions = []
    for risk, anom in zip(risk_probs, anomalies):
        if risk > risk_threshold or anom == -1:
            decisions.append(0) # Block (Multiplier 0)
        else:
            decisions.append(1) # Allow (Multiplier 1)
            
    # Calculate Equity
    pnl = df['PnL'].values
    # Shadow PnL = Real PnL * Decision (1 or 0)
    shadow_pnl = pnl * np.array(decisions)
    
    total_return = (shadow_pnl.sum() + 100000) / 100000
    
    # Objective: Maximize Total Return
    return total_return

if __name__ == "__main__":
    print("--- Starting AIRO V3 Optimization (Optuna) ---")
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=50) # 50 trials for speed, can increase
    
    print("\n--- Optimization Results ---")
    print(f"Best Return Multiplier: {study.best_value:.4f}x")
    print(f"Best ROI: {(study.best_value - 1) * 100:.2f}%")
    print("Best Parameters:")
    for k, v in study.best_params.items():
        print(f"  {k}: {v}")
    
    # Save best params to file for reference
    with open("v3_best_params.txt", "w") as f:
        f.write(str(study.best_params))
