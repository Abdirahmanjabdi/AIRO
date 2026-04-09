# Sentinel-Zero: Technical Architecture

> **Classification:** Internal Engineering Document
> **Version:** 1.0.0
> **Last Updated:** 2026-04-09

---

## 1. System Topology

```
┌─────────────────────────────────────────────────────────────┐
│                     CONTROL PLANE ("The Brain")             │
│                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  FastAPI      │   │  Redis        │   │  PostgreSQL    │  │
│  │  Brain API    │◄─►│  Heartbeat    │   │  Audit Trail   │  │
│  │  (Stateless)  │   │  + Risk Cache │   │  + Metadata    │  │
│  └──────┬───────┘   └──────────────┘   └────────────────┘  │
│         │                                                   │
│         │  Model Weights                                    │
│         ▼                                                   │
│  ┌──────────────┐   ┌──────────────────────┐               │
│  │  S3 / Blob   │   │  HashiCorp Vault     │               │
│  │  Model Store  │   │  (AppRole + Transit) │               │
│  └──────────────┘   └──────────────────────┘               │
└──────────────────────────┬──────────────────────────────────┘
                           │ gRPC / REST
┌──────────────────────────▼──────────────────────────────────┐
│                      DATA PLANE ("Sentinel Pods")           │
│                                                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐       ┌─────────┐   │
│  │ Pod:U1  │ │ Pod:U2  │ │ Pod:U3  │  ...  │ Pod:Un  │   │
│  │ Wine+MT5│ │ Wine+MT5│ │ Wine+MT5│       │ Wine+MT5│   │
│  │ (Relay) │ │ (Relay) │ │ (Relay) │       │ (Relay) │   │
│  └─────────┘ └─────────┘ └─────────┘       └─────────┘   │
│                                                             │
│  QoS: Guaranteed (limits == requests) — prevents OOM-kill   │
└─────────────────────────────────────────────────────────────┘
```

## 2. Component Specification

| Component | Technology | Role | Latency Budget |
|---|---|---|---|
| **Brain API** | FastAPI (Python 3.12, async) | Stateless risk assessment | < 10ms |
| **Risk Engine** | scikit-learn (IsolationForest + RandomForest) | Anomaly detection + classification | < 5ms |
| **Optimizer** | Optuna (Bayesian) | Hyperparameter tuning per-user | Offline |
| **Session Cache** | Redis 7 Cluster | Heartbeat, risk score cache (10s TTL) | < 2ms |
| **Audit Store** | PostgreSQL 16 | Trade logs, interventions, capital_saved | < 5ms |
| **Model Store** | S3 / Azure Blob (MinIO for dev) | Per-user .joblib model weights | < 50ms |
| **Secrets** | HashiCorp Vault (AppRole + Transit) | MT5 credential encryption | < 10ms |
| **Sentinel Pod** | Docker (Ubuntu + Wine + MT5) | Headless broker bridge (relay only) | < 20ms |

**End-to-end target: < 50ms** (trade telemetry → risk assessment → intervention)

## 3. Proprietary Logic (V5 Brain)

### 3.1 Anomaly Detection
- **Model:** Hybrid Isolation Forest (contamination=0.0399)
- **Purpose:** Detects "Fat Finger" events, freak market conditions
- **Training:** Minimum 50-trade user baseline

### 3.2 Risk Classification
- **Model:** Random Forest Classifier (n_estimators=151, max_depth=10)
- **Features (9 total):**
  - Behavioral: `Hour_Decimal`, `Losing_Streak`, `Drawdown_State`, `Lot_Deviation`, `Revenge_Timer`, `Lots`, `RR_Ratio`
  - Context: `Realized_Vol_20`, `Trend_Momentum`
- **Optimized Threshold:** 0.6537 (Bayesian via Optuna)

### 3.3 Active Intervention (PI Controller)
- **Logic:** Proportional sizing instead of binary block
- **Formula:** `size = max(0, 1 - (risk × sensitivity))` where sensitivity=1.5
- **Fail-safe:** Circuit breaker → Risk-Off (block all) on 5 consecutive failures

## 4. Scaling Strategy

### 4.1 Regional Clusters

| Region | Code | Primary Use | Target Users |
|---|---|---|---|
| London | LD4 | European brokers (FX, CFDs) | 40,000 |
| New York | NY4 | US equities, forex | 35,000 |
| Tokyo | TY3 | APAC coverage | 25,000 |

### 4.2 Pod Scheduling
- One Sentinel Pod per active user (ephemeral, scales to zero when disconnected)
- **Guaranteed QoS:** `resources.requests == resources.limits` (512Mi RAM / 0.5 vCPU)
- HPA for Brain API based on request latency P99

### 4.3 Model Storage
- Per-user `.joblib` files stored in S3 (region-local buckets)
- PostgreSQL stores metadata only: `user_id`, `s3_key`, `trained_at`, `trade_count`
- Model reload on pod startup: < 200ms from S3

## 5. Security Model

### 5.1 Credential Flow
```
User → Mobile App → API Gateway → Vault (Transit Encrypt)
                                        ↓
                              Sentinel Pod (Transit Decrypt at runtime)
                                        ↓
                                   MT5 Terminal
```

### 5.2 IP Protection
- **Rule:** V5 Brain logic NEVER leaves the Control Plane
- **Bridge script:** Relay only — sends telemetry, receives decisions
- **Enforcement:** Code review gate + automated scan in CI

## 6. Onboarding Flow

```
POST /v1/onboard {broker_creds, trade_history}
        ↓
   202 Accepted → {job_id}
        ↓
   BackgroundTask:
     1. Pull 50-500 historical trades from broker
     2. Feature engineering (9 features)
     3. Train per-user IsolationForest + RandomForest
     4. Serialize to .joblib → upload to S3
     5. Store metadata in PostgreSQL
     6. Webhook/WS notification: "Baseline Ready"
        ↓
   GET /v1/onboard/{job_id} → OnboardingStatus
```

**Minimum baseline: 50 trades.** Intervention does not activate until baseline is trained.
