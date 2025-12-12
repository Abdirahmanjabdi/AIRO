import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from simulation_ultimate import run_simulation_ultimate
from data_processor import DataLoader
from ai_ultimate import AIUltimate

def generate_assets():
    print("Generating GitHub Assets...")
    
    # 1. Run Simulation to get Data
    filepath = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
    loader = DataLoader(filepath)
    loader.load_data()
    df = loader.engineer_features()
    df = loader.engineer_context_features()
    
    agent = AIUltimate()
    agent.train(df)
    
    # Re-run simulation logic for curve
    initial = 100000
    real_curve = [initial]
    shadow_curve = [initial]
    curr_real = initial
    curr_shadow = initial
    
    for _, row in df.iterrows():
        pnl = row['PnL']
        curr_real += pnl
        
        mult, _ = agent.get_position_sizer(row)
        curr_shadow += (pnl * mult)
        
        real_curve.append(curr_real)
        shadow_curve.append(curr_shadow)
        
    # 2. Plot Equity Curve
    plt.figure(figsize=(12, 6))
    plt.style.use('dark_background')
    
    plt.plot(shadow_curve, label='AIRO Ultimate (AI-Governed)', color='#FFD700', linewidth=2)
    plt.plot(real_curve, label='Human (Unmanaged)', color='#00BFFF', linewidth=1.5, alpha=0.7)
    
    plt.title('AIRO Performance: Human vs AI Governance', fontsize=16)
    plt.ylabel('Account Equity ($)', fontsize=12)
    plt.xlabel('Trade Count', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.2)
    
    plt.savefig('equity_comparison.png', dpi=300, bbox_inches='tight')
    print("Saved 'equity_comparison.png'")
    
    # 3. Plot Feature Importance
    plt.figure(figsize=(10, 6))
    plt.style.use('dark_background')
    
    importances = agent.classifier.feature_importances_
    features = agent.features
    
    # Sort
    sorted_idx = np.argsort(importances)
    pos = np.arange(sorted_idx.shape[0]) + .5
    
    plt.barh(pos, importances[sorted_idx], align='center', color='#00FF7F')
    plt.yticks(pos, np.array(features)[sorted_idx])
    plt.title('Behavioral Feature Importance (Why Traders Fail)', fontsize=14)
    plt.xlabel('Relative Importance')
    
    plt.savefig('feature_importance.png', dpi=300, bbox_inches='tight')
    print("Saved 'feature_importance.png'")

if __name__ == "__main__":
    generate_assets()
