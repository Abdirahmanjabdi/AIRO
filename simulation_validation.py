from ai_ultimate import AIUltimate
from data_processor import DataLoader
import pandas as pd
import numpy as np

def run_validation(filepath):
    print("--- Starting Out-of-Sample Validation (70/30 Split) ---")
    
    # 1. Load All Data
    loader = DataLoader(filepath)
    loader.load_data()
    df = loader.engineer_features()
    df = loader.engineer_context_features()
    
    # 2. Time Series Split
    # We do NOT shuffle. We respect time.
    split_idx = int(len(df) * 0.70)
    
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    print(f"Total Trades: {len(df)}")
    print(f"Training Set: {len(train_df)} trades (First 70%)")
    print(f"Testing Set:  {len(test_df)} trades (Last 30% - UNSEEN DATA)")
    
    # 3. Train on PAST Data only
    agent = AIUltimate()
    print("Training Agent on Past Data...")
    agent.train(train_df)
    
    # 4. Simulate on FUTURE Data (Test Set)
    print("Simulating on Future Data...")
    
    initial_equity = 100000.0
    
    # Baseline (Unmanaged) Performance on Test Set
    real_pnl_sum = test_df['PnL'].sum()
    real_final = initial_equity + real_pnl_sum
    real_return = (real_final - initial_equity) / initial_equity * 100
    
    # AI Performance on Test Set
    shadow_equity = initial_equity
    shadow_curve = [initial_equity]
    
    exposure_sum = 0
    interventions = 0
    
    for index, row in test_df.iterrows():
        pnl = row['PnL']
        
        # Ask Agent (Who has never seen this specific trade before)
        size_multiplier, risk = agent.get_position_sizer(row)
        
        if size_multiplier < 1.0:
            interventions += 1
        
        shadow_pnl = pnl * size_multiplier
        shadow_equity += shadow_pnl
        shadow_curve.append(shadow_equity)
        exposure_sum += size_multiplier
        
    shadow_return = (shadow_equity - initial_equity) / initial_equity * 100
    avg_exposure = exposure_sum / len(test_df)
    
    print("\n--- Validation Results (Out-of-Sample) ---")
    print(f"Real Return (Test Set):   {real_return:.2f}%")
    print(f"AIRO Return (Test Set):   {shadow_return:.2f}%")
    print(f"Alpha Generated:          {shadow_return - real_return:.2f}%")
    print(f"Interventions / Trades:   {interventions} / {len(test_df)}")
    print(f"Avg Exposure:             {avg_exposure:.2f}x")
    
    return shadow_return, real_return

if __name__ == "__main__":
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    run_validation(filepath)
