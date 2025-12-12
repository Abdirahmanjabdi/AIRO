from simulation import run_simulation
from data_processor import DataLoader
from ai_ultimate import AIUltimate
import pandas as pd
import numpy as np

def run_simulation_ultimate(filepath):
    print("--- Starting THE ULTIMATE ENTITY Simulation ---")
    print("Architecture: V2 Context + V3 Optimized Params + V4 Active Sizing")
    
    # 1. Load Data (V2 Deep Context)
    loader = DataLoader(filepath)
    loader.load_data()
    loader.engineer_features()
    df = loader.engineer_context_features()
    
    # 2. Train Ultimate Agent (V3 Params)
    agent = AIUltimate()
    agent.train(df)
    
    # 3. Run Simulation (V4 Logic)
    initial_equity = 100000.0
    active_equity = initial_equity
    active_curve = [initial_equity]
    
    total_exposure = 0
    trade_count = 0
    
    print(f"Simulating {len(df)} trades...")
    
    for index, row in df.iterrows():
        pnl = row['PnL']
        
        # Get Optimized Sizer
        size_multiplier, risk = agent.get_position_sizer(row)
        
        total_exposure += size_multiplier
        trade_count += 1
        
        # PnL Impact
        active_pnl = pnl * size_multiplier
        active_equity += active_pnl
        active_curve.append(active_equity)
        
    avg_size = total_exposure / trade_count if trade_count > 0 else 0
    total_return = (active_equity - initial_equity) / initial_equity * 100
    
    print(f"\n>>> ULTIMATE RETURN: {total_return:.2f}%")
    print(f">>> Avg Trade Size: {avg_size:.2f}x")
    
    return total_return

if __name__ == "__main__":
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    run_simulation_ultimate(filepath)
