# PricePilot — DEPLOYMENT

**Status:** Phase 8 — production deployment readiness · **Date:** 2026-09-09

## 1. Target topology (approved architecture)

| Component | Target | Notes |
|---|---|---|
| Web (Next.js 16, App Router) | **Vercel** | stateless API client; no DB/Redis on functions |
| API (FastAPI) | **Render** (Docker web service) | long-running async service; single uvicorn worker |
| Worker | **Render** (Docker worker service) | persistent price-monitoring loop (NOT serverless) |
| Redis | Managed (Upstash / Render Redis / Redislabs) | cache + rate limiting; fail-open on outage |
| PostgreSQL + pgvector | **Supabase** (prod) / local container (dev) | migrations via `services/db` |

API and worker share the **same Docker image** (`services/api/Dockerfile`) with a
different startup command:
- API → `services/api/prod.sh` (applies Alembic migrations, then `uvicorn`)
- Worker → `services/worker/run.sh` (`python -m main`, persistent loop)

## 2. Production posture

> **CONTROLLED / PRIVATE deployment.** Identity today is deferred auth via an
> `X-User-Id` UUID header that idempotently creates a user row on first use —
> this is **NOT production authentication.** Anyone can claim any UUID.
> A public multi-user launch is blocked until real authentication (Supabase
> Auth, recommended) is implemented and the identity resolver is replaced.
> See `docs/SECURITY.md` and §9 below.

## 3. Environment variables

**Always injected as env vars, never committed.** `.env.example` is the source
of truth for names; `.env*` is git-ignored. In production set these as platform
secrets on Render, and `NEXT_PUBLIC_*` on Vercel.

### Shared (API + worker)
- `APP_ENV=production`, `LOG_LEVEL=INFO`, `PRICEPILOT_ENABLE_FIXTURES=false`
- `DATABASE_URL` — Supabase DSN (asyncpg). **Includes SSL** (`sslmode=require`).
- `REDIS_URL` — managed Redis DSN (auth + TLS per provider).
- `DB_POOL_SIZE` (default 5), `DB_MAX_OVERFLOW` (10), `DB_POOL_RECYCLE` (1800)
  — tune to the managed Postgres connection limit.

### API
- `JWT_SECRET` — **required strong random value**; the app refuses to start in
  production with the placeholder (Phase 7 guard).
- `PRICEPILOT_PUBLIC_BASE_URL`, `CORS_ORIGIN` (exact frontend origin, no wildcard)
- AI providers (all optional): `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`,
  `AI_BASE_URL`, `AI_TEMPERATURE`, `AI_MAX_TOKENS`, `AI_EMBEDDING_MODEL`
- Invite providers: `PRICEPILOT_EMBEDDING_PROVIDER`, `PRICEPILOT_VISION_PROVIDER`,
  `PRICEPILOT_REVIEW_PROVIDER` (empty = honest unavailable)
- Search: `PRICEPILOT_SEARCH_PROVIDER=openfoodfacts`, `OFF_API_BASE_URL`,
  `OFF_TIMEOUT_SECONDS`, `OFF_MAX_PAGE_SIZE`
- Notifications (optional): `PRICEPILOT_NOTIFICATION_PROVIDER`, `SMTP_HOST`,
  `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SENDER`

### Worker / monitoring
- `MONITOR_ENABLED`, `MONITOR_POLL_INTERVAL_SECONDS`, `MONITOR_PROVIDER_TIMEOUT_SECONDS`,
  `MONITOR_MAX_CONCURRENCY`, `MONITOR_RETRY_COUNT`, `MONITOR_OBSERVATION_WINDOW_SECONDS`

### Web (Vercel)
- `NEXT_PUBLIC_API_BASE_URL` — HTTPS API origin (browser-visible, never a secret)

## 4. Local development

`docker-compose.yml` runs `db` (pgvector:pg16), `redis`, `api` (uvicorn +
migrations on start), and `worker`. Web runs on the host via `npm run dev`.
Postgres/Redis host ports are bound to `127.0.0.1`.

## 5. CI/CD (GitHub Actions)

- **CI (`.github/workflows/ci.yml`)** — on PRs and `main` push: ruff, migrations
  (up → down → up), full pytest against service Postgres+Redis, web lint/
  typecheck/test/build, security (pip-audit, npm audit, gitleaks), Docker build.
  Least-privilege `permissions: contents: read`.
- **Deploy (`.github/workflows/deploy.yml`)** — on `main` push: Vercel production
  deploy (web) and Render deploy trigger (API + worker). Render watches the repo
  branch natively; the API image runs `prod.sh` which applies Alembic migrations
  at startup (guarded, idempotent). A smoke gate validates production URLs.

**No deploy when CI fails.** Secrets are GitHub Secrets / platform env only.

## 6. Production migration procedure

1. Backup the production database (provider snapshot / pg_dump).
2. Verify DB connectivity (`/readyz` or a manual `SELECT 1`).
3. Run `alembic upgrade head` (the API image's `prod.sh` does this at startup).
4. Verify migration head is `0009`.
5. Verify extensions `citext` and `vector` exist.
6. Start the API; confirm `/health` then `/readyz` are green.
7. Start the worker; confirm it logs a monitoring cycle.

No destructive migration runs automatically.

## 7. Rollback

- Web: redeploy the previous known-good commit on Vercel.
- API/Worker: redeploy the previous image/release (Render keeps prior deploys).
- Database migration: roll forward preferred; only `downgrade` if the new schema
  is broken AND data-compatible; otherwise restore from backup first.
- Redis: cache/rate-limit only — flush is safe (fail-open covers outage).

## 8. Observability

- Health: `GET /health` (liveness) and `GET /readyz` (DB required, Redis
  degradable) on the API.
- Logs: structured JSON with `request_id`; **secrets are never logged.**
- Worker: logs each cycle; a failure for one tracked offer never aborts the loop.

## 9. Authentication limitation (blocking public launch)

- Identity = `X-User-Id` UUID (deferred auth). Valid UUIDs auto-create a user row.
- This is safe for a **controlled/private/demo** deployment (invite-only testers).
- It is **not** production-grade: no verified account ownership, no recovery, no
  real per-user auth. **Supabase Auth (JWT) is a prerequisite before broad
  public multi-user launch**, at which point the identity resolver is replaced and
  RLS (already migration-ready in 0007) takes effect.