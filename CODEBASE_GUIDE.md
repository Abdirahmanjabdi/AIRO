# Sentinel Trading Codebase Guide

This guide is a practical walkthrough for engineers, reviewers, and operators who want to understand how the repository works.

## Start Here

Read these files first:

1. `README.md` - product, local setup, current readiness.
2. `ARCHITECTURE.md` - technical system design.
3. `README_PROD.md` - controlled-beta production runbook.
4. `AI_CONTRACT.md` - safety and contributor rules.

Then read the implementation in this order:

1. `src/sentinel/domain/models.py`
2. `src/sentinel/brain/risk_engine.py`
3. `src/sentinel/api/routes/analysis.py`
4. `src/sentinel/bridge/mt5_relay.py`
5. `frontend/src/pages/Onboarding.tsx`
6. `frontend/src/pages/CommandCenter.tsx`
7. `infra/terraform/main.tf`

## The Main Product Flow

### 1. User Onboards

Frontend file:

- `frontend/src/pages/Onboarding.tsx`

Backend files:

- `src/sentinel/api/routes/analysis.py`
- `src/sentinel/domain/models.py`
- `src/sentinel/infra/vault_client.py`
- `src/sentinel/infra/db.py`

Flow:

1. User submits broker metadata and a read-only password.
2. Frontend posts credentials to `/v1/credentials`.
3. Backend stores password material through Vault.
4. User submits Risk DNA values:
   - max drawdown before tilt
   - primary instrument
   - trading style
   - typical lot size
   - max lot multiplier
5. Frontend posts onboarding request to `/v1/onboard`.
6. Backend creates an onboarding job and pushes a command into Redis.
7. MT5 bridge reads the Redis command and fetches history.
8. Bridge posts history to `/v1/onboard/data`.
9. Backend trains and persists a user model if enough history exists.

Example onboarding payload:

```json
{
  "user_id": "trader-001",
  "broker_server": "ICMarkets-Demo",
  "account_id": "12345678",
  "min_trades": 20,
  "initial_parameters": {
    "max_drawdown_pct": 3,
    "primary_instrument": "NAS100",
    "trading_style": "intraday",
    "typical_lot_size": 1,
    "max_lot_multiplier": 2
  }
}
```

### 2. Bridge Streams Live Telemetry

Bridge file:

- `src/sentinel/bridge/mt5_relay.py`

The relay polls MT5 positions and creates `TradeTelemetry`, which matches the backend `TradeContext` model.

Example telemetry:

```json
{
  "user_id": "trader-001",
  "symbol": "EURUSD",
  "hour_decimal": 14.5,
  "losing_streak": 2,
  "drawdown_state": 0.025,
  "lot_deviation": 0.4,
  "revenge_timer": 45,
  "lots": 1.0,
  "rr_ratio": 1.0,
  "realized_vol_20": 0.0,
  "trend_momentum": 0.0
}
```

### 3. Brain Scores Risk

Files:

- `src/sentinel/api/routes/analysis.py`
- `src/sentinel/brain/risk_engine.py`
- `src/sentinel/brain/feature_engine.py`

Decision path:

- If a cached identical payload exists, return cached assessment and persist a cached audit.
- If no trained user model exists, use bootstrap/shadow scoring.
- If a trained model exists and the user is mature, use `SentinelBrain.assess_risk()`.
- Persist a risk audit.
- Increment live trade count and maturity metadata.

Example response:

```json
{
  "decision": "REDUCE_SIZE",
  "risk_score": 0.72,
  "is_anomaly": false,
  "size_multiplier": 0.71,
  "explanation": [
    {
      "feature": "Lot_ZScore",
      "impact": 0.8
    }
  ],
  "latency_ms": 2.4,
  "mode": "bootstrap",
  "maturity_state": "maturity_0",
  "shadow_mode": false
}
```

### 4. Command Center Displays The Audit Trail

Frontend files:

- `frontend/src/App.tsx`
- `frontend/src/hooks/useSentinelWorkspace.ts`
- `frontend/src/pages/CommandCenter.tsx`
- `frontend/src/lib/api.ts`

The dashboard reads:

- `/readyz`
- `/healthz`
- `/v1/user/{user_id}/dashboard`

It displays:

- latest decision
- current mode
- baseline status
- protection event count
- average latency
- audit table
- SHAP or fallback explanations when present

## Important Backend Modules

### `src/sentinel/domain/models.py`

The source of truth for API contracts.

Most important classes:

- `TradeContext`
- `RiskAssessment`
- `UserInitialParameters`
- `UserBaseline`
- `OnboardingRequest`
- `RiskAuditRecord`
- `WorkspaceSummary`

### `src/sentinel/brain/risk_engine.py`

The risk engine.

Important methods:

- `train()`
- `assess_risk()`
- `assess_bootstrap_risk()`
- `_bootstrap_signals()`
- `_relative_lot_z_score()`
- `_explain()`
- `save()` and `load()`

### `src/sentinel/brain/feature_engine.py`

Transforms historical trades into model features.

Key functions:

- `engineer_features()`
- `compute_losing_streak()`
- `compute_drawdown_state()`
- `compute_lot_deviation()`
- `compute_realized_volatility()`
- `compute_trend_momentum()`

### `src/sentinel/api/routes/analysis.py`

The main application orchestration layer.

It owns:

- credential route
- Whop webhook route
- analysis route
- onboarding route
- dashboard/profile/audit reads
- training and persistence from onboarding data

### `src/sentinel/infra/db.py`

SQLAlchemy models and persistence helpers.

Current tables:

- `User`
- `ApiCredential`
- `OnboardingJob`
- `RiskAudit`

### `src/sentinel/infra/redis_cache.py`

Cache and queue abstraction.

Used for:

- risk cache
- behavioral profile cache
- presence heartbeat
- onboarding queue
- intervention idempotency lock

### `src/sentinel/infra/vault_client.py`

Vault wrapper.

Stores:

- broker server
- login id
- encrypted password ciphertext

It returns decrypted credentials only to runtime code that needs to initialize MT5.

### `src/sentinel/infra/s3.py`

Model artifact storage.

Model keys:

```text
models/{user_id}/brain_v5.joblib
```

## Important Frontend Modules

### `frontend/src/App.tsx`

Defines routes and the workspace shell.

### `frontend/src/lib/api.ts`

Typed API client. Keep this in sync with Pydantic models.

### `frontend/src/hooks/useSentinelIdentity.ts`

Stores active identity in local storage.

### `frontend/src/hooks/useSentinelWorkspace.ts`

Polls readiness, health, and dashboard data.

### `frontend/src/pages/Onboarding.tsx`

Credential capture, Risk DNA survey, onboarding job start, and status polling.

### `frontend/src/pages/CommandCenter.tsx`

Main operator dashboard.

### `frontend/src/pages/Trading.tsx`

Manual probe and trading-facing workflow page.

### `frontend/src/pages/Admin.tsx`

Fleet-level overview.

## Infrastructure Modules

### Docker Compose

File: `docker-compose.yml`

Services:

- `brain`
- `bridge`
- `frontend`
- `redis`
- `postgres`
- `minio`
- `vault`

### Terraform

File: `infra/terraform/main.tf`

Defines AWS networking, EKS, RDS, Redis, S3, ECR, and IAM.

Current Terraform is beta-grade. It is not yet a complete 10k-user platform.

### Helm

Charts:

- `infra/helm/sentinel-brain`
- `infra/helm/sentinel-pod`
- `infra/helm/sentinel-vault`

## Test Suite

Run:

```bash
python -m pytest -q
```

Important test files:

- `tests/unit/test_risk_engine.py`
- `tests/unit/test_feature_engine.py`
- `tests/unit/test_domain_models.py`
- `tests/unit/test_preflight.py`
- `tests/integration/test_api.py`

The MT5 simulator lives at:

- `tests/mocks/mt5_simulator.py`

## What Is Implemented Versus Not Implemented

Implemented:

- Risk DNA onboarding
- blank baseline handling
- maturity state
- bootstrap/shadow/full model scoring
- per-user model artifact storage
- risk audits
- Redis intervention locks
- safer bridge fail-safe threshold
- local MT5 simulator
- frontend dashboard and onboarding flow

Not implemented yet:

- real K-Means clustering of users
- live Optuna retraining service
- production pod reaper
- Redis cluster mode Terraform
- ALB controller Terraform
- full PII pseudonymization
- broker-by-broker execution compatibility matrix
- committed live MT5 soak-test report

## Capital Safety Notes

The most important safety defaults are:

- enforcement off by default
- idempotency lock before MT5 ticket intervention
- fail-safe requires repeated failures and terminal disconnect confirmation
- zero-history users can be onboarded without pretending a mature model exists

Do not remove those controls without replacing them with stronger controls.
