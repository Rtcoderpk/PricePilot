# PricePilot — unified production image (API + worker + db migrations).
#
# Render's Blueprint expects a root `Dockerfile`. This single image contains the
# FastAPI service, the persistent price-monitoring worker, and the Alembic
# migrations. The two Render services (`pricepilot-api`, `pricepilot-worker`)
# run this same image with different start commands.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN addgroup --system app && adduser --system --ingroup app app

COPY services/api/pyproject.toml ./services/api/pyproject.toml
COPY services/api/pricepilot ./services/api/pricepilot
RUN pip install --upgrade pip && pip install -e ./services/api

COPY services/api/ ./services/api/
COPY services/worker/ ./services/worker/
COPY services/db/ ./services/db/

USER app

EXPOSE 8000

# Default: API (migrate + uvicorn). Worker services override the command.
CMD ["sh", "/srv/services/api/prod.sh"]