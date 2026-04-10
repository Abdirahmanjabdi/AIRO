# Sentinel-Zero Production Manifesto

## Purpose

Sentinel-Zero is an identity-first trading governance platform. Each trader is scored against their own behavioral baseline, their credentials are isolated in Vault, and their personalized model is persisted as a `.joblib` artifact in S3/MinIO.

This document is the operational runbook for the production-only controls that matter most:

- Vault master key rotation
- manual model retraining for trading-style drift
- canary launch expectations

## Identity and Model Mapping

The production inference path is keyed by `user_id`.

- The frontend submits `user_id` from `BrokerConnectCard.tsx`
- the onboarding API persists that `user_id`
- the model store writes the artifact to `models/{user_id}/brain_v5.joblib`
- runtime inference resolves the same `user_id` back to that object key before scoring

This is the core guarantee that prevents model cross-contamination between traders.

## Vault Master Key Rotation

### Goal

Rotate Vault sealing material and broker-secret access safely without exposing MT5 credentials or interrupting active scoring longer than necessary.

### Preconditions

- Confirm the Vault cluster is healthy
- Confirm at least 3 unseal key holders are available if using Shamir unseal
- Pause non-essential deploys during the rotation window
- Verify that Sentinel pods can tolerate a short credential-refresh interruption

### Procedure

1. Snapshot the current Vault state:
   - `vault status`
   - `vault operator raft snapshot save sentinel-vault-$(Get-Date -Format yyyyMMddHHmmss).snap`
2. Rotate the transit or root material according to your Vault operating mode:
   - For transit-backed application encryption keys: `vault write -f transit/keys/sentinel-master/rotate`
   - For recovery or rekey operations: `vault operator rekey -init`
3. If AppRole credentials are rotated, issue new credentials:
   - `vault read auth/approle/role/sentinel-brain/role-id`
   - `vault write -f auth/approle/role/sentinel-brain/secret-id`
4. Update Kubernetes secrets or your CI secret manager with the new Vault access material.
5. Restart only the bridge and brain workloads after secrets are updated:
   - `kubectl rollout restart deployment/<brain-release>-brain`
   - `kubectl rollout restart deployment/<pod-release>-pod`
6. Validate:
   - `GET /readyz` returns Redis and DB connected
   - a credentialed onboarding request succeeds
   - Vault read/write for one test user succeeds

### Post-Rotation Checks

- Confirm no onboarding jobs are stuck in `pulling_history`
- Confirm no new `403` or authentication warnings are appearing in bridge logs
- Confirm risk audits continue writing to Postgres

## Manual S3 Model Retrain

### When to Retrain

Trigger a manual retrain if a trader's behavior profile has clearly changed, for example:

- they changed asset class or broker
- average lot size drifted materially
- revenge-trading signatures no longer match current behavior
- a support review confirms sustained concept drift

### Manual Retrain Workflow

1. Identify the `user_id`.
2. Pull the latest historical trades from MT5 through the bridge path or an approved backfill process.
3. Start a new onboarding cycle for that user:
   - `POST /v1/onboard`
4. Submit refreshed historical trades to:
   - `POST /v1/onboard/data`
5. Wait for the onboarding job to reach `ready`.
6. Confirm the updated model object exists in S3/MinIO:
   - `models/{user_id}/brain_v5.joblib`
7. Confirm the user profile now points at the new object key and updated `trained_at`.

### Forced Retrain With Existing Infrastructure

If you need to trigger a retrain from the local stack:

1. Store credentials:
   - `POST /v1/credentials`
2. Start onboarding:
   - `POST /v1/onboard`
3. Let the bridge fetch MT5 history, or submit curated history directly to:
   - `POST /v1/onboard/data`

### What Success Looks Like

- `GET /v1/user/{user_id}/profile` shows `is_baseline_ready=true`
- the user's `model_s3_key` is populated
- new `/v1/analyze` calls resolve that user-specific model
- a fresh `.joblib` appears in the bucket path for that user

## Blank Baseline Policy

If `history_deals_get()` returns no deals for a new account, Sentinel-Zero must not crash or fail onboarding.

Expected behavior:

- the bridge posts an empty history payload
- the API records a `blank_baseline` onboarding state
- the user profile remains `is_baseline_ready=false`
- inference falls back to `baseline_pending` risk mode until enough history exists

This keeps the system safe while still onboarding net-new traders cleanly.

## Canary Launch Checklist

## Nuclear Reset

Use this sequence before a clean canary rebuild if the local stack has stale containers, old volumes, or inconsistent Terraform state:

1. Stop and remove the compose stack:
   - `docker compose down --volumes --remove-orphans`
2. Remove any leftover project containers:
   - `docker ps -a --filter "name=sentineltrading" --format "{{.ID}}" | ForEach-Object { docker rm -f $_ }`
3. Remove any leftover project networks:
   - `docker network ls --filter "name=sentineltrading" --format "{{.ID}}" | ForEach-Object { docker network rm $_ }`
4. Remove local project volumes:
   - `docker volume ls --filter "name=sentineltrading" --format "{{.Name}}" | ForEach-Object { docker volume rm $_ }`
5. Recreate Terraform local state:
   - `if (Test-Path infra/terraform/.terraform) { Remove-Item infra/terraform/.terraform -Recurse -Force }`
   - `if (Test-Path infra/terraform/.terraform.lock.hcl) { Remove-Item infra/terraform/.terraform.lock.hcl -Force }`
   - `terraform -chdir=infra/terraform init -backend=false`
6. Rebuild the canary stack:
   - `docker compose up -d --build`

This resets Redis, Postgres, MinIO, Vault dev state, and the local Terraform working directory.

### Local High-Fidelity Stack

Use the compose stack with the MT5 simulator enabled:

- `docker compose up --build`

The bridge is configured to load `tests.mocks.mt5_simulator` in local development so onboarding can complete without a live broker account.

### The First Five

For the initial canary cohort:

- onboard 5 trusted traders
- watch Postgres onboarding and audit rows
- watch Redis heartbeats and onboarding queue depth
- watch MinIO/S3 for five `.joblib` objects

You are production-live when:

- all five traders receive distinct model artifacts
- `/v1/analyze` serves identity-specific assessments
- Vault credential flow remains healthy after restarts

## Launch URLs

For the local canary environment:

- App: `http://localhost:3000`
- Brain API docs: `http://localhost:8000/docs`
- Whop webhook endpoint: `http://localhost:8000/v1/webhooks/whop`

## Failure Triggers

Abort or roll back the canary if any of the following happen:

- multiple traders resolve to the same `model_s3_key`
- onboarding jobs stall in `pulling_history` or `training`
- bridge heartbeats drop during market activity
- Postgres audit writes stop while `/v1/analyze` still returns `200`
- Vault credential reads fail for active pods
