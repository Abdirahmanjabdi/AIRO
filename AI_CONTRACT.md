# Sentinel Trading Contributor And AI Contract

This file defines rules for future AI agents and human contributors working in this repository. It is intentionally strict where user capital, credentials, and model boundaries are involved.

## 1. Truthfulness Rules

- Do not document aspirational behavior as implemented behavior.
- If a feature is a roadmap item, label it as a roadmap item.
- Do not claim live production readiness without real MT5 enforcement soak tests and infrastructure validation.
- Do not claim the system predicts market direction or guarantees trading profitability.
- Keep README, architecture, and production docs in sync with code changes.

## 2. Core Architecture Boundary

The system has two lanes:

- **Brain/control plane:** FastAPI, domain models, feature engineering, ML scoring, audits, model storage.
- **Bridge/data plane:** MT5 connectivity, history pull, telemetry relay, optional execution.

The V5 risk logic must stay in the Brain/control plane. The bridge may derive raw telemetry from MT5 account and position data, but it must not import or run `SentinelBrain`, `IsolationForest`, `RandomForestClassifier`, SHAP, Optuna, or training logic.

## 3. Safety Rules For MT5 Execution

Live intervention is dangerous. Treat every code path that calls `mt5.order_send()` as capital-affecting.

Required safeguards:

- `SENTINEL_ENFORCE_MODE` must default to `false`.
- MT5 execution must be skipped in audit-only mode.
- Every intervention must use a per-ticket idempotency lock.
- A global close-all fail-safe must require repeated failures and a confirmed terminal disconnect.
- Never add logic that can repeatedly close the same ticket every polling cycle.
- Never add automatic reverse-position logic.
- Prefer explicit operator review for new enforcement behavior.

## 4. Cold-Start And Model Rules

Implemented states:

- `maturity_0`: zero-history bootstrap scoring using Risk DNA.
- `maturity_1`: early-history shadow mode.
- `maturity_2`: full trained model scoring.

Rules:

- Do not replace relative/user-specific limits with global hard lot limits.
- Do not flag a high-lot trader simply because they trade high lots.
- Use relative deviation or user baseline features whenever possible.
- Keep cold-start logic conservative and explainable.
- Label K-Means or Optuna services as roadmap until they are actually implemented.

## 5. API And Domain Contracts

- All API request/response boundaries should use Pydantic models in `src/sentinel/domain/models.py`.
- Frontend TypeScript types in `frontend/src/lib/api.ts` must match backend response shapes.
- Route handlers should validate, delegate, persist/audit, and respond.
- Shared business logic should live in `src/sentinel/brain/`, `src/sentinel/domain/`, or a dedicated service module, not in UI conditionals.

## 6. Persistence And Privacy

Current storage:

- broker password material belongs in Vault, not PostgreSQL
- API keys are hashed before storage
- model artifacts belong in S3/MinIO, not PostgreSQL
- audits and user metadata currently store clear identifiers

Rules:

- Do not log plaintext broker passwords.
- Do not store plaintext broker passwords in DB or Redis.
- Do not add secrets to source files, Helm values, Terraform vars, or tests except clearly fake local-dev defaults.
- Treat `user_id`, `account_id`, and email as sensitive.
- Add pseudonymization or field encryption before claiming production-grade fintech privacy.

## 7. Testing Rules

Required before push:

```bash
python -m pytest -q
cd frontend
npm run lint
npm run build
```

Use the committed MT5 simulator for automated tests. Real MT5 demo/live-terminal testing is still required before enabling enforcement for users.

Good tests to add:

- duplicate ticket intervention is skipped
- fail-safe does not fire on one transient MT5 error
- maturity advances correctly from live audits
- blank-baseline onboarding remains safe
- cached risk assessment still persists audits as expected

## 8. Infrastructure Rules

Current Terraform is controlled-beta infrastructure, not a complete 10k-user platform.

Do not claim 10k-user production scalability until these are implemented and tested:

- HA or cluster-mode Redis
- ALB/Ingress production exposure
- EKS Auto Mode or Karpenter-based data-plane elasticity
- MT5 pod reaper/reprovisioning controller
- multi-AZ operational validation
- observability for bridge heartbeat, queue depth, p99 latency, order-send failures, and model load failures

## 9. Documentation Rules

When changing behavior, update docs in the same change:

- `README.md` for product and developer overview
- `ARCHITECTURE.md` for system design
- `README_PROD.md` for operations
- this file for contributor rules if safety boundaries change

Use ASCII in documentation unless there is a strong reason not to.

## 10. Push Checklist

Before pushing:

- run backend tests
- run frontend lint and build
- check `git diff --check`
- inspect changed files for secrets
- inspect docs for claims that exceed actual code
- confirm `SENTINEL_ENFORCE_MODE` still defaults to false

If any of those fail, do not push.
