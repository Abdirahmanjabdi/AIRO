# Sentinel Zero — AI-Driven Risk Management Layer

> **Identity-first, model-driven trade protection for professional traders on FTMO, prop firms, and managed accounts.**

[![CI](https://github.com/Abdirahmanjabdi/AIRO/actions/workflows/ci.yml/badge.svg)](https://github.com/Abdirahmanjabdi/AIRO/actions)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red)](LICENSE)

---

## 🧠 What Is Sentinel Zero?

Sentinel Zero is a real-time, per-user risk assessment engine that sits between a trader's MetaTrader 5 terminal and their live account. It uses a personalized **Isolation Forest + Random Forest** model trained on each trader's own behavioral baseline to detect anomalous trade patterns, equity drawdown violations, and revenge-trading cycles — and intervene in milliseconds to prevent catastrophic account blowup.

**Key capabilities:**
- **Identity-first architecture** — every assessment is scoped to a specific user model; no shared risk parameters
- **Real-time telemetry** — a lightweight MT5 bridge streams live position data to the Brain API every 2 seconds
- **Explainable AI** — every BLOCK decision includes a SHAP-powered reason visible on the Command Centre dashboard
- **Vault-secured credentials** — broker login details are never stored in plaintext; all access is via HashiCorp Vault

---

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TRADER'S MACHINE                         │
│                                                                 │
│   MetaTrader 5  ──────►  MT5 Bridge (mt5_relay.py)             │
│   (Live Account)          Python / MT5 API                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTPS POST /v1/analyze
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SENTINEL BRAIN (EKS)                        │
│                                                                 │
│  ┌────────────┐   ┌─────────────┐   ┌──────────────────────┐  │
│  │  FastAPI   │──►│ Risk Engine  │──►│  PostgreSQL (Audits) │  │
│  │  Brain API │   │  (IsoForest  │   │  Redis (Cache/State) │  │
│  └────────────┘   │  + RandForest│   │  S3 (Model Store)   │  │
│                   │  + SHAP)     │   └──────────────────────┘  │
│                   └─────────────┘                               │
│                         │                                       │
│                   ┌─────▼──────┐                               │
│                   │   Vault    │  ← Broker Credentials          │
│                   └────────────┘                               │
└──────────────────────────────┬──────────────────────────────────┘
                               │ WebSocket / REST
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   COMMAND CENTRE (React SPA)                    │
│                                                                 │
│   Risk Gauge · Audit Table · Baseline Status · SHAP Hover      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.12+ |
| Node.js | 20+ |
| Docker Desktop | Latest |
| MetaTrader 5 | Any (Windows) |

### 1. Clone & Configure

```bash
git clone https://github.com/Abdirahmanjabdi/AIRO.git
cd AIRO
cp .env.example .env   # Fill in your values — never commit .env!
```

### 2. Start the Backend (Brain + Data Stores)

```bash
docker-compose up -d
```

This spins up: **FastAPI Brain**, **PostgreSQL**, **Redis**, **Vault**, and **MinIO** (local S3).

### 3. Verify Everything is Healthy

```bash
curl http://localhost:8000/healthz
# Expected: {"status":"ok","version":"1.0.0",...}
```

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev
# Open: http://localhost:8081
```

### 5. Launch the MT5 Bridge (Windows Terminal)

```powershell
# Replace values with your FTMO credentials
$env:PYTHONPATH="src"
$env:VAULT_ADDR="http://localhost:8200"
$env:VAULT_TOKEN="your-vault-token"
$env:SENTINEL_USER_ID="Your-User-ID"
python -m sentinel.bridge.mt5_relay
```

### 6. Onboard Your Account

Navigate to `http://localhost:8081/workspace/onboarding` and follow the 4-step onboarding wizard to securely store your MT5 credentials in Vault and train your personal baseline model.

---

## 📁 Repository Structure

```
sentinel-zero/
├── src/sentinel/
│   ├── api/            # FastAPI routes (analyze, dashboard, onboarding)
│   ├── brain/          # ML engine (IsolationForest, RandomForest, SHAP)
│   ├── bridge/         # MT5 relay (live position polling)
│   ├── db/             # SQLAlchemy models & Alembic migrations
│   └── domain/         # Pydantic models (shared types)
├── frontend/           # React + TypeScript Command Centre
├── infra/
│   ├── docker/         # Dockerfiles for brain & bridge
│   ├── helm/           # Helm charts for EKS deployment
│   ├── k8s/            # Kubernetes manifests
│   └── terraform/      # EKS, RDS, Redis, S3, ECR, IAM
├── tests/              # Unit & integration tests
└── .github/workflows/  # CI/CD (Lint → Test → Build → Deploy)
```

---

## ☁️ Production Deployment (AWS EKS)

```bash
cd infra/terraform

# 1. Initialise providers
terraform init

# 2. Review plan (use a prod.tfvars you've filled in locally — never commit it)
terraform plan -var-file="prod.tfvars"

# 3. Apply
terraform apply -var-file="prod.tfvars"
```

After the cluster is up, the GitHub Actions `deploy-eks` job will handle all future zero-downtime deployments automatically on every push to `main`.

---

## 🔐 Security

- **Secrets:** All broker credentials are encrypted in HashiCorp Vault. `.env` files and `*.tfvars` are in `.gitignore` and are never committed.
- **IAM:** Node group roles follow least-privilege — read/write to the model S3 bucket only; no `DeleteObject` permission.
- **Docker:** All containers run as non-root (`sentinel` user).
- **ECR:** Images are scanned for vulnerabilities on every push (`scan_on_push = true`).

---

## 📄 License

Proprietary — All rights reserved. © 2026 Sentinel Zero / AIRO.
