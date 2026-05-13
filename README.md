# Sentinel Trading

Sentinel Trading is an institutional behavioral-risk engine for MetaTrader 5 traders. It uses Elevated Collaborative Intelligence (ECI) to detect trading behaviors that destroy capital: revenge entries, oversized positions, drawdown pressure, fatigue patterns, and abnormal deviation from a trader's own baseline.

Sentinel does not predict market direction. It protects the trader from themselves when execution quality starts to degrade.

## Mission

Financial markets already punish poor timing, poor sizing, and emotional escalation. Most trading tools focus on entries, indicators, or automation. Sentinel focuses on the missing layer: behavioral governance.

The system observes live trading telemetry, compares each trade against the trader's own profile, records an audit trail, and can optionally intervene through a secured MT5 bridge. The goal is capital preservation, funded-account protection, and executive-grade visibility into human behavioral risk.

## Product Workflow

```text
Trader / MT5 Account
  -> Sentinel MT5 Bridge Pod
     -> FastAPI Brain API
        -> API-key authentication
        -> Redis Cluster cache, locks, heartbeats
        -> SentinelBrain inference
        -> PostgreSQL user state and audit trail
        -> behavioral_logs feature store
        -> S3 Parquet data lake
        -> S3 / MinIO per-user model artifacts
        -> Vault-backed credential storage
```

The default operating mode is audit-only. Capital-affecting intervention is disabled unless `SENTINEL_ENFORCE_MODE=true`.

## The Brain

SentinelBrain combines:

- **Isolation Forest anomaly detection** for unsupervised behavioral outlier detection.
- **Random Forest risk classification** for supervised risk scoring when labels exist.
- **Dynamic Z-score baselining** so a 0.01-lot trader and a 100-lot trader are judged relative to their own normal behavior.
- **Cold-start Risk DNA scoring** for new users without trade history.
- **Maturity tiers** from bootstrap to shadow mode to active personalized scoring.
- **SHAP background explanations** for auditability and operator review.

The important principle is style agnosticism. Sentinel avoids fixed global claims like "10 lots is dangerous." Instead, it asks whether this trade is abnormal for this trader, in this regime, at this moment.

## Security And Authentication

Sentinel uses an API-key gate for protected `/v1/*` routes.

- Bootstrap routes issue and store API credentials.
- API keys are hashed before database storage.
- The React frontend captures the issued key during onboarding.
- Later dashboard and inference calls inject `X-API-Key` automatically.
- Backend validation compares the incoming header against the stored hash.

Credential handling is separated from the trading dataset. Broker passwords are routed through Vault-backed storage and are not written to PostgreSQL audit logs.

## Governance And Compliance

Sentinel treats behavioral telemetry as the company's core dataset.

- `behavioral_logs` stores high-fidelity feature telemetry for training and drift management.
- Logs use hashed trader identity rather than raw `user_id`.
- PostgreSQL handles real-time state and audit reads.
- S3 receives Parquet exports for offline model training.
- Daily export is partitioned by date for future deep learning workflows.

This keeps the production database responsive while preserving a structured behavioral data lake.

## Scale Path

The architecture is designed to grow from Vanguard beta users to a 10,000-account fleet:

| Layer | Current Design |
|---|---|
| Control plane | FastAPI Brain API on Kubernetes |
| Data plane | One MT5 bridge pod per trader |
| Compute scaling | EKS managed nodes plus Karpenter MT5 node pool |
| State | ElastiCache Redis replication group with cluster mode |
| Persistence | RDS PostgreSQL for state and audits |
| Model artifacts | S3 / MinIO joblib model store |
| Behavioral data lake | S3 Parquet partitions |
| Exposure | AWS Load Balancer Controller and ALB Ingress |

Terraform validates locally, but production rollout still requires a real AWS `terraform plan` with valid credentials before any `apply`.

## Maturity Workflow

| State | Trigger | Behavior |
|---|---|---|
| `maturity_0` | No usable history | Bootstrap scoring from Risk DNA |
| `maturity_1` | Early history | Shadow-mode observation |
| `maturity_2` | 20+ trades and model ready | Personalized Isolation Forest + classifier scoring |

Live behavioral logs trigger background retraining every 20 trades. Redis retraining locks prevent duplicate training jobs for the same user.

## Intervention Safety

Sentinel is built to fail conservatively.

- Decision timeouts return a blocking risk response.
- MT5 duplicate interventions are protected by Redis idempotency locks.
- Global close-all fail-safe requires repeated MT5 failures and confirmed terminal disconnect.
- Enforcement is disabled by default.
- Operator-facing UI separates audit, monitoring, and live enforcement posture.

## Repository Layout

```text
src/sentinel/
  api/              FastAPI app, auth dependency, routes, runtime startup
  brain/            feature engineering and SentinelBrain risk engine
  bridge/           MT5 history collector and live relay
  domain/           Pydantic contracts and enums
  infra/            DB, Redis, S3, data lake, Vault clients

frontend/
  src/App.tsx       React route tree and workspace shell
  src/lib/api.ts    Typed API client with X-API-Key injection
  src/pages/        Landing, onboarding, trading, analytics, admin, runtime
  src/components/   Dashboard, shell, charts, and UI components

infra/
  docker/           Brain and MT5 container definitions
  helm/             Brain, MT5 pod, and Vault charts
  terraform/        VPC, EKS, Karpenter, RDS, Redis, S3, ECR, ALB, IAM

tests/
  unit/             Domain, feature, risk, and preflight tests
  integration/      FastAPI integration tests
  mocks/            MT5 simulator
```

## Local Development

### Requirements

- Python 3.12+
- Node.js 20+
- Docker Desktop
- Windows + MetaTrader5 package for real MT5 integration

### Run Everything Locally

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

### Backend

```bash
pip install -e ".[dev]"
uvicorn sentinel.api.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

### MT5 Bridge Simulator

```powershell
$env:PYTHONPATH="src"
$env:BRAIN_API_URL="http://localhost:8000"
$env:REDIS_URL="redis://localhost:6379/0"
$env:SENTINEL_MT5_MODULE="tests.mocks.mt5_simulator"
$env:SENTINEL_MT5_SIMULATOR_MODE="success"
python -m sentinel.bridge.mt5_relay
```

## Verification

Latest local verification:

```bash
python -m pytest -q
```

```bash
cd frontend
npm run lint
npm test
npm run build
```

Validated status:

- Backend tests: `60 passed`
- Frontend tests: `8 passed`
- Frontend lint: passed
- Frontend production build: passed
- Terraform validation: passed after provider/module init

`terraform plan` requires valid AWS credentials. Do not run `terraform apply` on a personal/free-trial account until AWS Activate or equivalent credits are confirmed.

## Deployment Discipline

Sentinel is infrastructure-heavy by design. A 10,000-user architecture means MT5 bridge pods, Redis cluster state, RDS, S3, ALB, and EKS scaling all have real cost.

Recommended launch sequence:

1. Push the hardened repo.
2. Secure AWS Activate credits.
3. Run `terraform plan` with the funded AWS account.
4. Launch a Vanguard 50 audit-only cohort.
5. Enable intervention only after live MT5 soak testing.

## Positioning

Sentinel is not a signal service. It is not a trading bot. It is a behavioral governance layer for traders, prop-firm operators, and risk teams that need to preserve capital when human execution starts to fail.

The moat is the anonymized behavioral dataset: live trade context, relative deviation signals, intervention outcomes, and model drift history captured in a form that can support future deep learning systems.

## License

The project is currently prepared for private commercial development. Confirm final licensing terms before public distribution.
