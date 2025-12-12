from simulation import run_simulation
from data_processor import DataLoader
from ai_agent_v4 import ActiveAgent
import pandas as pd
import numpy as np

def run_simulation_v4(filepath):
    print("--- Starting V4 Active Agent Simulation (RL Concept) ---")
    
    # 1. Load Data
    loader = DataLoader(filepath)
    loader.load_data()
    df = loader.engineer_features()
    # (Optional: Use V2 Context features if desired, but let's stick to V1 features for fair comparison to V1 Baseline)
    
    # 2. Train Agent
    agent = ActiveAgent()
    agent.train(df)
    
    # 3. Simulation Loop
    initial_equity = 100000.0
    real_equity = initial_equity
    active_equity = initial_equity
    
    active_curve = [initial_equity]
    
    print(f"Simulating {len(df)} trades with Dynamic Sizing...")
    
    total_exposure = 0
    
    for index, row in df.iterrows():
        pnl = row['PnL']
        
        # Get Sizer
        size_multiplier, risk = agent.get_position_sizer(row)
        total_exposure += size_multiplier
        
        # Active PnL = Real PnL * Multiplier
        active_pnl = pnl * size_multiplier
        
        active_equity += active_pnl
        active_curve.append(active_equity)
        
    avg_size = total_exposure / len(df)
    active_return = (active_equity - initial_equity) / initial_equity * 100
    
    print(f"\nV4 Active Return: {active_return:.2f}%")
    print(f"Average Position Size: {avg_size:.2f} (vs 1.0)")
    
    return active_return

if __name__ == "__main__":
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    run_simulation_v4(filepath)
