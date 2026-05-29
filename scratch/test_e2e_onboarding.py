"""
End-to-end test: submits credentials + starts onboarding job, then polls status.
Run from the project root with: python scratch/test_e2e_onboarding.py
"""
import asyncio
import httpx
import time

BASE_URL = "http://localhost:8000"
USER_ID = "ftmo-test-user"
BROKER_SERVER = "FTMO-Demo"
ACCOUNT_ID = "1513523195"
PASSWORD = "Hfr@43243434349"  # Replace with actual FTMO password if needed


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # Step 1: Submit credentials
        print("[1] Submitting credentials...")
        cred_resp = await client.post("/v1/credentials", json={
            "user_id": USER_ID,
            "broker_server": BROKER_SERVER,
            "account_id": ACCOUNT_ID,
            "read_only_password": PASSWORD,
        })
        print(f"    Credentials: {cred_resp.status_code} {cred_resp.text[:100]}")

        # Step 2: Start onboarding
        print("[2] Starting onboarding...")
        onboard_resp = await client.post("/v1/onboard", json={
            "user_id": USER_ID,
            "broker_server": BROKER_SERVER,
            "account_id": ACCOUNT_ID,
            "min_trades": 20,
        })
        print(f"    Onboard: {onboard_resp.status_code}")
        onboard_data = onboard_resp.json()
        job_id = onboard_data.get("job_id")
        print(f"    Job ID: {job_id}")
        print(f"    State: {onboard_data.get('state')}")
        print(f"    Message: {onboard_data.get('message')}")

        # Step 3: Poll status
        print("[3] Polling job status (60s max)...")
        deadline = time.time() + 60
        last_state = None
        while time.time() < deadline:
            status_resp = await client.get(f"/v1/onboard/{job_id}")
            data = status_resp.json()
            state = data.get("state")
            msg = data.get("message", "")
            if state != last_state:
                print(f"    [{time.strftime('%H:%M:%S')}] state={state} msg={msg[:80]}")
                last_state = state
            if state in ("complete", "failed", "error"):
                print(f"[4] FINAL STATE: {state}")
                print(f"    Trade count: {data.get('trade_count')}")
                break
            await asyncio.sleep(2.0)
        else:
            print(f"[4] TIMED OUT. Last state: {last_state}")

        # Step 4: Check SQLite queue state
        import sqlite3
        conn = sqlite3.connect("redis_fallback.db")
        queue_rows = conn.execute("SELECT id, key, substr(value, 1, 60) FROM queue").fetchall()
        print(f"[5] Queue remaining: {queue_rows}")
        conn.close()


if __name__ == "__main__":
    asyncio.run(main())
