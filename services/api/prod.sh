#!/usr/bin/env sh
# PricePilot — production API entrypoint (Render web).
#
# Applies Alembic migrations, then starts uvicorn. A failed migration aborts
# startup (no serving on a half-migrated schema). Migration is idempotent.
set -e

echo "[prod] APP_ENV=${APP_ENV:-<unset>} — running migrations"
cd /srv/services/db
alembic upgrade head

echo "[prod] migrations applied — starting uvicorn"
exec uvicorn pricepilot.api:app --host 0.0.0.0 --port "${PORT:-8000}"