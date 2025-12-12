# AIRO "Grand Architecture" Implementation Plan

## Goal Description
Build 5 distinct versions of the AI Risk Officer to demonstrate the evolution from simple rules to an optimized, context-aware, active AI agent. Each version will be a standalone "entity" with its own report.

## The 5 Entities
1.  **V1: The Baseline (Shadow Ledger)** [DONE]
    - *Tech:* IsolationForest, RandomForest.
    - *Goal:* Verify basic "Block/Allow" concept.
2.  **V2: Deep Context (Market Regime)**
    - *Upgrade:* Adds Volatility (ATR) and Trend (ADX) awareness.
    - *Goal:* Stop blocking trades when volatility is favourable.
3.  **V3: The Optimizer (Hyperparameter Tuning)**
    - *Upgrade:* Uses `Optuna` to find the perfect Thresholds (e.g., Block if Risk > 68% instead of 70%).
    - *Goal:* Mathematically maximize Sharpe Ratio.
4.  **V4: The Active Agent (Reinforcement Learning)**
    - *Upgrade:* Uses Contextual Bandits (partial RL) to output a "Position Sizer" (0.0 - 1.0) instead of binary Block.
    - *Goal:* Smooth the equity curve by reducing size in uncertainty.
5.  **V5: The Live Bridge (Nervous System)**
    - *Upgrade:* FastAPI/Flask Server to accept webhooks from MT5.
    - *Goal:* Production-ready architecture.

## Proposed Changes (Sequential Execution)

### Phase 1: V2 Deep Context (The Data Upgrade)
#### [MODIFY] [data_processor.py](file:///c:/Users/jamaa/OneDrive/Documents/AIRO/data_processor.py)
- Add `engineer_context_features()` method:
    - `ATR_14`: Volatility metric.
    - `ADX_14`: Trend Strength metric.
    - `Regime`: Categorical (Trending/Ranging).

#### [NEW] [simulation_v2_context.py](file:///c:/Users/jamaa/OneDrive/Documents/AIRO/simulation_v2_context.py)
- Runs the simulation using the new extended feature set.

### Phase 2: V3 The Optimizer (The Math Upgrade)
#### [NEW] [optimizer_v3.py](file:///c:/Users/jamaa/OneDrive/Documents/AIRO/optimizer_v3.py)
- Uses `optuna` library.
- Objective Function: Maximize `Sharpe_Ratio` or `Total_Return`.
- Parameters to tune: `contamination` (IsoForest), `n_estimators` (RandomForest), `Block_Threshold`.

### Phase 3: V4 The Active Agent (The Logic Upgrade)
#### [NEW] [ai_agent_v4.py](file:///c:/Users/jamaa/OneDrive/Documents/AIRO/ai_agent_v4.py)
- New Logic: `get_position_size(trade_row)`
- Instead of `if risk > 0.7: block`, logic is `size_multiplier = 1.0 - risk_score`.
- Creates a "Variable Exposure" equity curve.

### Phase 4: V5 The Live Bridge (The Infrastructure Upgrade)
#### [NEW] [server_v5.py](file:///c:/Users/jamaa/OneDrive/Documents/AIRO/server_v5.py)
- `FastAPI` app with endpoint `/analyze_trade`.
- Accepts JSON payload (Trade params).
- returns JSON `{ "decision": "ALLOW", "size_modifier": 0.8 }`.

## Verification Plan
- For each Version, generate a `report_vX.md` containing:
    - Tech Stack.
    - How it works.
    - Performance vs Baseline.
