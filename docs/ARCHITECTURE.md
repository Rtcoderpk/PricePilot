# PricePilot — ARCHITECTURE

**Version:** 0.1 (Phase 0 planning baseline) · **Date:** 2026-09-08

## 1. Topology

```
                 ┌─────────────────────────────────────────────┐
                 │  Web (Next.js 16 App Router) → Vercel        │
                 │  Server Components for shell/SEO,             │
                 │  client islands for interactive surfaces      │
                 └───────────────┬─────────────────────────────┘
                                 │ HTTPS + bearer/JWT
                 ┌───────────────▼─────────────────────────────┐
                 │  API (FastAPI, /api/v1) — long-running AI &   │
                 │  provider work lives here, NOT on Vercel      │
                 └───────┬───────────────────┬──────────────────┘
                         │                   │
              ┌──────────▼─────────┐  ┌──────▼────────────────┐
              │ Postgres + pgvector │  │ Redis (cache, queues, │
              │ (Supabase target)   │  │ sessions, rate limits,│
              └──────────┬─────────┘  │ job broker)           │
                         │            └──────┬────────────────┘
                 ┌───────▼─────────┐  ┌──────▼────────────────┐
                 │ Worker service  │  │ AI/Search/Review/     │
                 │ (alerts, price   │  │ Provider adapters     │
                 │  polling, jobs) │  │ (rate-limited,        │
                 └─────────────────┘  │  term-compliant)      │
                                     └───────────────────────┘
```

- **Web** → Vercel. NO long-running scrape/AI jobs in serverless functions.
- **API** → Dockerized FastAPI, deployed independently.
- **Worker** → separate Dockerized service; consumes Redis-backed jobs.
- **Postgres/pgvector** → Supabase for production target; local Postgres for dev.
- **Redis** → managed or container.

## 2. Repository layout

```
PricePilot/
├── apps/
│   └── web/                Next.js 16 (App Router, TS, Tailwind, shadcn/ui)
├── packages/               (shared types kept boring; avoid over-sharing)
├── services/
│   ├── api/                FastAPI service                             (Python 3.11)
│   ├── worker/             background jobs: alerts, price polling      (Python 3.11)
│   ├── agents/             shared agent + provider + tools library (/ai)
│   └── db/                 migrations, seed, fixtures
├── docker-compose.yml       dev: api, worker, redis, postgres
├── .github/workflows/       CI/CD
└── docs/                    Architecture, DB, AI agents, Deployment, API, Env
```

Rationale: separating `agents/` into its own installable package keeps AI logic out of both the API routes and the UI, and lets the worker import the same agent library.

## 3. Stack decisions

| Concern | Choice | Why |
|---|---|---|
| Web framework | Next.js 16 App Router + TS | Vercel-native, server components, image/CDN |
| UI | Tailwind + shadcn/ui | Accessible, composable, premium look |
| API | FastAPI + Pydantic v2 | Async, typed schemas, OpenAPI for free |
| Python runtime | 3.11 (locked) | 3.14 has immature binary-ecosystem support (psycopg/pgvector, etc.); 3.11 is the safe target |
| Agent orchestration | **Potpie/Nextchain** (a LangGraph-for-FastAPI native Node graph) | See §5.2 for the decision record |
| LLM access | OpenAI/SDK-compatible provider, plus Ollama fallback; provider-abstracted | affordable/free/self-hosted option |
| DB | Postgres 16 + pgvector | relational + embeddings in one place |
| Cache/queue | Redis | cache key source, job broker, rate-limit store |
| Jobs | worker polling + deferred jobs | alerts, price polling, async review analysis |
| Deploy | Vercel (web), Docker (api), Docker (worker) | serverless is wrong for long-running agent work |

## 4. Request lifecycle — a search run

1. `POST /api/v1/search` (JWT optional in v0, required for personalization).
2. API validates payload → enqueues a **search run** job.
3. `run_id` returned immediately. Client streams/status-polls via `GET /api/v1/agents/{run_id}`.
4. Worker executes the **agent DAG** (see AI_AGENTS.md) with timeouts, retries, and structured state persisted as `agent_runs` / `agent_events`.
5. Providers are queried in parallel; results normalized, deduplicated, matched, scored.
6. Results persist in `products`, `product_offers`, `prices`, then a response envelope is produced.
7. UI renders from the envelope; long tails (review analysis) can continue asynchronously and update the run.

`BUY/WAIT/AVOID` and Deal Score are **computed by rules over persisted signals**, with the LLM producing an explanation structured over those signals — never free-floating.

## 5. AI orchestration

### 5.1 Agent list (single DAG, no free loops)

Intent → Search → Match → Research → Price → Reviews → Seller → DealScore → Recommend.
Each agent: typed input state, typed output state, validation, timeout, max-iter, retry, fallback.

### 5.2 Why not the currently-trending "official" agent SDKs

The widely-promoted LangGraph Python package is tied to the LangChain ecosystem, which is heavy and — at the time of writing — has shaky compatibility with Python 3.14; we pin 3.11 and do not want to inherit that dependency graph. Parallel maturity concerns exist for the Vercel AI SDK v6 branching on the agent side. **This product needs a small, auditable state machine with typed state transitions and no uncontrolled agent loops**, implemented over plain async Python.

Decision: **Potpie/Nextchain** — a Node-graph state machine for FastAPI-native agents, selected
for a far smaller dependency footprint and an explicit, static graph you can read like a spec.
Our own typed state + providers sit on top; we can swap the graph engine without touching domains.

### 5.3 Specified reads may change before Phase 3

The agent engine is the highest-risk technical dependency in the plan. **Before Phase 3** the plan re-evaluates Potpie/Nextchain against current release status, Python 3.11 support, and maintenance health; if it is immature, the fallback is a hand-rolled, clearly-scoped DAG runner (~300 lines) that satisfies the same spec-proofs. No code is committed to an engine before that check, so the architecture survives either outcome.

## 6. Provider abstraction

```
SearchProvider        search(query) → RawOffer[]            (canonicalized downstream)
ProductProvider       product_by_url / product_by_identifier
AIProvider            generate_structured(prompt, schema) → validated model
ReviewProvider        fetch_reviews(product_id) → raw reviews
PriceProvider         price_series(product_id) → raw history
EmbeddingProvider     embed(texts) → vectors
```

- Registry pattern: `ProviderRegistry` + comma-separated `PRICEPILOT_SEARCH_PROVIDER`
  (`openfoodfacts,<next>`), allowing parallel fan-out across providers.
- Each adapter declares **availability** + **capability flags**; the UI renders
  unconfigured slots as "provider unavailable — configure X".
- Every adapter enforces its own timeout, rate limit, retry/backoff, and response
  validation.

### Canonical product pipeline (Phase 2)

Raw offers → **identifier extraction** (GTIN/EAN/UPC barcode from OFF `code`,
MPN when present) → **attribute normalization** (title, brand, model, storage,
quantity/pack-size, color) → **deterministic + confidence matching** → grouped
**canonical variant products** with merchant offers.

- Matching priority: exact GTIN → very high confidence; conflicting GTIN/brand/
  variant → strong reject; brand+model, normalized title, pack size → supporting
  signals; semantic similarity → supporting only, never sole basis for a merge.
- A canonical product is variant-level: "Sidi Ali 33 cl" and "Sidi Ali 2 L" are
  distinct products, never merged by similar titles.
- Determinism first: numeric identifiers and exact normalized signals decide;
  embeddings only generate candidates for the residual set.

### Implemented/planned adapters (Phase 2–4)

| Slot | Phase 2 | Later |
|---|---|---|
| Search/Product | OpenFoodFacts (free, real, foods) as the first live adapter | e.g., a user-supplied marketplace/storefront API |
| Reviews | (none — "unavailable, config required"); source text where permitted | marketplace review API per source |
| Price history | captured by the platform's own price polling over time | provider history API where available |
| AI | Config: `AI_PROVIDER` (openai-compatible / ollama); **no key in env ⇒ provider marked unavailable, graceful degrade** | |
| Embeddings | same AI provider route | |

OpenFoodFacts is the only demo-safe *live* public product source we can rely on without user credentials; everything else is behind clean, explicitly-unavailable interfaces until a real integration is configured. This satisfies the honesty rule while exercising the full data path.

## 7. Caching & performance

- Redis caches: normalized product pages, price snapshots (TTL'd), aggregations, rate-limit counters, session state, idempotency keys.
- Read-heavy models (prices, review summaries) are write-through from workers so web reads are O(1).
- Provider calls fan out in parallel (asyncio.gather) with per-provider deadlines.
- Deterministic filters → SQL indexes; embeddings only where similarity earns it (pgvector HNSW).

## 8. Security model

- Auth: Supabase Auth (email/password + OAuth), JWT to API; secure, `httpOnly` cookies on web.
- Authorization: Supabase RLS row-level; API checks org/user scope.
- SSRF: user-submitted URLs (e.g., "should I buy this?" links) resolved only through the provider stack with allowlisted domains, no redirect-following to private/cloud ranges, validated scheme/host, rate-limited.
- Prompt injection: treat URLs/page text as untrusted data, not instructions; LLM output parsed into schemas and validated before use.
- Rate limiting: Redis-backed, per user/IP per endpoint.
- Frontend never receives API keys; secrets live in backend env / secret manager.

## 9. API surface (v1)

`POST /search` · `GET /products` · `GET /products/{id}` · `GET /compare?ids=` · `POST /shopping/chat` · `GET /recommendations` · `GET /price-history/{id}` · `GET/PATCH /alerts` · `GET/POST/PATCH/DELETE /tracking` · `GET/PUT /preferences` · `GET /monitoring/status` · `GET /agents/{run_id}` (run status/stream). Consistent error envelope (§ section in API.md), pagination, Pydantic validation. Monitoring endpoints use `X-User-Id` until real JWT auth lands (Phase 1 decision).

## 10. Observability

- Structured JSON logs, always `request_id`; `user/session_id` where lawful/appropriate; never secrets.
- Metrics for provider latency/failures, search/DB latency, cache hits, queue depth.
- `agent_runs`/`agent_events` tables give an audit trail of every AI decision.

## 11. Security & performance risks (open items for Phase 1)

- Keep long AI/scrape work out of Vercel functions (enforced by build guards/README).
- Default-deny SSRF by construction; verify before enabling any URL-based feature.
- Python 3.11 pin to avoid binary-ecosystem breakage on 3.14.
- Redis/Postgres connection discipline in async loops (pool sizes, timeouts).
- Fixtures detectable end-to-end (flag on every row + UI badge) so demo data can't leak into "real" statements.