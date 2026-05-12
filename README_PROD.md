# Sentinel Trading Production Runbook

This runbook documents how to operate the current Sentinel Trading codebase beyond local development. It is written for a controlled beta. Do not treat this repository as fully validated for broad live enforcement until real MT5 soak tests, production infrastructure load tests, and privacy hardening are complete.

## Production Readiness Position

Current recommended launch mode:

- audit-only for Vanguard users
- `SENTINEL_ENFORCE_MODE=false`
- real MT5 bridge connected to demo or explicitly consented accounts
- operator review of every `BLOCK` and `REDUCE_SIZE` decision before enabling live intervention

Do not enable live close/reduce behavior for general users until:

- repeated MT5 reconnect tests pass
- broker rejection and partial-fill behavior is understood
- intervention idempotency is verified against a real terminal
- infrastructure alerts prove heartbeat and pod replacement behavior

## Environment Variables

### Brain API

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL URL. |
| `REDIS_URL` | Redis URL for cache, queue, heartbeat, and locks. |
| `S3_ENDPOINT` | Optional S3-compatible endpoint, used by MinIO locally. |
| `S3_BUCKET` | Model artifact bucket. |
| `AWS_ACCESS_KEY_ID` | S3 credential when not using IAM role injection. |
| `AWS_SECRET_ACCESS_KEY` | S3 credential when not using IAM role injection. |
| `AWS_DEFAULT_REGION` | AWS region. |
| `VAULT_ADDR` | Vault API URL. |
| `VAULT_ROLE_ID` | Vault AppRole role id. |
| `VAULT_SECRET_ID` | Vault AppRole secret id. |
| `VAULT_TOKEN` | Dev/local token path. Avoid in production. |
| `SENTINEL_REQUIRE_VAULT` | Set to `true` in production. |
| `SENTINEL_MODEL_PATH` | Optional default model path. |
| `PUBLIC_API_BASE_URL` | Callback base URL used in onboarding commands. |
| `CORS_ORIGINS` | Comma-separated frontend origins. |

### MT5 Bridge

| Variable | Purpose |
|---|---|
| `BRAIN_API_URL` | Brain API base URL. |
| `REDIS_URL` | Redis URL. |
| `VAULT_ADDR` | Vault API URL. |
| `VAULT_ROLE_ID` | Vault AppRole role id. |
| `VAULT_SECRET_ID` | Vault AppRole secret id. |
| `SENTINEL_REQUIRE_VAULT` | Set to `true` in production. |
| `SENTINEL_USER_ID` | User identity for a live monitored bridge. |
| `SENTINEL_ENFORCE_MODE` | Defaults to `false`; only `true` sends MT5 close orders. |
| `BRAIN_DECISION_TIMEOUT_SECONDS` | Default `0.5`. Timeout returns a defensive block decision to the bridge. |
| `POLL_INTERVAL` | Bridge polling interval. |
| `SENTINEL_MT5_MODULE` | Test/dev override for mock MT5 module. Do not set for real MT5. |

## Vault Bootstrap

Production should use Vault with AppRole and Transit encryption. The local compose stack uses a dev Vault token only for development.

### Install Vault

```bash
helm upgrade --install sentinel-vault infra/helm/sentinel-vault \
  --namespace sentinel-infra \
  --create-namespace
```

or:

```bash
kubectl apply -f infra/k8s/sentinel-vault.yaml
```

Wait for Vault:

```bash
kubectl rollout status statefulset/sentinel-vault -n sentinel-infra
```

### Initialize And Unseal

Initialize exactly once:

```bash
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- \
  vault operator init -key-shares=5 -key-threshold=3 -format=json > vault-init.json
```

Keep `vault-init.json` offline. Unseal with any three keys:

```bash
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault operator unseal <key-1>
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault operator unseal <key-2>
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault operator unseal <key-3>
```

Login with the root token only for bootstrap:

```bash
kubectl exec -it -n sentinel-infra statefulset/sentinel-vault -- vault login <root-token>
```

### Enable Engines

```bash
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- \
  vault secrets enable -path=sentinel-kv kv-v2

kubectl exec -n sentinel-infra statefulset/sentinel-vault -- \
  vault secrets enable -path=sentinel-transit transit

kubectl exec -n sentinel-infra statefulset/sentinel-vault -- \
  vault write -f sentinel-transit/keys/sentinel-mt5
```

### AppRole

```bash
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- vault auth enable approle
```

Create policy:

```hcl
path "sentinel-kv/data/users/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "sentinel-kv/metadata/users/*" {
  capabilities = ["list", "read"]
}

path "sentinel-transit/encrypt/sentinel-mt5" {
  capabilities = ["update"]
}

path "sentinel-transit/decrypt/sentinel-mt5" {
  capabilities = ["update"]
}

path "sentinel-transit/keys/sentinel-mt5" {
  capabilities = ["read"]
}
```

Apply the policy:

```bash
kubectl exec -i -n sentinel-infra statefulset/sentinel-vault -- \
  vault policy write sentinel-brain -
```

Create the role:

```bash
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- \
  vault write auth/approle/role/sentinel-brain \
  token_policies="sentinel-brain" \
  token_ttl=1h \
  token_max_ttl=4h \
  secret_id_ttl=24h
```

Retrieve credentials:

```bash
kubectl exec -n sentinel-infra statefulset/sentinel-vault -- \
  vault read -field=role_id auth/approle/role/sentinel-brain/role-id

kubectl exec -n sentinel-infra statefulset/sentinel-vault -- \
  vault write -field=secret_id -f auth/approle/role/sentinel-brain/secret-id
```

## Kubernetes Secrets

Brain runtime secret:

```bash
kubectl create secret generic sentinel-brain-runtime \
  --from-literal=DATABASE_URL='<postgres-url>' \
  --from-literal=REDIS_URL='<redis-url>' \
  --from-literal=S3_BUCKET='<model-bucket>' \
  --from-literal=AWS_DEFAULT_REGION='eu-west-2' \
  --from-literal=VAULT_ADDR='http://sentinel-vault.sentinel-infra.svc.cluster.local:8200' \
  --from-literal=VAULT_ROLE_ID='<role-id>' \
  --from-literal=VAULT_SECRET_ID='<secret-id>' \
  --from-literal=SENTINEL_REQUIRE_VAULT='true'
```

MT5 pod runtime secret:

```bash
kubectl create secret generic sentinel-pod-runtime \
  -n sentinel-users \
  --from-literal=VAULT_ADDR='http://sentinel-vault.sentinel-infra.svc.cluster.local:8200' \
  --from-literal=VAULT_ROLE_ID='<role-id>' \
  --from-literal=VAULT_SECRET_ID='<secret-id>' \
  --from-literal=SENTINEL_REQUIRE_VAULT='true'
```

## Deployment

Terraform:

```bash
cd infra/terraform
terraform init
terraform plan -var-file="prod.tfvars"
terraform apply -var-file="prod.tfvars"
```

Brain Helm release:

```bash
helm upgrade --install sentinel-brain infra/helm/sentinel-brain \
  --set image.tag=<image-tag> \
  --wait \
  --timeout=5m
```

Per-user MT5 pod release example:

```bash
helm upgrade --install sentinel-pod-<safe-user-id> infra/helm/sentinel-pod \
  --namespace sentinel-users \
  --create-namespace \
  --set-string env.SENTINEL_USER_ID=<user-id> \
  --set-string userLabels.entries.sentinel-user-id=<user-id>
```

## Readiness Checks

Brain:

```bash
curl http://<brain-host>/healthz
curl http://<brain-host>/readyz
```

Expected production readiness:

- `model_loaded=true`
- `redis_connected=true`
- `db_connected=true`
- `vault_required=true`
- `vault_connected=true`

User profile:

```bash
curl http://<brain-host>/v1/user/<user_id>/profile
```

Dashboard:

```bash
curl http://<brain-host>/v1/user/<user_id>/dashboard
```

## Canary Launch Procedure

1. Deploy the Brain API, Redis, Postgres, S3 bucket, and Vault.
2. Keep `SENTINEL_ENFORCE_MODE=false`.
3. Onboard 5 trusted users.
4. Confirm every user has a distinct profile and onboarding job.
5. Confirm model artifacts appear under `models/{user_id}/brain_v5.joblib` for users with enough history.
6. Confirm blank-baseline users remain safe in bootstrap/shadow modes.
7. Run at least 48 hours of audit-only MT5 telemetry.
8. Review every `BLOCK` and `REDUCE_SIZE` decision.
9. Enable live enforcement only for explicitly consenting users after review.

Abort the canary if:

- two users resolve to the same model key
- audit writes stop while `/v1/analyze` still returns `200`
- Vault reads fail for active bridges
- bridge heartbeats stop during market activity
- MT5 order execution behavior differs from simulator assumptions

## Model Retraining

Automatic retraining from live audits is not fully implemented as a production training pipeline. Current retraining is onboarding-data driven.

Manual retrain path:

1. Store or confirm broker credentials via `/v1/credentials`.
2. Start a new onboarding job via `/v1/onboard`.
3. Let the bridge submit history or post curated data to `/v1/onboard/data`.
4. Wait for the job to reach `ready`.
5. Confirm `model_s3_key` and `trained_at` changed on the user profile.

## Incident Response

### Vault Unavailable

Expected behavior:

- `/readyz` reports `vault_required=true` and `vault_connected=false`
- credential storage/retrieval fails

Action:

- do not onboard new users
- restart or unseal Vault
- rotate AppRole secret if needed
- restart affected Brain/bridge deployments after secret restoration

### Redis Unavailable

Expected impact:

- risk cache unavailable
- onboarding queue unavailable
- heartbeats unavailable
- intervention idempotency locks unavailable

Action:

- keep enforcement disabled until Redis is healthy
- restore Redis before resuming live bridge enforcement
- for production, migrate to a highly available Redis topology

### MT5 Terminal Disconnect

Current bridge behavior:

- a single `positions_get()` failure does not trigger global close-all
- five consecutive failures plus confirmed `terminal_info() is None` are required
- close-all only executes if `SENTINEL_ENFORCE_MODE=true`

Action:

- inspect bridge logs
- confirm whether reconnect succeeds
- keep audit-only mode until disconnect behavior is understood for the broker

## Local Reset

Use this for a clean local canary rebuild:

```powershell
docker compose down --volumes --remove-orphans
docker compose up -d --build
```

If Terraform local state is stale:

```powershell
if (Test-Path infra/terraform/.terraform) { Remove-Item infra/terraform/.terraform -Recurse -Force }
if (Test-Path infra/terraform/.terraform.lock.hcl) { Remove-Item infra/terraform/.terraform.lock.hcl -Force }
terraform -chdir=infra/terraform init -backend=false
```

## Production Gaps To Close

Before claiming broad production readiness:

- add Alembic migrations for current DB schema
- add ALB/Ingress through AWS Load Balancer Controller or Terraform
- migrate Redis to cluster mode or HA replication group
- add Karpenter or EKS Auto Mode for data-plane elasticity
- add a pod reaper/reprovisioning controller for stalled MT5 pods
- field-encrypt or pseudonymize PII
- add retention/deletion workflows for audit data
- run real MT5 enforcement soak tests
- document broker-specific filling modes and rejection handling
