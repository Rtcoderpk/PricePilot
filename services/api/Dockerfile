# PricePilot API image
#
# Runs the FastAPI service. SQL migrations are applied via the `alembic`
# override (entrypoint script) referenced in docker-compose and CI.

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
COPY services/db/ ./services/db/

USER app

EXPOSE 8000

# Production default: apply Alembic migrations, then start uvicorn.
# A platform override may supply a migration-free `uvicorn` start command.
CMD ["sh", "/srv/services/api/prod.sh"]