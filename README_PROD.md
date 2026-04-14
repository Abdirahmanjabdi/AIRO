# Sentinel-Zero Production Manifesto

## Purpose

Sentinel-Zero is an identity-first trading governance platform. Each trader is scored against their own behavioral baseline, their credentials are isolated in Vault, and their personalized model is persisted as a `.joblib` artifact in S3/MinIO.

This document is the operational runbook for the production-only controls that matter most:

- Vault deployment and AppRole bootstrap
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

## Vault Deployment and Bootstrap

### Goal

Deploy Vault inside the cluster, initialize it once, enable the engines Sentinel uses, and inject AppRole credentials into the brain and MT5 bridge through Kubernetes secrets.

### Procedure

1. Install the in-cluster Vault release:
   - `helm upgrade --install sentinel-vault infra/helm/sentinel-vault --namespace sentinel-infra --create-namespace`
   - or `kubectl apply -f infra/k8s/sentinel-vault.yaml`
2. Wait for the stateful pod:
   - `kubectl rollout status statefulset/sentinel-vault -n sentinel-infra`
3. Initialize Vault exactly once and keep the output offline:
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault operator init -key-shares=5 -key-threshold=3 -format=json > vault-init.json`
4. Unseal using any 3 of the returned unseal keys:
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault operator unseal <key-1>`
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault operator unseal <key-2>`
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault operator unseal <key-3>`
5. Log in with the root token from `vault-init.json`:
   - `kubectl exec -it -n sentinel-infra statefulset/sentinel-vault -- vault login <root-token>`
6. Enable the secret engines Sentinel expects:
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault secrets enable -path=sentinel-kv kv-v2`
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault secrets enable -path=sentinel-transit transit`
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault write -f sentinel-transit/keys/sentinel-mt5`
7. Enable AppRole auth:
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault auth enable approle`
8. Create the Sentinel policy:
   - `kubectl exec -i -n sentinel-infra statefulset/sentinel-vault -- vault policy write sentinel-brain - <<'EOF'`
   - `path "sentinel-kv/data/users/*" { capabilities = ["create", "read", "update", "delete", "list"] }`
   - `path "sentinel-kv/metadata/users/*" { capabilities = ["list", "read"] }`
   - `path "sentinel-transit/encrypt/sentinel-mt5" { capabilities = ["update"] }`
   - `path "sentinel-transit/decrypt/sentinel-mt5" { capabilities = ["update"] }`
   - `path "sentinel-transit/keys/sentinel-mt5" { capabilities = ["read"] }`
   - `EOF`
9. Create the AppRole used by Sentinel workloads:
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault write auth/approle/role/sentinel-brain token_policies="sentinel-brain" token_ttl=1h token_max_ttl=4h secret_id_ttl=24h`
10. Retrieve the AppRole credentials:
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault read -field=role_id auth/approle/role/sentinel-brain/role-id`
   - `kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault write -field=secret_id -f auth/approle/role/sentinel-brain/secret-id`
11. Create the runtime secret for the API deployment:
   - `kubectl create secret generic sentinel-brain-runtime -n default --from-literal=DATABASE_URL='<postgres-url>' --from-literal=REDIS_URL='<redis-url>' --from-literal=S3_BUCKET='<model-bucket>' --from-literal=AWS_DEFAULT_REGION='eu-west-2' --from-literal=VAULT_ADDR='http://sentinel-vault.sentinel-infra.svc.cluster.local:8200' --from-literal=VAULT_ROLE_ID='<role-id>' --from-literal=VAULT_SECRET_ID='<secret-id>' --from-literal=SENTINEL_REQUIRE_VAULT='true'`
12. Create the runtime secret for the MT5 bridge or per-user pod release:
   - `kubectl create secret generic sentinel-pod-runtime -n sentinel-users --from-literal=VAULT_ADDR='http://sentinel-vault.sentinel-infra.svc.cluster.local:8200' --from-literal=VAULT_ROLE_ID='<role-id>' --from-literal=VAULT_SECRET_ID='<secret-id>' --from-literal=SENTINEL_REQUIRE_VAULT='true'`
13. Restart the brain and bridge workloads after the secrets exist:
   - `kubectl rollout restart deployment/sentinel-brain -n default`
   - `kubectl rollout restart deployment/<bridge-or-user-pod-release> -n sentinel-users`
14. Validate:
   - `GET /readyz` returns `vault_connected=true`
   - backend logs no longer show `fallback_memory_store`
   - `POST /v1/credentials` succeeds and writes ciphertext to Vault

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
