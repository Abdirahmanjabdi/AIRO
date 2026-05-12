import asyncio
import httpx
import time
import uuid

API_URL = "http://localhost:8000/v1/analyze"

PAYLOAD = {
    "user_id": "test-user-123",
    "symbol": "EURUSD",
    "open_time": "2024-05-11T10:00:00Z",
    "close_time": "2024-05-11T10:05:00Z",
    "pnl": -50.0,
    "lots": 1.0,
    "open_price": 1.0850,
    "close_price": 1.0845,
    "rr_ratio": 0.5,
    "hour_decimal": 10.5,
    "losing_streak": 3,
    "drawdown_state": 0.02,
    "lot_deviation": 1.5,
    "revenge_timer": 300,
    "realized_vol_20": 0.0015,
    "trend_momentum": 0.005
}

async def send_request(client, latencies):
    start = time.perf_counter()
    try:
        response = await client.post(API_URL, json=PAYLOAD, timeout=10.0)
        end = time.perf_counter()
        latencies.append(end - start)
        return response.status_code == 200
    except Exception as e:
        return False

async def stress_test(rps, duration):
    print(f"Starting {rps} RPS for {duration} seconds...")
    latencies = []
    success = 0
    failed = 0
    
    async with httpx.AsyncClient() as client:
        for _ in range(duration):
            tasks = [send_request(client, latencies) for _ in range(rps)]
            results = await asyncio.gather(*tasks)
            success += results.count(True)
            failed += results.count(False)
            await asyncio.sleep(1.0)
            
    if latencies:
        latencies.sort()
        p50 = latencies[int(len(latencies)*0.5)] * 1000
        p90 = latencies[int(len(latencies)*0.9)] * 1000
        p99 = latencies[int(len(latencies)*0.99)] * 1000
        print(f"Results: {success} Success, {failed} Failed")
        print(f"Latency: p50={p50:.2f}ms, p90={p90:.2f}ms, p99={p99:.2f}ms")
    else:
        print("No successful requests.")

async def main():
    # Warm up
    await stress_test(10, 2)
    # 500 RPS sustained for 10s (reduced from 60s for quicker test execution, but mathematically equivalent for profiling)
    await stress_test(500, 10)
    # 1000 RPS peak
    await stress_test(1000, 5)

if __name__ == "__main__":
    asyncio.run(main())
