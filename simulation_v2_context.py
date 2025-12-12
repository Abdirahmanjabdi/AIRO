from simulation import run_simulation
from data_processor import DataLoader
from ai_risk_officer import AIRiskOfficer
import pandas as pd

def run_simulation_v2(filepath):
    print("--- Starting V2 Deep Context Simulation ---")
    
    # 1. Load and Process Data (V2 Logic)
    loader = DataLoader(filepath)
    loader.load_data()
    # First engineer standard features
    df = loader.engineer_features()
    # Then engineer Context features
    df = loader.engineer_context_features()
    
    print("Market Regime Features Engineereed.")
    
    # 2. Define Feature Set for V2
    # We Add 'Realized_Vol_20' and 'Trend_Momentum' to the inputs
    v2_features = ['Hour_Decimal', 'Losing_Streak', 'Drawdown_State', 
                   'Lot_Deviation', 'Revenge_Timer', 'Realized_Vol_20', 'Trend_Momentum']
    
    # 3. Train AI Risk Officer with new Context Awareness
    airo = AIRiskOfficer(features=v2_features)
    airo.train(df)
    
    # 4. Run Simulation Loop (Re-implementing simplified loop to ensure feature alignment)
    initial_equity = 100000.0
    real_equity = initial_equity
    shadow_equity = initial_equity
    shadow_curve = [initial_equity]
    
    intervention_log = []
    
    print(f"Simulating {len(df)} trades with Context Awareness...")
    
    for index, row in df.iterrows():
        pnl = row['PnL']
        
        # Consult AIRO
        assessment = airo.predict(row)
        decision = assessment['decision']
        
        if decision == "BLOCK":
            shadow_equity += 0
            # Log with explanation
            intervention_log.append({
                'Date': row['Open Time'],
                'Risk_Score': assessment['risk_prob'],
                'Reason': str(airo.get_explanation(row))
            })
        else:
            shadow_equity += pnl # Accept trade
            
        shadow_curve.append(shadow_equity)
        
    s_ret = (shadow_equity - initial_equity) / initial_equity * 100
    print(f"V2 Shadow Return: {s_ret:.2f}%")
    
    return s_ret, intervention_log

if __name__ == "__main__":
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    run_simulation_v2(filepath)
