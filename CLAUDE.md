# Sentinel Trading (AIRO) Development Workspace Guide

Welcome to the Sentinel Trading codebase. This document outlines the build/test commands, project layout, and the 9 core behavioral columns driving our ML threat detection model.

---

## 🛠️ Commands & Operational Workflows

### Build & Compilation
*   **Frontend Typecheck:** `cd frontend && npx tsc --noEmit`
*   **Frontend Development Server:** `cd frontend && npm run dev`
*   **Backend Server Setup (Dev):** `uvicorn src.sentinel.api.main:app --reload --port 8000`
*   **Production Launch Command:** `SENTINEL_SECRET_KEY=your_key uvicorn src.sentinel.api.main:app --host 0.0.0.0 --port 8000 --workers 4`

### Testing
*   **Run All Tests:** `pytest`
*   **Run Unit Tests:** `pytest tests/unit`
*   **Run Integration Tests:** `pytest tests/integration`
*   **Verification Script:** `python local_fire_drill.py`

---

## 🗺️ Codebase Map & Topology

```text
SentinelTrading/
├── frontend/                   # React Single-Page Application (Vite + TS + Tailwind)
│   ├── src/
│   │   ├── components/         # Premium Qasali Aesthetic charts and UI widgets
│   │   ├── hooks/              # Workspace, identity, and browser storage sync hooks
│   │   ├── lib/                # API client, presentation utils
│   │   └── pages/              # Onboarding, CommandCenter, Analytics, Trading
├── src/sentinel/               # Control Plane & Data Plane Backend (FastAPI + Python)
│   ├── api/                    # Routers, middleware, and dependency injection
│   ├── brain/                  # ML models, feature engineering, and risk calculations
│   ├── bridge/                 # MetaTrader 5 bridges and telemetry relay loops
│   ├── domain/                 # Type declarations and database schemas
│   └── infra/                  # Postgres, SQLite WAL, Redis, S3, and Vault client drivers
└── tests/                      # Unit & integration testing suites
```

---

## 📊 The 9 Core Behavioral Columns

Our feature extraction pipeline (`src/sentinel/brain/feature_engine.py`) maps raw trade telemetry into these 9 core metrics. These features are evaluated by `SentinelBrain` to classify risks and flag tilt behaviors:

| Column Name | Metric Explained | Risk Logic & Context |
|---|---|---|
| **Hour_Decimal** | Time of day as a decimal fraction (e.g., 14.5 for 2:30 PM). | Identifies fatigue patterns, low-liquidity session trading, and timezone drift. |
| **Losing_Streak** | Consecutive unprofitable transactions. | Directly triggers the emotion-based **tilt threshold**. Increments on loss; resets on profit. |
| **Drawdown_State** | Equity decay velocity. | Measures drawdown percentage relative to initial balance vs. specified tilt tolerance limits. |
| **Lot_Deviation** | Sizing deviation compared to typical historical base. | Spot size surges (e.g. z-score deviations). Flags doubling down (Martingale behavior). |
| **Revenge_Timer** | Seconds elapsed since the last losing trade exit. | Captures impulsive re-entry trades. Shorter times since exit suggest emotional reaction. |
| **Lots** | Absolute lot volume of the current transaction. | Evaluates absolute volume risk constraints. |
| **RR Ratio** | Realized Risk-to-Reward ratio. | Monitors changes in target placement quality (e.g. cutting winners early, letting losers run). |
| **Realized_Vol_20** | Rolling historical standard deviation of returns. | Flags abnormal market volatility environment behavior. |
| **Trend_Momentum** | Directional momentum/strength index. | Detects if trades are running counter to aggressive market momentum trends. |

---

## 🔒 Security & Tenant Governance

1.  **Fernet Security:** Client requests must pass authentication via Fernet-encrypted session tokens.
2.  **Rate Limiting:** Managed at `src/sentinel/api/dependencies.py`. Enforces a strict maximum of **10 requests per second per user** via a Redis token bucket algorithm.
3.  **Tenant Isolation:** Ensures database scopes and query parameters are always bounded by the active client context. No user can view or alter another's credentials or telemetry.
4.  **Credential Vaulting:** MT5 account details and passwords must be stored inside HashiCorp Vault transit engines. The SQLite `redis_fallback.db` acts as an encrypted memory backup when Vault is offline.

---

## 🤖 Ruflow Operational Team Directives

When interacting with this codebase as a Ruflow agent:
*   **Engineering Roles (CTO, Devs):** Do not break the compilation of backend models or frontend types. Check your changes with `npx tsc` and `pytest`. Keep the core feature definitions in `feature_engine.py` intact.
*   **Security Roles (CISO):** Never print/leak Vault secrets, JWT keys, or API tokens in log statements. Ensure all exceptions are caught cleanly without leaking stack traces or database info.
*   **Growth/Marketing Roles (CMO):** Content modifications must adhere to the premium, golden-trimmed Qasali Capital design guidelines.
