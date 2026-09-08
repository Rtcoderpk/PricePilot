# PricePilot — Phase 0 Report

*Date: 2026-09-08 · Greened project. This report audits the (empty) repo, decides architecture, and proposes the exact Phase 1 plan. No implementation happened.*

---

## 1. Repository audit

- **Status:** empty directory at `C:\Users\skku\Downloads\PricePilot`; no code, no git repo yet.
- **References:** `C:\Users\skku\Downloads\CLAUDE.md` → `@AGENTS.md` (no AGENTS.md content found); full PricePilot master spec is in this conversation.
- **Toolchain available:** Node 24.15, npm 12, Python 3.14 (default) **and** Python 3.11 (Store), pip 26, Docker 29.6, git 2.54, Vercel CLI installed.
- **Credentials:** none for an app (no OpenAI/Anthropic/Supabase/Postgres/Redis/Eleven/etc.). The only `ANTHROPIC_*` env vars are the Claude Code harness's **session** auth — not ours, not usable. That is the defining constraint.

## 2. Existing architecture
None. Greenfield.

## 3. Recommended architecture

Web (Next.js 16 App Router + TS + Tailwind + shadcn/ui) on **Vercel** → **FastAPI `/api/v1`** (Docker, Python **3.11-locked**) → Postgres 16 + **pgvector** (Supabase tgt) + Redis (cache + **job broker**). A separate **worker** consumes Redis jobs for alerts + price polling and does async review analysis. Long AI/scrape runs execute in API/worker, **never** in Vercel functions.

## 4. Feature gap analysis

| Area | Status | Gap |
|---|---|---|
| Frontend | 0% | build from scratch |
| API/DB/auth | 0% | build from scratch |
| NL intent | 0% | build |
| Search/Product matching | 0% | build; needs live data |
| Reviews | 0% | needs permitted source (likely "unavailable — config required" initially) |
| Price history | 0% | must be **captured over time**; only real history shown |
| Alerts/workers | 0% | build |
| Forecasting | 0% | skip unless uncertainty model implemented |
| Image/voice/chat | 0% | design; voice Web Speech API; image uncertain ⇒ "possible matches" |

## 5. Database design
See `docs/DATABASE.md`. Core entities: users/profiles/preferences, products + identifiers, merchants/sellers, product_offers, prices (append-only series), reviews + summaries, search_sessions, agent_runs/events, watchlists, price_alerts, notifications, shopping_sessions, embeddings. Money = `numeric(14,2)` + explicit `currency_code`. RLS owner-only for user rows; catalog public read/service write.

## 6. API design
`/api/v1`: `POST /search`, `GET /products`, `GET /products/{id}`, `GET /compare`, `POST /shopping/chat`, `GET /recommendations`, `GET /price-history/{id}`, `GET|POST /alerts`, `GET|POST /watchlist`, `GET|PUT /preferences`, `GET /agents/{run_id}`. Consistent error envelope, pagination, Pydantic schemas, Redis rate limiting.

## 7. AI-agent architecture
See `docs/AI_AGENTS.md`. Typed-DAG: Intent → Search → Match → Research → [Price | Review | Seller] → DealScore → Recommend. Structured Pydantic state per node, validation + bounded retry-with-correction + fallback, max-iter/timeouts, `agent_events` audit trail. Numbers (Deal Score, BUY/WAIT/AVOID) computed by **rules over persisted data**; LLM only writes explanations over those values — never invents them.

## 8. Provider/integrations strategy
All behind interfaces (`AIProvider`, `SearchProvider`, ..., registry + env config). **Live-data reality:** SFCC world keeps the honest path narrow: **OpenFoodFacts** is the only demo-safe live public source (real products/prices, no key, permissive licensing) → use as the first live adapter. Everything else remains a clean, first-class interface explicitly marked "provider unavailable — configure X." AI provider configurable (`openai-compatible` | `ollama`); **no key = graceful degrade, never hardcoded.** No credentials in env here; `.env.example` documents keys.

## 9. Security risks
- **SSRF on user-submitted URLs** (SIBT/URL feature): default-deny allowlist, no private/cloud ranges, scheme/host validation, rate-limited. Highest-priority risk; stays disabled in Phase 1.
- Secrets in frontend/repo → policy is vault/env only; CI secret-scans.
- Prompt injection via any fetched page text → treat as data; structured outputs + validation.
- RLS misconfig → owner-only policies asserted in tests.
- No default **admin/auth** bootstrap in v0 (see decision) — documented, added later.

## 10. Performance risks
- Python 3.14 binary-ecosystem breakage (psycopg/pgvector) → **pin 3.11**.
- Async DB/Redis connection handling in loops → pool sizes + timeouts.
- Long agent runs must not hold user requests → enqueue + poll by `run_id`.
- Provider calls must not serialize → parallel fan-out with deadlines.
- Fixture leakage into "real" claims → `is_fixture` flag on every row + UI badge.

## 11. Deployment architecture
See `docs/DEPLOYMENT.md`. Vercel web; Dockerized API + worker; Redis managed/container; Supabase Postgres+pgvector; GitHub Actions ci → deploy (migrations before rollout); health endpoints; structured logs with `request_id`; CI guards against serverless-bound long jobs.

## 12. Phase 1 implementation plan (next, on approval)

**Foundation only** — no shopping features, no AI.
1. Scaffold monorepo (`apps/web`, `services/{api,worker,db,agents}`), root config, `.env.example`, `.gitignore`, `README`.
2. Backend: FastAPI app + `/health`, `/readyz`, `/api/v1/*` skeleton, Pydantic models, consistent error envelope, structured logging + `request_id` middleware, Redis rate limiting (Redis hook), Supabase-compatible Postgres connection (async pool) from `DATABASE_URL`, without braking on 3.11/3.14 split.
3. Database migrations `001…007` per `DATABASE.md`, plus flake8/pytest harness.
4. Frontend: Next.js 16 App Router scaffold, Tailwind + shadcn/ui, base layout, Landing hero + `SearchResults` shell, `/api/*` internal proxies, shadcn init; smoke-check dev build in-browser.
5. Dockerfile(s) for api + worker; `docker-compose.yml` (db/redis/api/worker); GitHub Actions CI (install→lint→typecheck→units→integ→build→security).
6. Docs: `API.md`, `ENVIRONMENT.md`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md` (only what exists).
7. Verify: lint/typecheck/unit/integration/build all green end-to-end; report changes; **stop** for Phase-2 approval.

## Assumptions & notes
- No Supabase/Redis/OpenAI credentials in this environment → Phase 1 uses local Postgres via `docker compose`, Redis via `docker compose`. Providers unconfigured where no key exists; nothing is fake.
- **Auth deferred to a later phase** (user-facing risk to greenfield velocity), keeping Phase 1 provably correct without third-party setup.
- Possible later re-fork of third-party data: if a buyer-facing retailer integration is added, it must be term/robots/law-compliant and credential-gated, unchanged from §8 policy.