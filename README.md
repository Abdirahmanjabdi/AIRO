# Sentinel Trading

Sentinel Trading is an identity-first risk governance system for MetaTrader 5 traders. It is designed to watch live trading behavior, score each trade against the trader's own profile, record an audit trail, and optionally intervene through a Python MT5 bridge.

The current repository is a working controlled-beta codebase. It includes the FastAPI Brain API, the V5 risk engine, cold-start onboarding, a React command center, an MT5 bridge, local infrastructure with Docker Compose, and AWS/EKS deployment assets. It is not documented here as a guaranteed profit system or a finished 10,000-user production platform. The code is strongest for audit-only beta use and still needs live MT5 enforcement soak tests before capital-affecting automation is enabled for broad use.

## What The Product Does

Sentinel helps traders by targeting behavioral failure modes:

- oversizing after losses
- revenge entries shortly after a close
- drawdown pressure and tilt risk
- abnormal lot-size jumps relative to the trader's normal size
- anomalous patterns detected by a per-user ML model once enough data exists

It does not predict market direction. It does not promise profitability. Its value is defensive: slow down or block behavior that often damages funded accounts and discretionary trading accounts.

## Current System At A Glance

```text
React Command Center
  -> FastAPI Brain API
     -> Pydantic domain contracts
     -> SentinelBrain risk engine
     -> PostgreSQL users, onboarding jobs, audits
     -> Redis cache, heartbeats, onboarding queue, intervention locks
     -> S3 or MinIO per-user model artifacts
     -> Vault broker credential storage

MT5 Bridge
  -> reads onboarding commands from Redis
  -> fetches MT5 history for training
  -> polls live MT5 positions
  -> posts telemetry to /v1/analyze
  -> logs decisions in audit-only mode by default
  -> can close/reduce positions only when SENTINEL_ENFORCE_MODE=true
```

## Key Features

- **Cold-start onboarding:** New traders can submit Risk DNA survey data before any historical trades exist.
- **User maturity state:** The backend tracks `maturity_0`, `maturity_1`, and `maturity_2`.
- **Bootstrap scoring:** Zero-history users are scored with style-aware limits from their Risk DNA profile.
- **Shadow mode:** Early-history users can be watched without blocking trades.
- **Full model mode:** Mature users use the IsolationForest + RandomForest model stored per user.
- **Relative lot anomaly detection:** Cold-start lot risk is based on deviation from the declared typical lot size, not a global hard lot limit.
- **Audit trail:** Each analysis writes risk decisions, scores, modes, explanations, and latency into PostgreSQL.
- **Vault credential boundary:** Broker credentials are encrypted via Vault Transit or an encrypted in-memory fallback for local/test use.
- **MT5 Python bridge:** The bridge uses the MetaTrader5 Python API path rather than an MQL5 EA.
- **Intervention safety:** Live execution is off by default and protected by Redis idempotency locks when enabled.
- **Local simulator:** Tests and local compose can use `tests.mocks.mt5_simulator` instead of a live broker.

## Important Safety Defaults

`SENTINEL_ENFORCE_MODE` defaults to `false`.

In audit-only mode, the bridge logs `ALLOW`, `REDUCE_SIZE`, and `BLOCK` decisions but does not send MT5 close orders. This is intentional. A new deployment should prove model quality and bridge stability in audit-only mode before enabling live capital intervention.

When enforcement is enabled:

- duplicate MT5 ticket interventions are blocked by a Redis NX lock with a TTL
- global close-all fail-safe requires repeated MT5 polling failures and confirmed terminal disconnect
- the bridge uses `mt5.order_send()` to close or partially close positions

## User Maturity Model

| State | Trigger | Behavior |
|---|---|---|
| `maturity_0` | 0 trades | Risk DNA bootstrap scoring. Can produce block/reduce decisions, but bridge still obeys enforce-mode setting. |
| `maturity_1` | 1-19 trades | Shadow mode. The model watches behavior and returns `ALLOW` while recording risk. |
| `maturity_2` | 20+ trades and trained baseline ready | Full V5 model scoring with IsolationForest, RandomForest, size multiplier, and SHAP background explanations. |

The 20-trade threshold is implemented in the domain model and onboarding flow. Historical data can fast-track an experienced trader if the bridge submits enough MT5 history during onboarding.

## Core Backend Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/healthz` | GET | Liveness probe. |
| `/readyz` | GET | Readiness probe for model, Redis, DB, and Vault state. |
| `/v1/credentials` | POST | Stores broker credentials through Vault. |
| `/v1/webhooks/whop` | POST | Creates a user API credential and Helm command metadata from a Whop activation event. |
| `/v1/analyze` | POST | Scores one trade telemetry payload. |
| `/v1/onboard` | POST | Starts onboarding and queues an MT5 history job. |
| `/v1/onboard/{job_id}` | GET | Reads onboarding job status. |
| `/v1/onboard/data` | POST | Receives MT5 historical trades and trains/persists a model. |
| `/v1/user/{user_id}/profile` | GET | Reads baseline and maturity metadata. |
| `/v1/user/{user_id}/audits` | GET | Reads recent risk audit records. |
| `/v1/user/{user_id}/dashboard` | GET | Reads the command-center summary. |
| `/v1/admin/overview` | GET | Reads fleet-level admin data. |

## Repository Layout

```text
src/sentinel/
  api/              FastAPI app, routes, middleware, startup dependencies
  brain/            feature engineering and SentinelBrain risk engine
  bridge/           MT5 history collector and live relay
  domain/           Pydantic contracts and enums
  infra/            DB, Redis cache, S3/MinIO model store, Vault client

frontend/
  src/App.tsx       Route tree and workspace shell
  src/lib/api.ts    Typed frontend API client
  src/pages/        Landing, onboarding, trading, analytics, admin, config
  src/components/   Dashboard, shell, visualization, UI components

infra/
  docker/           Brain and MT5 container definitions
  helm/             Brain, MT5 pod, and Vault charts
  k8s/              Kubernetes manifests
  terraform/        AWS VPC, EKS, RDS, Redis, S3, ECR, IAM

tests/
  unit/             Domain, risk engine, feature engine, preflight tests
  integration/      FastAPI integration tests
  mocks/            MT5 simulator
```

## Local Development

### Requirements

- Python 3.12+
- Node.js 20+
- Docker Desktop
- MetaTrader5 package only for real Windows MT5 integration

### Run Everything With Docker Compose

```bash
docker compose up -d --build
```

Local services:

- Frontend: `http://localhost:8080`
- Brain API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- MinIO: `http://localhost:9001`
- Vault dev server: `http://localhost:8200`
- Redis: `localhost:6379`
- Postgres: `localhost:5432`

The compose bridge uses `tests.mocks.mt5_simulator`, so the local onboarding path can run without a real broker terminal.

### Run Backend Locally

```bash
pip install -e ".[dev]"
uvicorn sentinel.api.main:app --host 0.0.0.0 --port 8000
```

### Run Frontend Locally

```bash
cd frontend
npm ci
npm run dev
```

The Vite dev server defaults to `http://localhost:8080`.

### Run The MT5 Bridge Manually

For local simulator mode:

```powershell
$env:PYTHONPATH="src"
$env:BRAIN_API_URL="http://localhost:8000"
$env:REDIS_URL="redis://localhost:6379/0"
$env:SENTINEL_MT5_MODULE="tests.mocks.mt5_simulator"
$env:SENTINEL_MT5_SIMULATOR_MODE="success"
python -m sentinel.bridge.mt5_relay
```

For live MT5 mode, omit `SENTINEL_MT5_MODULE`, run on a Windows host with MetaTrader 5 installed, and store credentials through `/v1/credentials` first.

## Testing And Verification

Commands used for the latest verified state:

```bash
python -m pytest -q
cd frontend
npm run lint
npm run build
```

Latest local verification:

- Backend tests: `60 passed`
- Frontend lint: passed
- Frontend production build: passed
- Git whitespace check: passed

The backend test suite currently emits scikit-learn warnings about feature names because inference uses a NumPy vector while training uses a DataFrame. The warnings are known; the tests pass.

## Security Model

- Broker passwords are not stored in PostgreSQL.
- Vault Transit encrypts credential material in real deployments.
- Local/test fallback stores encrypted blobs in process memory when Vault is not required.
- API credentials generated by the Whop webhook path are hashed before storage.
- Model artifacts live in S3 or MinIO under `models/{user_id}/brain_v5.joblib`.
- PostgreSQL stores metadata, audit records, onboarding jobs, and maturity state.

Known privacy limitations:

- `user_id`, `account_id`, and `email` are currently stored in clear form.
- Trade audit records store symbols and risk signals in clear form.
- For production privacy standards, add user/account pseudonymization, field-level encryption for PII, retention controls, and data deletion workflows.

## Infrastructure Status

Terraform currently defines:

- VPC
- EKS cluster
- Brain node group on On-Demand capacity
- MT5 worker node group on Spot capacity
- MT5 On-Demand failover node group
- RDS PostgreSQL
- single-node ElastiCache Redis
- S3 model bucket
- ECR repositories
- IAM policy for model-store access

This is controlled-beta infrastructure. The Terraform file includes TODOs for 10k-user production work:

- migrate MT5 data plane to EKS Auto Mode or Karpenter
- add AWS Load Balancer Controller or an explicit ingress/ALB layer
- replace single-node Redis with cluster-mode ElastiCache or an equivalent highly available Redis topology
- add pod reaper/reprovisioning for stalled MT5 pods

## What Is Ready Now

Ready for a Vanguard beta:

- Risk DNA onboarding
- identity-scoped model storage
- audit-only live telemetry
- simulated MT5 onboarding
- backend and frontend test/build verification
- safety defaults for intervention

Not ready to claim broad autonomous production:

- live MT5 enforcement has not been soak-tested against real broker conditions
- 10k-pod infrastructure is not implemented
- Redis is not yet clustered
- ALB/Ingress production exposure is not fully codified in Terraform
- privacy hardening is incomplete
- K-Means clustering mentioned in product planning is not implemented in code
- Optuna/Bayesian tuning values are static defaults, not a live tuning pipeline

## Deployment Notes

Use `README_PROD.md` for Vault bootstrap, model retraining, canary launch, and production operating procedures.

Use `ARCHITECTURE.md` for the technical design, current system boundaries, and known gaps.

Use `AI_CONTRACT.md` for engineering rules that future AI agents and contributors should follow.

## License

The repository currently documents proprietary project intent in historical docs, while `pyproject.toml` lists MIT metadata. Resolve this before any commercial distribution or public launch.
