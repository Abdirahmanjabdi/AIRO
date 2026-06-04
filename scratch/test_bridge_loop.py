import asyncio
import json
import logging
import sys
import os

# Set python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sentinel.infra.redis_cache import cache_manager, InMemoryRedis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)

async def test_loop():
    print("[INIT] Starting Diagnostic Bridge Loop...")
    print(f"[INIT] cache_manager.r = {cache_manager.r}")
    
    # Swap to SQLite fallback manually
    print("[INIT] Swapping cache_manager.r to SQLite InMemoryRedis fallback...")
    cache_manager.r = InMemoryRedis()
    print(f"[INIT] Swapped: {cache_manager.r} (db_path = {cache_manager.r.db_path})")

    from sentinel.bridge.mt5_history import MT5HistoryBridge
    history_bridge = MT5HistoryBridge("http://localhost:8000")

    while True:
        print("[LOOP] Checking onboarding queue...")
        try:
            command = await cache_manager.dequeue_onboarding_job(timeout_seconds=2)
            if command is not None:
                print(f"[JOB] Dequeued onboarding job! payload = {json.dumps(command)}")
                user_id = str(command["user_id"])
                job_id = str(command["job_id"])
                
                print(f"[JOB] Setting presence heartbeat for user {user_id}")
                await cache_manager.set_heartbeat(user_id)
                
                print(f"[JOB] Collecting and submitting MT5 history for user {user_id}...")
                await history_bridge.collect_and_submit(
                    job_id=job_id,
                    user_id=user_id,
                    broker_server=str(command["broker_server"]),
                    account_id=str(command["account_id"]),
                    limit=int(command.get("min_trades", 100)),
                )
                print(f"[JOB] Onboarding history collection completed successfully!")
            else:
                print("[LOOP] Queue is empty.")
        except Exception as e:
            print(f"[ERROR] Exception in loop: {e}")
            import traceback
            traceback.print_exc()

        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(test_loop())
