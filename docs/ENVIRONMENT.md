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
| `PRICEPILOT_EMBEDDING_PROVIDER` | *(empty)* | `openai-compatible` to enable pgvector semantic search; empty → keyword fallback (honest `semantic:"keyword"`) |
| `PRICEPILOT_VISION_PROVIDER` | *(empty)* | not yet implemented; empty → image upload returns honest "vision not configured" |
| `PRICEPILOT_REVIEW_PROVIDER` | *(empty)* | not yet implemented; review agent reads real `reviews` rows + theme extraction |
| `AI_EMBEDDING_MODEL` | *(empty)* | e.g. `text-embedding-3-small` (1536-dim matches the table) |
| `MONITOR_ENABLED` | `true` | master switch for the Phase 5 monitoring worker |
| `MONITOR_POLL_INTERVAL_SECONDS` | `3600` | price polling cadence (1 sample/hour per offer by default) |
| `MONITOR_PROVIDER_TIMEOUT_SECONDS` | `15.0` | per-provider request budget in the worker |
| `MONITOR_MAX_CONCURRENCY` | `4` | bounded parallel polls per cycle |
| `MONITOR_RETRY_COUNT` | `2` | retries on transient provider failure (exponential backoff) |
| `MONITOR_OBSERVATION_WINDOW_SECONDS` | `3600` | dedupe window — unchanged prices not re-inserted within it |

## Notifications (Phase 5)

| Variable | Default | Notes |
|---|---|---|
| `PRICEPILOT_NOTIFICATION_PROVIDER` | *(empty)* | `email` when SMTP is configured; empty → honest no-op (in-app alerts still persist) |
| `SMTP_HOST` / `SMTP_PORT` | *(empty)* / `587` | requires username+password+sender to enable email |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | *(empty)* | secrets — never commit |
| `SMTP_SENDER` | *(empty)* | envelope sender for alert emails |

## Web

| Variable | Default | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | API origin the browser/server calls |

## Security

- **No secrets in the frontend.** Only `NEXT_PUBLIC_*` values ship to the client.
- CI runs a secret scan (gitleaks) and dependency audits (`pip-audit`, `npm audit`).
- `PRICEPILOT_ENABLE_FIXTURES=true` is a dev-only escape hatch and is guarded in CI.