# Sentinel Trading Architecture

> Version: 2026-05-12
> Status: controlled-beta architecture, not yet a fully validated 10k-user production system

This document describes the code that exists in this repository. It intentionally separates implemented behavior from roadmap items.

## 1. System Purpose

Sentinel Trading is a risk-governance layer for MetaTrader 5 traders. It is not a market-prediction engine. The system watches behavior and attempts to identify risk patterns such as tilt, revenge trading, outsized position changes, and drawdown stress.

The product has two runtime lanes:

- **Control plane:** FastAPI Brain API, ML scoring, audits, metadata, model storage, Vault credential flow.
- **Data plane:** One MT5 bridge process per trader or account context, responsible for fetching history and streaming live telemetry.

## 2. High-Level Topology

```text
Frontend React SPA
  |
  | REST
  v
FastAPI Brain API
  |
  |-- PostgreSQL: users, onboarding_jobs, api_credentials, risk_audits
  |-- Redis: risk cache, behavioral profile cache, onboarding queue, heartbeats, intervention locks
  |-- S3/MinIO: per-user joblib model artifacts
  |-- Vault: encrypted broker credential storage
  |
  v
SentinelBrain
  |-- cold-start bootstrap scorer
  |-- IsolationForest anomaly detector
  |-- RandomForest risk classifier
  |-- SHAP explanation background task

MT5 Bridge
  |
  |-- Redis onboarding queue
  |-- MetaTrader5 Python API
  |-- /v1/analyze telemetry posts
  |-- optional mt5.order_send intervention when enforce mode is enabled
```

## 3. Backend Components

### 3.1 FastAPI App

Entry point: `src/sentinel/api/main.py`

Responsibilities:

- initialize database metadata
- start model-store initialization in the background
- load the default model from `default_model.joblib` when present
- configure CORS
- register health and analysis routers

Health endpoints:

- `GET /healthz`: liveness only
- `GET /readyz`: checks default model, Redis, DB, and Vault requirement state

### 3.2 Analysis And Onboarding Routes

Main file: `src/sentinel/api/routes/analysis.py`

Implemented routes:

- `POST /v1/credentials`
- `POST /v1/webhooks/whop`
- `POST /v1/analyze`
- `POST /v1/onboard`
- `GET /v1/onboard/{job_id}`
- `POST /v1/onboard/data`
- `GET /v1/user/{user_id}/profile`
- `GET /v1/user/{user_id}/audits`
- `GET /v1/user/{user_id}/dashboard`
- `GET /v1/admin/overview`

Important behavior:

- `/v1/analyze` caches identical risk payloads in Redis.
- Every non-failing analysis path attempts to persist a `RiskAudit`.
- User behavioral profiles are cached in Redis for faster repeat access.
- SHAP explanation work runs in a background task when a real trained user model exists.
- Onboarding accepts empty history and records a `blank_baseline` instead of failing.

### 3.3 Domain Contracts

Main file: `src/sentinel/domain/models.py`

Important models:

- `TradeContext`: live telemetry input.
- `RiskAssessment`: risk decision output.
- `UserInitialParameters`: Risk DNA cold-start parameters.
- `UserBaseline`: user model and maturity metadata.
- `OnboardingRequest`, `OnboardingStatus`, `OnboardingDataSubmission`.
- `RiskAuditRecord`, `WorkspaceSummary`, `AdminOverview`.

Important enums:

- `Decision`: `ALLOW`, `BLOCK`, `REDUCE_SIZE`
- `RiskMode`: `normal`, `risk_off`, `baseline_pending`, `shadow`, `bootstrap`
- `UserMaturity`: `maturity_0`, `maturity_1`, `maturity_2`
- `TradingStyle`: `scalper`, `intraday`, `swing`

## 4. Risk Engine

Main file: `src/sentinel/brain/risk_engine.py`

### 4.1 Feature Columns

The trained model uses these nine features:

- `Hour_Decimal`
- `Losing_Streak`
- `Drawdown_State`
- `Lot_Deviation`
- `Revenge_Timer`
- `Lots`
- `RR Ratio`
- `Realized_Vol_20`
- `Trend_Momentum`

Feature engineering lives in `src/sentinel/brain/feature_engine.py`.

### 4.2 Cold-Start Scoring

Zero-history users do not have enough data for a personal IsolationForest or RandomForest model.

The implemented cold-start path uses `assess_bootstrap_risk()`:

- reads `UserInitialParameters`
- checks drawdown against declared tilt tolerance
- uses a relative lot-size z-score proxy based on declared typical lot size
- checks max lot multiplier
- checks losing streak
- checks revenge timing using trading-style-specific thresholds

This is not K-Means clustering. K-Means was discussed as a roadmap idea but is not implemented in the codebase.

### 4.3 Maturity State

Implemented maturity logic:

| State | Criteria | Runtime behavior |
|---|---|---|
| `maturity_0` | zero trades | bootstrap scoring |
| `maturity_1` | 1-19 trades | shadow scoring, returns `ALLOW` while recording risk |
| `maturity_2` | 20+ trades and trained model available | full V5 model scoring |

Live audit calls increment trade count and update maturity metadata. Historical onboarding can fast-track a user if enough trades are submitted.

### 4.4 Full V5 Model

When the user has a trained model:

- IsolationForest detects anomalies.
- RandomForestClassifier produces a risk probability.
- The risk threshold defaults to `0.6537`.
- An anomaly hard-blocks.
- High risk above threshold can block or reduce position size.
- Lower risk can still reduce size gently if multiplier drops below full size.

The model hyperparameters are static defaults in code. There is no live Optuna/Bayesian tuning job in the current repository.

### 4.5 Circuit Breaker

`SentinelBrain` tracks consecutive prediction failures. If failures exceed the circuit breaker threshold, the engine returns risk-off responses. This is independent from the MT5 bridge fail-safe.

## 5. MT5 Bridge

Main files:

- `src/sentinel/bridge/mt5_relay.py`
- `src/sentinel/bridge/mt5_history.py`

### 5.1 Onboarding History Flow

The bridge:

1. Reads onboarding jobs from Redis.
2. Fetches credentials from Vault.
3. Initializes MT5.
4. Pulls historical deals.
5. Converts them into `HistoricalTrade` records.
6. Posts them to `/v1/onboard/data`.

Local development uses `tests.mocks.mt5_simulator`.

### 5.2 Live Monitoring Flow

The relay loop:

1. Attempts to initialize MT5 for the configured `SENTINEL_USER_ID`.
2. Polls open positions.
3. Derives telemetry such as drawdown, lot deviation, losing streak, and revenge timer.
4. Sends telemetry to `/v1/analyze`.
5. Logs the returned decision.
6. Optionally executes intervention if `SENTINEL_ENFORCE_MODE=true`.

### 5.3 Enforcement Safety

Live enforcement is disabled by default.

When enabled:

- `REDUCE_SIZE` attempts to close the difference between current lots and adjusted lots.
- `BLOCK` attempts to close matching symbol positions.
- every MT5 ticket intervention uses a Redis NX lock: `intervention:{ticket_id}`
- the lock TTL prevents duplicate close orders during fast polling
- global close-all fail-safe requires five consecutive `positions_get()` failures and confirmed `terminal_info() is None`

Known limitation:

- The bridge still needs real broker soak testing before broad enforcement.
- The current bridge handles a simple open-position polling model and should be tested carefully with hedging accounts, partial fills, symbol-specific filling modes, broker rejections, and multi-position cases.

## 6. Persistence

Main file: `src/sentinel/infra/db.py`

Tables:

- `users`
- `api_credentials`
- `onboarding_jobs`
- `risk_audits`

The DB module includes in-memory fallbacks for test/lightweight runtime situations when PostgreSQL is unavailable. This is useful for local tests but should not be relied upon in production.

The code currently uses `Base.metadata.create_all()` plus `ALTER TABLE IF NOT EXISTS` compatibility statements at startup. Alembic is present, but there are no migration versions committed. Production should move schema changes into explicit Alembic revisions before public launch.

## 7. Redis

Main file: `src/sentinel/infra/redis_cache.py`

Current uses:

- risk assessment cache
- behavioral profile cache
- presence heartbeat
- onboarding command queue
- MT5 intervention idempotency lock

Local fallback:

- `InMemoryRedis` is used only if the Redis Python package is not installed.
- If the package is installed but no Redis server exists, connection attempts can fail unless callers handle exceptions.

Production limitation:

- Terraform currently provisions a single ElastiCache Redis cluster node, not cluster mode.
- This is acceptable for local/control beta, not 10k concurrent trade streams.

## 8. Model Storage

Main file: `src/sentinel/infra/s3.py`

Behavior:

- Production path uses S3.
- Local path can use MinIO through `S3_ENDPOINT`.
- If boto3 is unavailable, the model store falls back to in-memory bytes.
- Model keys use `models/{user_id}/brain_v5.joblib`.

## 9. Vault And Credentials

Main file: `src/sentinel/infra/vault_client.py`

Behavior:

- Production path uses Vault KV v2 and Transit encryption.
- AppRole and token auth are supported.
- If Vault is required and unavailable, credential operations raise.
- If Vault is not required, encrypted in-memory fallback is used.

Production expectations:

- set `SENTINEL_REQUIRE_VAULT=true`
- inject `VAULT_ROLE_ID` and `VAULT_SECRET_ID`
- do not rely on `VAULT_TOKEN` outside local/dev workflows

## 10. Frontend Architecture

Main files:

- `frontend/src/App.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/Onboarding.tsx`
- `frontend/src/pages/CommandCenter.tsx`
- `frontend/src/pages/Trading.tsx`
- `frontend/src/pages/Admin.tsx`

Routing:

- `/`: landing page
- `/workspace`: command center
- `/workspace/onboarding`
- `/workspace/trading`
- `/workspace/analytics`
- `/workspace/timeline`
- `/workspace/config`
- `/workspace/admin` when admin is enabled

State:

- identity is stored in local storage with a seven-day age limit
- React Query polls readiness, health, and dashboard data
- API base URL is local or cloud depending on `execution_mode`

Risk DNA survey fields:

- max drawdown before tilt
- primary instrument
- trading style
- typical lot size
- max lot multiplier before review

## 11. Infrastructure

Main file: `infra/terraform/main.tf`

Implemented Terraform:

- VPC
- EKS
- managed node group for Brain on On-Demand
- managed node group for MT5 on Spot
- managed MT5 failover node group on On-Demand
- RDS PostgreSQL
- single-node ElastiCache Redis
- S3 model bucket
- ECR repositories
- IAM model-store policy

Helm charts:

- `infra/helm/sentinel-brain`
- `infra/helm/sentinel-pod`
- `infra/helm/sentinel-vault`

Current scaling truth:

- This infrastructure is suitable as a controlled beta baseline.
- It does not yet implement EKS Auto Mode, Karpenter, Redis cluster mode, ALB controller, or an MT5 pod reaper.
- The code includes TODOs in Terraform for those 10k-user milestones.

## 12. CI/CD

Main file: `.github/workflows/ci.yml`

Jobs:

- Python lint and mypy
- unit tests
- integration tests
- frontend build
- Docker brain image build
- bridge IP-protection scan
- EKS deploy on `main`

Important caveat:

The deploy job is configured, but production correctness depends on real AWS secrets, EKS cluster naming, Helm values, image publishing, and environment-specific configuration. Treat CI deploy as a scaffold until validated against the actual AWS account.

## 13. Known Gaps

These are intentionally explicit:

- No real MT5 enforcement soak test is committed.
- K-Means trader clustering is not implemented.
- Optuna/Bayesian tuning is not an active training service.
- Alembic migration history is empty.
- Redis is single-node in Terraform.
- ALB/Ingress is not codified in Terraform.
- MT5 pod reaper/reprovisioning controller is not implemented.
- PII is not fully pseudonymized or field-encrypted.
- The frontend still has mock cloud bridge provisioning helpers.
- Production license metadata is inconsistent between historical docs and `pyproject.toml`.

## 14. Recommended Launch Posture

Recommended current posture:

1. Run Vanguard users in audit-only mode.
2. Confirm that `BLOCK` and `REDUCE_SIZE` decisions would have been correct.
3. Collect real MT5 latency, broker rejection, partial-fill, and reconnect data.
4. Enable enforcement only for explicit opt-in users.
5. Add infrastructure hardening before scaling beyond a small beta.

This is a serious foundation, but the capital-affecting path should be treated with the same caution as any live trading middleware.
