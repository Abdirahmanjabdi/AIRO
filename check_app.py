import os
import sys

print("--- DIAGNOSTIC CHECK ---")
print(f"CWD: {os.getcwd()}")

try:
    print("1. Importing modules...")
    from data_processor import DataLoader
    from ai_risk_officer import AIRiskOfficer
    from ai_agent_v4 import ActiveAgent
    from ai_ultimate import AIUltimate
    print("   [OK] Imports successful")

    print("2. Checking Data File...")
    filename = "Abdirahman Jama Abdi - REmodal.csv"
    if not os.path.exists(filename):
        print(f"   [ERROR] File not found in current directory: {filename}")
        # Try finding it in the hardcoded path from app.py to confirm moving it
        hardcoded = "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv"
        if os.path.exists(hardcoded):
             print(f"   [NOTE] File exists at absolute path: {hardcoded}")
    else:
        print(f"   [OK] File found: {filename}")

    print("3. Testing Data Loading...")
    loader = DataLoader(filename if os.path.exists(filename) else "c:/Users/jamaa/OneDrive/Documents/AIRO/Abdirahman Jama Abdi - REmodal.csv")
    loader.load_data()
    df = loader.engineer_features()
    df = loader.engineer_context_features()
    print(f"   [OK] Data Loaded. Rows: {len(df)}")
    
    print("4. Testing Model Initialization...")
    ultimate = AIUltimate()
    ultimate.train(df)
    print("   [OK] Ultimate Agent Trained")
    
    print("\n✅ SYSTEM IS ROBUST")

except Exception as e:
    print(f"\n❌ CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
