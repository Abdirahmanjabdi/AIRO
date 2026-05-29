"""
Full bridge-in-the-loop E2E test.
Tests that the bridge relay automatically picks up the job and submits empty trades.
Run from project root: python scratch/test_bridge_e2e.py
"""
import asyncio
import httpx
import time

BASE_URL = "http://localhost:8000"
USER_ID = "bridge-loop-test"
BROKER_SERVER = "FTMO-Demo"
ACCOUNT_ID = "00000001"


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Step 1: Submit credentials
        print("[1] Submitting credentials...")
        cred_resp = await client.post("/v1/credentials", json={
            "user_id": USER_ID,
            "broker_server": BROKER_SERVER,
            "account_id": ACCOUNT_ID,
            "read_only_password": "bridge-test-pass",
        })
        assert cred_resp.status_code == 200, f"Creds failed: {cred_resp.text}"
        print(f"    OK: {cred_resp.json()['stored']}")

        # Step 2: Start onboarding
        print("[2] Starting onboarding...")
        onboard_resp = await client.post("/v1/onboard", json={
            "user_id": USER_ID,
            "broker_server": BROKER_SERVER,
            "account_id": ACCOUNT_ID,
            "min_trades": 10,
        })
        assert onboard_resp.status_code == 202, f"Onboard failed: {onboard_resp.text}"
        job_id = onboard_resp.json()["job_id"]
        print(f"    Job ID: {job_id}")

        # Step 3: Poll — bridge should auto-process within 20s (15s MT5 timeout + margin)
        print("[3] Waiting for bridge to auto-process job (45s max)...")
        deadline = time.time() + 45
        last_state = None
        while time.time() < deadline:
            status_resp = await client.get(f"/v1/onboard/{job_id}")
            job = status_resp.json()
            state = job.get("state")
            if state != last_state:
                elapsed = int(45 - (deadline - time.time()))
                print(f"    [+{elapsed:02d}s] state={state} | {job.get('message','')[:70]}")
                last_state = state
            if state in ("complete", "failed", "error", "blank_baseline", "ready"):
                print(f"\n[PASS] Bridge processed job! Final state: {state}")
                print(f"       Trade count: {job.get('trade_count')}")
                return
            await asyncio.sleep(2.0)

        print(f"\n[FAIL] Bridge did NOT process job within 45s. Last state: {last_state}")
        print("       Check that the bridge relay is running: python -m sentinel.bridge.mt5_relay")


if __name__ == "__main__":
    asyncio.run(main())
