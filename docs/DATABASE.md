# PricePilot — DATABASE

**Version:** 0.1 (Phase 0 planning baseline) · **Date:** 2026-09-08 · Target: PostgreSQL 16 + pgvector 0.7 (Supabase-compatible)

## 1. Principles

- Normalized relational core; **no redundant/trendy tables**.
- Prices/offers are append-only history; current values are denormalized caches for O(1) reads.
- Every row carries `created_at`/`updated_at`; concurrent-change-safe `updated_at`.
- `currency_code` always explicit (mission-critical for INR/USD etc.). **Never trust implicit.**

## 2. entities & responsibilities

```
users                Profiles of users
profiles             user metadata (public display info)
user_preferences     reusable shopping prefs (brands, budget, stores, condition, weights)
products             canonical deduped product — variant-level, one per matched identity+variant (variant_key + normalized_attrs since 0008)
product_identifiers  GTIN/UPC/EAN, model, MPN → product
product_offers       offer per merchant (price, shipping, tax, url)
prices               append-only point-in-time series (worker/ingest writes)
reviews              raw review statements (from permitted sources)
review_summaries     derived theme aggregation; container row, chunks in a table
product_embeddings   pgvector blob for canonical products
search_sessions      user intent runs; AI features moved here to avoid SKU churn
agent_runs           orchestration run (intent, status)
agent_events         per-agent step (type, state snapshot, validation result)
shopping_sessions    multi-turn chat context (filters, history, prefs snapshot)
watchlists           user tracks a product
price_alerts         conditions (target price | % drop | back-in-stock)
notifications        delivery history for alerts
snapshot_alerts      back-in-stock now handled through price_alerts (bonus... see note)
```

**Note:** A dedicated `price_history`/`comparisons` table was considered and dropped: point-in-time data is exactly `prices`; comparisons are derivable projections over `product_offers` + `agent_runs`, not an entity.

## 3. schema sketch (tables & key constraints)

> Column-list is a planning sketch; implemented in Alembic migrations under `services/db/alembic/versions`.

### identity & auth
- `users(id uuid PK, email citext unique not null, created_at, updated_at)`
- `profiles(id uuid PK → users, display_name text, avatar_url text, created_at, updated_at)`
- `user_preferences(id uuid PK, user_id → users ON DELETE CASCADE, preferred_brands text[], max_budget numeric(14,2), min_specs jsonb, preferred_stores text[], preferred_condition text[] CHECK (condition in ('new','refurbished','any')), price_vs_quality numeric(3,2) CHECK (0<=price_vs_quality<=1), currency_code char(3) default 'USD', shopping_locale text, created_at, updated_at, UNIQUE(user_id))`

### catalog
- `products(id uuid PK, canonical_name text not null, description text, brand text, category text, condition text, meta jsonb, variant_key text, normalized_attrs jsonb [added 0008], is_fixture boolean not null default false, created_at, updated_at)`
- `product_identifiers(id uuid PK, product_id → products ON DELETE CASCADE, id_type text CHECK in {'sku','gtin','upc','ean','mpn','model_number'}, id_value text not null, source text, UNIQUE(id_type, id_value))`

### offers & price series
- `merchants(id uuid PK, name text not null, domain text unique, is_authoritative boolean default false, created_at, updated_at)`
- `sellers(id uuid PK, merchant_id → merchants ON DELETE CASCADE, name text not null, seller_ref text, rating numeric(3,2) CHECK 0..5, review_count int CHECK >=0, return_policy jsonb, warranty jsonb, authenticity_flags jsonb, confidence text CHECK in {'high','medium','low','limited'}, data_source text, is_fixture boolean default false, created_at, updated_at, UNIQUE(merchant_id, seller_ref))`
- `product_offers(id uuid PK, product_id → products ON DELETE CASCADE, seller_id → sellers ON DELETE CASCADE, url text, available boolean default false, price_amount numeric(14,2) not null, price_currency char(3) not null, shipping_amount numeric(14,2), shipping_currency char(3), tax_estimate numeric(14,2), fees numeric(14,2), coupon_discount numeric(14,2), coupon_code text, condition text, data_source text, is_fixture boolean default false, first_seen_at timestamptz, last_seen_at timestamptz, created_at, updated_at)`
- `prices(id uuid PK, offer_id → product_offers ON DELETE CASCADE, product_id → products ON DELETE CASCADE (denormalized for time-series querying), amount numeric(14,2) not null, currency char(3) not null, recorded_at timestamptz not null default now(), source text)`
- `product_embeddings(product_id uuid PK → products ON DELETE CASCADE, embedding vector(1536) not null, model text not null, created_at)`
  - remark: model-dimension pinned at 1536 for OpenAI-compatible; if a model with a different dim is configured the index is rebuilt under its own `model` key — embedding column is deliberately per-model to avoid mixed-dim rows.

### reviews
- `reviews(id uuid PK, product_id → products ON DELETE CASCADE, source text, external_review_id text, rating numeric(3,2) CHECK 0..5, title text, body text, author text, review_date timestamptz, metadata jsonb, raw_fetched_at timestamptz, created_at, updated_at, UNIQUE(source, external_review_id))`
- `review_summaries(id uuid PK, product_id → products ON DELETE CASCADE, positives text[], negatives text[], common_complaints jsonb, suspicious_patterns jsonb, generated_at timestamptz, source_data jsonb, created_at, updated_at, UNIQUE(product_id))`

### agent orchestration
- `search_sessions(id uuid PK, user_id → users ON DELETE SET NULL, raw_query text not null, intent jsonb, currency_code char(3), locale text, status text, run_id → agent_runs, result_summary jsonb, created_at, updated_at)`
- `agent_runs(id uuid PK, session_id → search_sessions ON DELETE CASCADE, graph_name text, status text, error_code text, started_at, finished_at, final_state jsonb, created_at)`
- `agent_events(id uuid PK, run_id → agent_runs ON DELETE CASCADE, sequence int, agent text, status text, input_state jsonb, output_state jsonb, validation jsonb, latency_ms int, created_at)`

### tracking / alerts / shopping
- `watchlists(id uuid PK, user_id → users, product_id → products, note text, created_at, UNIQUE(user_id, product_id))`
- `price_alerts(id uuid PK, user_id → users, product_id → products, kind text CHECK in {'target_price','percent_drop','back_in_stock'}, target_amount numeric(14,2), target_currency char(3), percent_threshold numeric, triggering_offer jsonb, status text default 'active' CHECK in {'active','triggered','paused','cancelled'}, created_at, updated_at, updated_at_triggered_at)`
- `notifications(id uuid PK, user_id → users, alert_id → price_alerts ON DELETE CASCADE, channel text, title text, body text, sent_at, delivered jsonb, created_at)`
- `shopping_sessions(id uuid PK, user_id → users, run_id → agent_runs, intent_history jsonb, applied_filters jsonb not null default '{}'::jsonb, messages jsonb not null default '[]'::jsonb, prefs_snapshot jsonb, status text default 'active' CHECK in {'active','closed'}, created_at, updated_at)`

## 4. indexes

| Table | Index | Purpose |
|---|---|---|
| products | `(canonical_name)` (lower trgm in Phase 4 Semantic) | name search / dedup kicks |
| product_identifiers | `(id_type, id_value)` | resol=new lookups (already unique) |
| product_offers | `(product_id, available)`, `(seller_id)`, `(price_amount)` | best-price, offer listing |
| prices | BRIN or `(product_id, recorded_at DESC)` | time-series reads |
| reviews | `(product_id, review_date DESC)` | per-product review feed |
| price_alerts | `(status, kind)`, `(product_id)` | worker sweep |
| notifications | `(user_id, sent_at DESC)` | user inbox |
| agent_runs | `(session_id)`, `(user_id, created_at DESC)` | run history |
| agent_events | `(run_id, sequence)` | replay/debug |
| product_embeddings | ivfflat/HNSW on `embedding` | similarity search |

`product_offers` gets a **partial unique index** to prevent two live offers from the same seller/product shoving duplicates into best-price logic (unless `available=false` history is intentionally read — then exclude it).

## 5. RLS / auth notes (Supabase)

- `users`, `profiles`: row visible to self (+ service-role for workers).
- `watchlists`, `price_alerts`, `notifications`, `shopping_sessions`, `search_sessions`, `user_preferences`: owner-only.
- Catalog (`products`, `offers`, `prices`, `reviews`, `sellers`, embeddings): public read, write via service role only.
- Workers use the service role; the API authenticates users' JWTs and asserts ownership.

## 6. migrations

- `services/db/alembic/versions/*.py` in numbered order; applied via `alembic upgrade head` (Alembic tracks `alembic_version`).
- Phase 1 ships: `001_users_profiles`, `002_catalog`, `003_offers_prices`, `004_reviews`, `005_agents`, `006_tracking_alerts`, `007_pgvector`.
- Roll strategy: no destructive drop in `up`; `down` provided. Supabase `db push` compatible.

## 7. seeds & fixtures

- Seed data: only admin/system defaults via migrations (none shipped yet in Phase 1).
- **Fixtures** are *not* a migration; they are a dev-only, flagged corpus (`is_fixture=true`) so the UI can be built before real providers are configured. Env-gated (`PRICEPILOT_ENABLE_FIXTURES`), never default in production.

## 8. retention / lifecycle

- `prices`: keep full history for tracked products; cap ingest frequency via worker throttle (default ≤ 1 sample/hour per offer, configurable).
- `reviews`, `agent_events`: retained for audit; `agent_events` purged after e.g. 90d via a worker sweep if size becomes a concern (configurable).
- `product_embeddings`: rebuilt on re-index; old model versions removable.

## 9. open questions (resolve in Phase 1 before writing migrations)

1. Exact precision/scale for money columns — decided now: `numeric(14,2)` with currency column (no float money).
2. Whether to add `product_aliases` for raw provider titles before dedup (leaning: yes, in a `providers_raw` staging table, not shipped in v1).
3. RLS deployment model: Supabase console vs SQL in repo. Default: SQL-in-repo so dev mirrors prod exactly.
4. Backfill strategy for `prices` from provider histories — Phase 2+ decision.
5. `updated_at` on `prices` — intentionally omitted (append-only); only `recorded_at`.