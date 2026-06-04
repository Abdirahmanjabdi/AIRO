#!/bin/sh
set -e

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head 2>/dev/null || echo "[entrypoint] Alembic migration skipped (DB may not be ready yet — init_db will handle it)"

echo "[entrypoint] Starting Sentinel Brain API..."
exec uvicorn sentinel.api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${UVICORN_WORKERS:-4}" \
    --limit-concurrency 1000
