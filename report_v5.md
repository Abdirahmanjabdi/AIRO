# AIRO Version 5 Report: The Live Bridge ("Nervous System")

## 🎯 The Objective
Simulation is theory. **AIRO V5 ("Nervous System")** is practice. This module exposes the AI logic via a REST API, allowing *any* trading platform (MetaTrader 5, cTrader, Python Scripts) to consult the AI Risk Officer in real-time.

## ⚙️ Methodology: Microservice Architecture
We wrapped the V4 Active Agent in a `FastAPI` container.

**The Workflow:**
1.  **Trader** clicks "Buy" on MT5.
2.  **EA** intercepts the click and sends account stats (Drawdown, Streak) to `http://localhost:8000/analyze_trade`.
3.  **AIRO API** runs the Random Forest model in <50ms.
4.  **AIRO API** responds: `{"decision": "REDUCE_SIZE", "size_multiplier": 0.5}`.
5.  **EA** executes the trade at half size.

## 🚀 How to Run locally
1.  Start the server:
    ```bash
    python server_v5.py
    ```
2.  Send a test POST request (e.g., via Postman or Python):
    ```json
    {
      "Hour_Decimal": 14.5,
      "Losing_Streak": 3,
      "Drawdown_State": 6.0,
      "Lot_Deviation": 2.5,
      "Revenge_Timer": 5
    }
    ```
3.  Receive Response:
    ```json
    {
        "decision": "BLOCK",
        "risk_score": 0.88,
        "size_multiplier": 0.0
    }
    ```

## 🏆 Key Takeaway
This is the "Endgame" architecture. The AI is no longer a tool you look at; it is a gatekeeper that lives between you and the market.
