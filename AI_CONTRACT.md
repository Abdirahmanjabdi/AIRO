# AI Development Contract: Sentinel-Zero

> **Classification:** Mandatory Engineering Standards
> **Version:** 1.0.0
> **Enforcement:** All AI agents (Antigravity, Codex) MUST reference this before writing code.

---

## 1. Development Standards

### 1.1 Strict Typing
- All Python code MUST use `mypy` type hints
- `Any` type is **PROHIBITED** — use explicit types or generics
- Pydantic models for all API boundaries (request/response)

### 1.2 Async First
- All Brain API calls MUST be asynchronous
- Required async libraries: `httpx`, `redis.asyncio`, `asyncpg`
- Synchronous ML prediction calls MUST be wrapped in `asyncio.to_thread()`

### 1.3 Error Handling
- Every MT5 command MUST be wrapped in a circuit-breaker pattern (`pybreaker`)
- **Fail-safe state:** `Risk-Off` (close/block positions)
- Circuit opens after 5 consecutive failures, half-open retry after 30s

### 1.4 Code Organization
- Logic MUST live in `src/sentinel/domain/` and `src/sentinel/brain/`
- **NEVER** place business logic in UI conditionals or API route handlers
- Route handlers: validate → delegate → respond (max 10 lines)

---

## 2. Infrastructure as Code (IaC)

### 2.1 No Manual Changes
- All K8s deployments defined in Helm Charts
- All cloud resources defined in Terraform
- No `kubectl apply` from local machines in production

### 2.2 MT5 Integration
- Codex is **PROHIBITED** from mocking the MT5 Bridge
- Real integration tests with a demo terminal are mandatory
- Headless Wine+MT5 containers must use Guaranteed QoS (limits == requests)

---

## 3. IP Protection

### 3.1 The Cardinal Rule
> **V5 Brain logic MUST NEVER be included in the client-side bridge script.**

### 3.2 Bridge Boundary
- The bridge script is a **RELAY ONLY**
- It sends trade telemetry to the Brain API
- It receives decisions (ALLOW / BLOCK / REDUCE_SIZE)
- It executes decisions on the MT5 terminal
- **NO** anomaly detection, risk classification, or Bayesian logic in the bridge

### 3.3 Enforcement
- If any AI agent attempts to move scoring/classification logic into the bridge → **FLAG AS IP BREACH**
- CI pipeline includes automated scan for prohibited imports in `bridge/`

---

## 4. Data Contracts

### 4.1 Trade Telemetry (Input)
```python
class TradeContext(BaseModel):
    hour_decimal: float           # 0.0 - 23.99
    losing_streak: int            # >= 0
    drawdown_state: float         # >= 0.0
    lot_deviation: float          # z-score
    revenge_timer: float          # minutes since last close
    lots: float                   # > 0.0
    rr_ratio: float               # > 0.0
    realized_vol_20: float        # >= 0.0 (V2)
    trend_momentum: float         # >= 0.0 (V2)
```

### 4.2 Risk Assessment (Output)
```python
class RiskAssessment(BaseModel):
    decision: Literal["ALLOW", "BLOCK", "REDUCE_SIZE"]
    risk_score: float             # 0.0 - 1.0
    is_anomaly: bool
    size_multiplier: float        # 0.0 - 1.0
    explanation: list[FeatureContribution]
    latency_ms: float
```

---

## 5. Model Storage Contract

- Per-user model weights: **S3 / Azure Blob** (NOT PostgreSQL)
- PostgreSQL stores metadata ONLY: `user_id`, `s3_key`, `trained_at`, `trade_count`
- Model format: `.joblib` (scikit-learn serialization)
- Maximum model size: 10MB per user

---

## 6. Handoff Protocols

### 6.1 Antigravity → Codex
- Must include a `knowledge_graph.json` refresh
- Must include `STATUS_HANDOFF.md` with:
  - Completed modules (with test pass/fail status)
  - Pending technical debt
  - Critical secrets / Vault paths

### 6.2 Codex → Master
- Must pass "Lie Detection" audit:
  - No hallucinated library imports
  - No insecure Vault paths
  - No mocked MT5 connections in integration tests
  - No V5 logic in bridge scope

### 6.3 STATUS_HANDOFF.md Template
```markdown
# Status Handoff
## Completed Modules
- [ ] module_name — tests: PASS/FAIL

## Technical Debt
- Issue description → suggested fix

## Vault Paths
- secret/sentinel/mt5/{user_id} — broker credentials
- transit/keys/sentinel-master — encryption key
```
