"""
End-to-end test that bypasses MT5 auth by directly calling /v1/onboard/data
with empty trades — simulates what the bridge does on auth failure / no MT5.
Run from project root: python scratch/test_e2e_direct.py
"""
import asyncio
import httpx
import time

BASE_URL = "http://localhost:8000"
USER_ID = "sentinel-local-test"
BROKER_SERVER = "FTMO-Demo"
ACCOUNT_ID = "99999999"


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Step 1: Submit dummy credentials
        print("[1] Submitting credentials...")
        cred_resp = await client.post("/v1/credentials", json={
            "user_id": USER_ID,
            "broker_server": BROKER_SERVER,
            "account_id": ACCOUNT_ID,
            "read_only_password": "test-password-123",
        })
        print(f"    Status: {cred_resp.status_code} | {cred_resp.text[:80]}")

        # Step 2: Start onboarding
        print("[2] Starting onboarding...")
        onboard_resp = await client.post("/v1/onboard", json={
            "user_id": USER_ID,
            "broker_server": BROKER_SERVER,
            "account_id": ACCOUNT_ID,
            "min_trades": 20,
        })
        print(f"    Status: {onboard_resp.status_code}")
        onboard_data = onboard_resp.json()
        job_id = onboard_data.get("job_id")
        print(f"    Job ID: {job_id}")
        print(f"    State:  {onboard_data.get('state')}")

        # Step 3: Wait for bridge to dequeue job (max 10s)
        print("[3] Waiting for bridge to pick up job (10s)...")
        await asyncio.sleep(3)

        # Step 4: Simulate bridge callback — submit empty trades directly
        print("[4] Simulating bridge callback: POST /v1/onboard/data with 0 trades...")
        data_resp = await client.post("/v1/onboard/data", json={
            "job_id": job_id,
            "user_id": USER_ID,
            "trades": [],
        })
        print(f"    Status: {data_resp.status_code}")
        data = data_resp.json()
        print(f"    State:  {data.get('state')}")
        print(f"    Msg:    {data.get('message', '')[:100]}")

        # Step 5: Poll until complete
        print("[5] Polling for final state (30s)...")
        deadline = time.time() + 30
        last_state = None
        while time.time() < deadline:
            status_resp = await client.get(f"/v1/onboard/{job_id}")
            job = status_resp.json()
            state = job.get("state")
            if state != last_state:
                print(f"    [{time.strftime('%H:%M:%S')}] state={state} | {job.get('message','')[:80]}")
                last_state = state
            if state in ("complete", "failed", "error", "blank_baseline", "ready"):
                print(f"\n[SUCCESS] ONBOARDING COMPLETE! Final state: {state}")
                print(f"   Trade count: {job.get('trade_count')}")
                print(f"   Message: {job.get('message')}")
                break
            await asyncio.sleep(2.0)
        else:
            print(f"\n⚠️  Timed out. Last state: {last_state}")

        # Step 6: Check dashboard
        print("\n[6] Fetching user dashboard...")
        dash_resp = await client.get(f"/v1/user/{USER_ID}/dashboard")
        if dash_resp.status_code == 200:
            dash = dash_resp.json()
            profile = dash.get("profile", {})
            print(f"    trade_count:       {profile.get('trade_count')}")
            print(f"    is_baseline_ready: {profile.get('is_baseline_ready')}")
            print(f"    maturity_state:    {profile.get('maturity_state')}")
            print(f"    blank_baseline:    {dash.get('blank_baseline')}")
        else:
            print(f"    Dashboard error: {dash_resp.status_code}")


if __name__ == "__main__":
    asyncio.run(main())
