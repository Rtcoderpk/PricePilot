# PricePilot — Autonomous AI Shopping Agent

Tell PricePilot what you want to buy; it researches products, compares stores,
analyzes prices and reviews, evaluates sellers, and returns an **explainable**
recommendation.

> **Status: Phase 1 (foundation).** Live search works against the real
> OpenFoodFacts public API. AI agents, price tracking, and advanced features are
> in later phases (see roadmap below). No data is ever fabricated; unavailable
> providers are reported as unavailable.

---

## What's real right now

- **AI Shopping Agent** (Phase 3) — `POST /api/v1/shopping/search` parses intent,
  searches providers concurrently, deduplicates, analyzes real offers/price/sellers,
  and ranks explainable recommendations with hard-constraint enforcement.
  Typed Pydantic state; no unstructured dict. No fabrication. Deterministic fallback
  when no LLM key is configured.
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
| 3 | AI agents (intent → recommendation) | planned |
| 4 | SIBT, chat, image/voice, review intelligence | planned |
| 5 | Price monitoring, alerts, worker jobs | planned |
| 6 | Premium UI (dashboard, compare, track, alerts) | planned |

See `docs/` for detail. **No feature is documented as done until it exists.**

## Configuration

See `.env.example` and `docs/ENVIRONMENT.md`. `docker compose` provides local DB
and Redis; the API applies migrations on startup.