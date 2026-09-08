# PricePilot — Environment

Every value is read from the environment (or a `.env` file at the repo root).
**Never commit `.env`.** Copy `.env.example` → `.env` and fill in real values.

`docker compose` reads `.env` for the `api`/`worker` services unless the
compose `environment:` block overrides it (it hardcodes local DB/Redis DSNs for
the port mappings shown).

## Common

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development` \| `test` \| `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `PRICEPILOT_ENABLE_FIXTURES` | `false` | dev-only demo corpus; **must stay `false` in prod** |

## API

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | local asyncpg DSN | used for app + readiness; Alembic auto-converts to sync psycopg |
| `REDIS_URL` | `redis://localhost:6379/0` | cache + rate limiting |
| `PRICEPILOT_PUBLIC_BASE_URL` | `http://localhost:8000` | seen in docs/health |
| `CORS_ORIGIN` | `http://localhost:3000` | web origin allowed by CORS |
| `JWT_SECRET` | placeholder | auth is deferred, placeholder only |

## Search providers

| Variable | Default | Notes |
|---|---|---|
| `PRICEPILOT_SEARCH_PROVIDER` | `openfoodfacts` | currently only `openfoodfacts` |
| `OFF_API_BASE_URL` | `https://world.openfoodfacts.org` | keyless public API |
| `OFF_TIMEOUT_SECONDS` | `12` | per-request budget |
| `OFF_MAX_PAGE_SIZE` | `20` | bounded page size (respects API) |

## AI providers (Phase 3 — optional now)

| Variable | Notes |
|---|---|
| `AI_PROVIDER` | `openai-compatible` \| `ollama`; leave empty to disable (graceful degrade) |
| `AI_MODEL` | model id |
| `AI_API_KEY` | secret — never commit |
| `AI_BASE_URL` | endpoint override for compat/ollama |
| `AI_TEMPERATURE` | default `0.2` |
| `AI_MAX_TOKENS` | default `2048` |

## Worker

| Variable | Default | Notes |
|---|---|---|
| `ALERT_SWEEP_INTERVAL_SECONDS` | `300` | alert sweep cadence (Phase 5) |
| `PRICE_POLL_INTERVAL_SECONDS` | `3600` | price polling cadence (Phase 5) |
| `MAX_ALERTS_PER_SWEEP` | `100` | cap per sweep |

## Web

| Variable | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | API origin the browser/server calls |

## Security

- **No secrets in the frontend.** Only `NEXT_PUBLIC_*` values ship to the client.
- CI runs a secret scan (gitleaks) and dependency audits (`pip-audit`, `npm audit`).
- `PRICEPILOT_ENABLE_FIXTURES=true` is a dev-only escape hatch and is guarded in CI.