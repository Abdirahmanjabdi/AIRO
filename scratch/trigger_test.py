import time
import httpx

API_URL = "http://127.0.0.1:8000"
USER_ID = "test-user-01"

def trigger_onboarding():
    print("[INIT] Submitting connection credentials for FTMO-Demo...")
    
    # First submit the credentials
    cred_payload = {
        "user_id": USER_ID,
        "broker_server": "FTMO-Demo",
        "account_id": "1513523195",
        "read_only_password": "6@*U4hJT3$"
    }
    
    try:
        resp = httpx.post(f"{API_URL}/v1/credentials", json=cred_payload, timeout=10.0)
        resp.raise_for_status()
        print("[OK] Credentials stored successfully in Vault fallback!")
    except Exception as e:
        print(f"[ERROR] Failed to store credentials: {e}")
        return

    # Now trigger onboarding
    onboard_payload = {
        "user_id": USER_ID,
        "broker_server": "FTMO-Demo",
        "account_id": "1513523195",
        "min_trades": 20,
        "initial_parameters": {
            "max_drawdown_pct": 2.0,
            "primary_instrument": "GBPUSD",
            "trading_style": "intraday",
            "typical_daily_trades": 2,
            "typical_lot_size": 20.0,
            "average_win_hold_minutes": 120.0,
            "tilt_response": "wait_for_setup",
            "loss_review_threshold": 2,
            "max_lot_multiplier": 1.5
        }
    }
    
    try:
        resp = httpx.post(f"{API_URL}/v1/onboard", json=onboard_payload, timeout=10.0)
        resp.raise_for_status()
        job_data = resp.json()
        job_id = job_data.get("job_id")
        print(f"[OK] Onboarding job successfully queued! Job ID: {job_id}\n")
    except Exception as e:
        print(f"[ERROR] Onboarding failed: {e}")
        return

    # Poll status
    print("--- Polling Onboarding Job Status ---")
    for i in range(30):
        try:
            status_res = httpx.get(f"{API_URL}/v1/onboard/{job_id}", timeout=5.0)
            status_data = status_res.json()
            print(f"Poll {i+1}: State = {status_data['state']} | Message = {status_data['message']}")
            if status_data.get("state") in {"ready", "blank_baseline"}:
                print("\n[SUCCESS] Onboarding finalized successfully! Baseline Model Built and promoted.")
                return
            elif status_data.get("state") == "failed":
                print(f"\n[FAILED] Onboarding failed with detail: {status_data.get('error_detail')}")
                return
        except Exception as e:
            print(f"Polling error: {e}")
        time.sleep(2)

if __name__ == "__main__":
    trigger_onboarding()
