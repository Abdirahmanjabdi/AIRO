import pandas as pd
import numpy as np
from data_processor import DataLoader
from ai_risk_officer import AIRiskOfficer

def run_simulation(filepath):
    print("--- Starting Shadow Ledger Simulation ---")
    
    # 1. Load and Process Data
    loader = DataLoader(filepath)
    loader.load_data()
    df = loader.engineer_features()
    
    # 2. Train AI Risk Officer
    # In a real scenario, we'd train on past data and test on future.
    # Here we train on the full set to demonstrate the "Rules Validation".
    airo = AIRiskOfficer()
    airo.train(df)
    
    # 3. Initialize Simulation
    initial_equity = 100000.0
    real_equity = initial_equity
    shadow_equity = initial_equity
    
    real_curve = [initial_equity]
    shadow_curve = [initial_equity]
    
    intervention_log = []
    
    print(f"Simulating {len(df)} trades...")
    
    for index, row in df.iterrows():
        # Update Real Equity
        pnl = row['PnL']
        real_equity += pnl
        real_curve.append(real_equity)
        
        # Consult AIRO
        # We need to predict based on the features available available at that time
        # The AIRiskOfficer.predict method expects a row with features
        assessment = airo.predict(row)
        
        decision = assessment['decision']
        risk_score = assessment['risk_prob']
        is_anomaly = assessment['is_anomaly']
        
        if decision == "BLOCK":
            # Shadow Equity does NOT take the trade
            shadow_equity += 0
            
            # Log Intervention
            explanation = airo.get_explanation(row)
            # explanation is list of tuples: [('Feature', val), ...]
            reason_str = ", ".join([f"{k}: {v:.2f}" for k, v in explanation])
            
            intervention_log.append({
                'Date': row['Open Time'],
                'Symbol': row['Symbol'], # Assuming Symbol exists
                'PnL_Saved': -pnl, # If PnL was negative, we saved a loss (positive value)
                'Risk_Score': round(risk_score * 100, 1),
                'Reason': reason_str
            })
        else:
            # Shadow Equity TAKES the trade
            shadow_equity += pnl
        
        shadow_curve.append(shadow_equity)
        
    # 4. Compile Results
    # Align curves with dataframe (len(curve) = len(df) + 1 for initial)
    # Let's just create a results DF aligned with the trades
    
    results = df.copy()
    results['Real_Equity'] = real_curve[1:] # Skip initial
    results['Shadow_Equity'] = shadow_curve[1:]
    
    # Calculate Metrics
    real_return = (real_equity - initial_equity) / initial_equity * 100
    shadow_return = (shadow_equity - initial_equity) / initial_equity * 100
    
    print(f"\n--- Simulation Results ---")
    print(f"Real Return:   {real_return:.2f}%")
    print(f"Shadow Return: {shadow_return:.2f}%")
    print(f"Interventions: {len(intervention_log)}")
    
    # Save Intervention Log
    log_df = pd.DataFrame(intervention_log)
    if not log_df.empty:
        print("\nTop Interventions:")
        print(log_df.head())
        # log_df.to_csv("intervention_log.csv", index=False)
        
    return results, log_df, real_return, shadow_return

if __name__ == "__main__":
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    results, log, r_ret, s_ret = run_simulation(filepath)
    
    # Save results for Dashboard
    results.to_csv("simulation_results.csv", index=False)
    log.to_csv("intervention_log.csv", index=False)
    print("Results saved to 'simulation_results.csv' and 'intervention_log.csv'")
