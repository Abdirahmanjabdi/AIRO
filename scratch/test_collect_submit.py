"""
Direct test of the collect_and_submit flow.
Run from project root: python scratch/test_collect_submit.py
"""
import asyncio
import sys

sys.path.insert(0, "src")

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

async def main():
    print("[TEST] Importing MT5HistoryBridge...")
    from sentinel.bridge.mt5_history import MT5HistoryBridge, mt5
    print(f"[TEST] mt5 module: {mt5}")
    
    bridge = MT5HistoryBridge("http://localhost:8000")
    print(f"[TEST] api_base_url: {bridge.api_base_url}")
    
    # Use the job ID from the last test run
    job_id = "dea56aab-3f2f-4b57-9fd2-cdab2cb2b1d1"
    user_id = "ftmo-test-user"
    
    print(f"[TEST] Calling collect_and_submit for job {job_id}...")
    try:
        await bridge.collect_and_submit(
            job_id=job_id,
            user_id=user_id,
            broker_server="FTMO-Demo",
            account_id="1513523195",
            limit=20,
        )
        print("[TEST] collect_and_submit completed OK!")
    except Exception as exc:
        print(f"[TEST] ERROR: {exc}")
        import traceback
        traceback.print_exc()
    
    print("[TEST] Checking job status via API...")
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        resp = await client.get(f"/v1/onboard/{job_id}")
        print(f"[TEST] Job status: {resp.status_code} {resp.text[:200]}")

if __name__ == "__main__":
    asyncio.run(main())
