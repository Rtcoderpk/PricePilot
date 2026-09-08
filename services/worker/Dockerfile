# PricePilot worker image
#
# Shares the API source (same env/config/db/wiring); only the entrypoint
# differs — this process runs the background loop, not a web server.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN addgroup --system app && adduser --system --ingroup app app

# Install dependencies first (better layer caching)
COPY services/api/pyproject.toml ./services/api/pyproject.toml
COPY services/api/pricepilot ./services/api/pricepilot
RUN pip install --upgrade pip && pip install -e ./services/api

COPY services/api/ ./services/api/
COPY services/worker/ ./services/worker/
COPY services/db/ ./services/db/

USER app

CMD ["/bin/sh", "/srv/services/worker/run.sh"]