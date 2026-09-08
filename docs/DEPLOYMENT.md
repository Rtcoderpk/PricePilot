# PricePilot — DEPLOYMENT

**Version:** 0.1 (Phase 0 planning baseline) · **Date:** 2026-09-08

## 1. Target topology

| Component | Target | Notes |
|---|---|---|
| Web (Next.js App Router) | **Vercel** | static/server-rendered surface; no long-running AI/scrape in functions |
| API (FastAPI) | **Dockerized service** | long-running agent work; deployed on a container platform (Render/Fly/Railway or your exact target) |
| Worker | **Dockerized service** | Redis-backed job consumption, price polling, alerts |
| Redis | Managed or container | cache, job broker, rate limiting |
| Postgres + pgvector | **Supabase** (prod) / local container (dev) | migrations via `services/db` |

API and worker may start on the same image with a different entrypoint (`api` vs `worker`).

## 2. Environment matrix

**Always injected as env vars, never committed.** `.env.example` documents every key with safe defaults; `.env*` git-ignored.

### Shared
- `LOG_LEVEL`, `APP_ENV=development|test|production`, `PRICEPILOT_ENABLE_FIXTURES=false`

### API
- `DATABASE_URL` (Postgres/pgvector DSN — Supabase in prod), `REDIS_URL`, `JWT_SECRET`, `PRICEPILOT_PUBLIC_BASE_URL`, `CORS_ORIGIN`
- `AI_PROVIDER`, `AI_MODEL`, `AI_API_KEY`, `AI_BASE_URL`, `AI_TEMPERATURE`, `AI_MAX_TOKENS` (may be `openai-compatible` or `ollama`; no key = graceful unavailable)
- Per-provider: `PROVIDER_<NAME>_API_KEY`, base URLs, rate limits

### Worker
- `DATABASE_URL`, `REDIS_URL`, `ALERT_SWEEP_INTERVAL_SECONDS`, `PRICE_POLL_INTERVAL_SECONDS`, `MAX_ALERTS_PER_SWEEP`

### Web
- `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (public-role only — no secrets)

## 3. Local development

`docker-compose.yml`:
- `db` (postgres:16 + pgvector), `redis`, `api` (uvicorn, reload), `worker` (dev loop), and the web via `pnpm dev`/`npm run dev` locally on the host.
- `services/db` runs migrations on first `api` start.

## 4. CI/CD (GitHub Actions)

Pipeline (`.github/workflows/ci.yml` + `deploy.yml`):
1. **ci**: install → lint → typecheck → unit tests → integration tests → build → security checks (`pip-audit`, `npm audit`, secret scan, basic dep/MV sanity) → fail on any critical.
2. **deploy**: on merge to `main` / tag → Vercel web (via `vercel` CLI or GitHub integration), API+worker images built & pushed, migrations applied before rollout, then rolling updates.

**No deploy when critical checks fail.** Secrets passed as GitHub Secrets (or OIDC).

## 5. Production runbooks

### Migrations
- Apply before new worker/api versions take live traffic (Supabase `db push` or configured runner). Down-scripts provided; tag compatibility so web/API/worker stay on one schema.

### Rollbacks
- Web: Vercel instant rollback / reuse prior preview.
- API: redeploy previous image (DB-compatible), watch `agent_runs` error rate.
- Worker: scale-in before API rollback to avoid alert storms.

### Alerts & observability
- Health: `/healthz` (API, worker, redis ping, db ping) + `/readyz` (migrations applied, schema version).
- Metrics: request latency, provider latency/failures, queue depth, cache hit-rate, DB slow-queries.
- Logs: structured JSON with `request_id`; never secrets. Deploy-time dashboards in target monitor.

## 6. Serverless boundary (must hold)

- Vercel functions only serve read-heavy UI fast-paths (e.g., cached product pages).
- Any multi-agent run, provider crawl, or review analysis executes in **API/worker**.
- CI adds a guard so a "long-running" route does not silently end up in a serverless handler.

## 7. Performance & scaling

- Reads scale horizontally on the API with cached product pages + price snapshots from workers.
- Writes bottlenecked by provider rate limits and Redis queue depth — adequate for the demo/portfolio scale with per-provider throttling.
- pgvector HNSW index handles semantic search at catalog scale; if insert throughput explodes, reindex in worker off-peak.

## 8. Open items before Phase 1 deploy

1. Pin Python base image (3.11-slim) and Node (24) in Dockerfiles/CI.
2. Decide exact container platform for API/worker (Render/Railway/Fly or your preference) — needed before writing `deploy.yml` fully.
3. Supabase project to provision (env pull via Vercel Marketplace).
4. Redis managed URI to provision.
5. Verify `PRICEPILOT_ENABLE_FIXTURES` is `false` in every prod workflow (guard in CI).