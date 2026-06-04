"""
Sentinel Trading — End-to-End Local Fire Drill Simulation
=========================================================
Run this script to simulate a user onboarding and taking 5 terrible trades
sequentially, causing the risk engine to trigger a Guillotine BLOCK decision.

Pre-requisites:
1. Start the FastAPI backend:
   python -m uvicorn src.sentinel.api.main:app --host 127.0.0.1 --port 8000 --reload
2. Start the React frontend:
   cd frontend
   npm run dev
3. Open the frontend in your browser (usually http://localhost:5173).
"""

import time
import httpx

API_URL = "http://127.0.0.1:8000"
USER_ID = "vanguard_fire_drill"

def run_fire_drill():
    print("[INIT] Starting Sentinel Trading End-to-End Local Fire Drill...\n")
    
    # 1. Onboard the user
    print(f"[STEP 1] Onboarding user '{USER_ID}' with typical Risk DNA survey...")
    onboard_payload = {
        "user_id": USER_ID,
        "broker_server": "ICMarkets-Demo",
        "account_id": "999999",
        "min_trades": 20,
        "initial_parameters": {
            "max_drawdown_pct": 3.0,
            "primary_instrument": "EURUSD",
            "trading_style": "intraday",
            "typical_daily_trades": 8,
            "typical_lot_size": 1.0,
            "average_win_hold_minutes": 60.0,
            "tilt_response": "wait_for_setup",
            "loss_review_threshold": 3,
            "max_lot_multiplier": 2.0
        }
    }
    
    try:
        resp = httpx.post(f"{API_URL}/v1/onboard", json=onboard_payload, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        api_key = data.get("api_key")
        print(f"[OK] Onboarding job queued! Job ID: {data.get('job_id')}")
        print(f"[INFO] API Key issued: {api_key[:12]}...\n")
    except Exception as e:
        print(f"[ERROR] Onboarding failed: {e}")
        print("[INFO] Make sure your FastAPI backend is running on http://127.0.0.1:8000")
        return

    # 1.5. Submit historical trade data to trigger baseline model training
    print("[STEP 1.5] Submitting 25 historical trades to fast-track baseline model training...")
    from datetime import datetime, timedelta
    
    historical_trades = []
    base_time = datetime.utcnow() - timedelta(days=10)
    for i in range(25):
        open_time = base_time + timedelta(hours=i * 4)
        close_time = open_time + timedelta(minutes=45)
        historical_trades.append({
            "symbol": "EURUSD",
            "open_time": open_time.isoformat() + "Z",
            "close_time": close_time.isoformat() + "Z",
            "pnl": 50.0 if i % 2 == 0 else -30.0,
            "lots": 1.0,
            "open_price": 1.1000,
            "close_price": 1.1050 if i % 2 == 0 else 1.0970,
            "rr_ratio": 1.5
        })
        
    onboard_data_payload = {
        "job_id": data.get("job_id"),
        "user_id": USER_ID,
        "trades": historical_trades
    }
    
    try:
        headers = {"X-API-Key": api_key} if api_key else {}
        data_resp = httpx.post(f"{API_URL}/v1/onboard/data", json=onboard_data_payload, headers=headers, timeout=10.0)
        data_resp.raise_for_status()
        print("[OK] Historical trades submitted! Model training triggered.")
    except Exception as e:
        print(f"[ERROR] Historical data submission failed: {e}")
        return
        
    # Wait a few seconds for the background training to complete
    print("[INFO] Waiting 3 seconds for background model training to finalize...")
    time.sleep(3.0)

    # Simulate 5 trades sequentially representing a rapid tilt sequence
    trades = [
        {
            "description": "Trade 1: Standard trade within expected bounds.",
            "lots": 1.0,
            "losing_streak": 0,
            "drawdown_state": 0.0,
            "revenge_timer": 3600.0,
            "rr_ratio": 2.0
        },
        {
            "description": "Trade 2: Immediate re-entry with standard size (revenge signature).",
            "lots": 1.0,
            "losing_streak": 1,
            "drawdown_state": 0.005,
            "revenge_timer": 45.0, # Revenge timer low!
            "rr_ratio": 2.0
        },
        {
            "description": "Trade 3: Quick re-entry, slight increase in lot size.",
            "lots": 1.5, # Size deviation!
            "losing_streak": 2,
            "drawdown_state": 0.015,
            "revenge_timer": 20.0,
            "rr_ratio": 1.8
        },
        {
            "description": "Trade 4: Furious re-entry, lot size exceeds limits.",
            "lots": 2.5, # Violates 2.0x lot multiplier limit!
            "losing_streak": 3, # Hits loss review threshold!
            "drawdown_state": 0.025,
            "revenge_timer": 12.0,
            "rr_ratio": 1.5
        },
        {
            "description": "Trade 5: Total Tilt! Maximum drawdown exceeded, huge lot deviation, instant re-entry.",
            "lots": 3.5, # Major deviation!
            "losing_streak": 4, # Exceeds limit!
            "drawdown_state": 0.038, # Exceeds 3% drawdown limit!
            "revenge_timer": 5.0, # Immediate reentry!
            "rr_ratio": 1.0
        }
    ]

    for i, trade in enumerate(trades, 1):
        print(f"[STEP 2.{i}] {trade['description']}")
        payload = {
            "user_id": USER_ID,
            "symbol": "EURUSD",
            "hour_decimal": 14.5,
            "losing_streak": trade["losing_streak"],
            "drawdown_state": trade["drawdown_state"],
            "lot_deviation": float(trade["lots"] - 1.0) / 0.25, # Derived lot deviation score
            "revenge_timer": trade["revenge_timer"],
            "lots": trade["lots"],
            "rr_ratio": trade["rr_ratio"],
            "realized_vol_20": 0.015,
            "trend_momentum": 0.005
        }
        
        try:
            headers = {"X-API-Key": api_key} if api_key else {}
            analyze_resp = httpx.post(f"{API_URL}/v1/analyze", json=payload, headers=headers, timeout=5.0)
            analyze_resp.raise_for_status()
            result = analyze_resp.json()
            
            decision = result["decision"]
            score = result["risk_score"]
            multiplier = result["size_multiplier"]
            
            status_indicator = "[ALLOW]" if decision == "ALLOW" else "[REDUCE_SIZE]" if decision == "REDUCE_SIZE" else "[BLOCK]"
            print(f"   -> Decision: {status_indicator} | Risk Score: {score:.4f} | Size Multiplier: {multiplier:.2f}")
            
            if decision == "BLOCK":
                print("\n[WARNING] GUILLOTINE DROP CONFIRMED!")
                print("   -> The Sentinel Risk Engine has blocked active trading execution due to high-risk behavioral anomalies.")
            
            time.sleep(1.0)
        except Exception as e:
            print(f"   [ERROR] Analyze request failed: {e}")
            return

    print("\n[SUCCESS] Fire drill simulation complete on the backend!")
    print("=========================================================================")
    print("Next Verification Steps in Frontend:")
    print("1. Log in to the React CommandCenter with User ID 'vanguard_fire_drill'.")
    print("2. The dashboard will instantly display a full-screen, unignorable red LOCKOUT overlay.")
    print("3. Verify the 15-minute countdown clock is ticking.")
    print("4. Try refreshing the page — the countdown will survive and lock the screen!")
    print("5. Once the countdown expires, choose 'Valid Intercept' or 'False Positive'.")
    print("6. Verify that your SQLite MLflow tracking server logs the retrained weights!")
    print("=========================================================================\n")

if __name__ == "__main__":
    run_fire_drill()
