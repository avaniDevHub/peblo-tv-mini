#!/usr/bin/env bash
# API container entrypoint:
#   1) run DB migrations (with retry while Postgres finishes starting)
#   2) seed + optional demo publish (idempotent — safe on every start)
#   3) start the API server
set -euo pipefail

echo "[entrypoint] Running database migrations (alembic upgrade head)..."
migrated=0
for i in $(seq 1 15); do
  if alembic upgrade head; then
    migrated=1
    break
  fi
  echo "[entrypoint] migration attempt ${i} failed (DB not ready yet?) — retrying in 2s..."
  sleep 2
done
if [ "${migrated}" -ne 1 ]; then
  echo "[entrypoint] ERROR: migrations did not succeed after multiple attempts." >&2
  exit 1
fi

echo "[entrypoint] Seeding data + optional demo publish (idempotent)..."
# Non-fatal: even if publish stays blocked, the API is fully usable and the
# viewer simply shows its empty state.
python -m app.bootstrap || echo "[entrypoint] bootstrap reported issues (non-fatal) — see logs above."

echo "[entrypoint] Starting API on 0.0.0.0:8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
