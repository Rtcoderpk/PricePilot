# PricePilot — Autonomous AI Shopping Agent

Tell PricePilot what you want to buy; it researches products, compares stores,
analyzes prices and reviews, evaluates sellers, and returns an **explainable**
recommendation.

> **Status: Phase 8 (production deployment readiness).** Live search against the
> real OpenFoodFacts API, AI shopping agent, price monitoring/tracking/alerts,
> premium UI, and security hardening are all complete and verified. This
> deployment is **controlled/private** — identity is a deferred-auth `X-User-Id`
> UUID, NOT production authentication. Real user authentication is required
> before a public multi-user launch. No data is ever fabricated; unavailable
> providers are reported as unavailable.

---

## What's real right now

- **AI Shopping Agent** (Phase 3) — `POST /api/v1/shopping/search` parses intent,
  searches providers concurrently, deduplicates, analyzes real offers/price/sellers,
  and ranks explainable recommendations with hard-constraint enforcement.
  Typed Pydantic state; no unstructured dict. No fabrication. Deterministic fallback
  when no LLM key is configured.
- **Advanced AI surface** (Phase 4):
  - **Should I Buy?** — explainable BUY / WAIT / AVOID / insufficient-data verdict
    per product from real signals.
  - **Multi-turn chat** — `POST /api/v1/shopping/chat` with session persistence and
    deterministic refinements ("only <brand>", "cheaper", "under N", "ignore
    refurbished", "more results").
  - **Voice input** — browser Web Speech API (honest "not supported" fallback).
  - **Image shopping** — `POST /api/v1/shopping/image` with strict validation and
    honest "vision not configured" response when no provider.
  - **Review intelligence** — real `reviews` theme extraction + `review_summaries`
    upsert; honest `review_data_unavailable` when no reviews exist.
  - **Semantic search / RAG** — pgvector service + embedding provider interface;
    keyword fallback when unconfigured (honest `semantic:"keyword"` status).
  - **Price forecasting** — uncertainty-gated (range + confidence), only with ≥30
    real history samples; else `insufficient_history`.
- **Canonical product engine** (Phase 2) — raw offers are normalized, identifiers
  extracted (GTIN/barcode), and deterministically matched into deduplicated
  variant-level products with multiple merchant offers.
- **Live search** — `POST /api/v1/search` queries OpenFoodFacts (real products).
- **Provider abstraction** — slots for search/AI providers; unconfigured slots
  reported as `unavailable`, never simulated.
- **Redis-backed search cache + rate limiting**.
- **PostgreSQL schema** (Alembic migrations, pgvector, RLS-ready) via `docker compose`.
- **FastAPI service + background worker** (Dockerized, health/readiness probes).
- **Next.js 16 frontend** — landing, canonical search cards, and `/shopping` AI agent
  page with intent display, recommendations, deal score, and seller/review status.
- **GitHub Actions CI** (lint, typecheck, tests, build, security, Docker builds).

## How to run locally

Requirements: Docker Desktop, Node 24, Python 3.11.

```bash
# 1. Start Postgres + Redis + FastAPI + worker
docker compose up --build

# 2. Web app (another terminal)
cd apps/web
npm install
npm run dev          # http://localhost:3000

# 3. API docs
# http://localhost:8000/docs
```

Search something: `http://localhost:3000/search?q=nutella`.

## Repository layout

```
apps/web          Next.js 16 web app (Vercel-ready)
services/api      FastAPI service (Python 3.11)
services/worker   background process (alerts/price polling in Phase 5)
services/db       Alembic migrations + schema
docs/             architecture, database, agents, deployment, API, env
.github/workflows CI/CD
```

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Audit + architecture | done |
| 1 | Foundation | done |
| 2 | Product intelligence (normalization, matching, dedup, multi-provider) | done |
| 3 | AI agents (intent → recommendation) | done |
| 4 | Advanced AI (SIBT, chat, voice, image, reviews, semantic, forecast) | done |
| 5 | Price monitoring, alerts, worker jobs | done |
| 6 | Premium UI (dashboard, compare, track, alerts) | done |
| 7 | Security, testing, production hardening | done |
| 8 | Production deployment & launch readiness | done (controlled/private) |
| 9 | Real authentication (Supabase Auth), public launch | planned |

See `docs/` for detail (especially `docs/DEPLOYMENT.md`, `docs/ENVIRONMENT.md`).
**No feature is documented as done until it exists.**

## Configuration

See `.env.example` and `docs/ENVIRONMENT.md`. `docker compose` provides local DB
and Redis; the API applies migrations on startup.