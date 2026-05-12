import redis
import json
import time
import requests
import datetime
import random

r = redis.Redis(host='localhost', port=6379, db=0)
queue_name = b'sentinel:onboarding:queue'

print("Starting Mock MT5 Bridge...")
print(f"Listening on Redis queue: {queue_name.decode()}")

while True:
    item = r.blpop(queue_name, timeout=5)
    if item:
        _, raw = item
        job = json.loads(raw)
        job_id = job.get("job_id")
        user_id = job.get("user_id")
        min_trades = job.get("min_trades", 100)
        
        print(f"Received job {job_id} for user {user_id}. Simulating {min_trades} trades...")
        
        # Simulate processing time
        time.sleep(2)
        
        trades = []
        now = datetime.datetime.utcnow()
        for i in range(min_trades):
            open_time = now - datetime.timedelta(days=10) + datetime.timedelta(hours=i)
            close_time = open_time + datetime.timedelta(minutes=random.randint(5, 60))
            trades.append({
                "symbol": "XAUUSD",
                "open_time": open_time.isoformat() + "Z",
                "close_time": close_time.isoformat() + "Z",
                "pnl": round(random.uniform(-100, 200), 2),
                "lots": round(random.uniform(0.1, 2.0), 2),
                "open_price": 2000.0,
                "close_price": 2000.0 + random.uniform(-10, 10),
                "rr_ratio": round(random.uniform(0.5, 3.0), 2)
            })
            
        payload = {
            "job_id": job_id,
            "user_id": user_id,
            "trades": trades
        }
        
        print(f"Sending {len(trades)} trades to backend...")
        try:
            resp = requests.post("http://localhost:8000/v1/onboard/data", json=payload)
            resp.raise_for_status()
            print("Successfully sent data to backend!")
            print("Response:", resp.json())
        except Exception as e:
            print("Failed to send data to backend:", e)
            if hasattr(e, 'response') and e.response is not None:
                print(e.response.text)
