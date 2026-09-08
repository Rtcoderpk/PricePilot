# PricePilot — API

Base: `http://localhost:8000` (dev) · OpenAPI schema at `/docs`.

## Service endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe (200 when process is up) |
| GET | `/readyz` | Readiness (DB required, Redis degradable) |
| POST | `/api/v1/search` | Run a shopping search |
| POST | `/api/v1/shopping/search` | Run the full AI shopping agent |
| POST | `/api/v1/shopping/chat` | Multi-turn shopping chat (session-persisted) |
| POST | `/api/v1/shopping/image` | Upload a product image → possible matches |
| GET | `/api/v1/monitoring/status` | Monitoring capability state (enabled/provider/count/message) |
| GET | `/api/v1/price-history/{product_id}` | Real recorded price observations + analytics |
| POST | `/api/v1/tracking` | Track a product (target price optional); 409-free duplicate → `already_tracked` |
| GET | `/api/v1/tracking` | List the caller's tracked products |
| GET | `/api/v1/tracking/{watchlist_id}` | One tracked product (404 if not the caller's) |
| PATCH | `/api/v1/tracking/{watchlist_id}` | Update target/preferences/pause (404 if not the caller's) |
| DELETE | `/api/v1/tracking/{watchlist_id}` | Remove tracking (204) |
| GET | `/api/v1/alerts?unread=` | Alert notifications (optionally unread only) |
| PATCH | `/api/v1/alerts/{notification_id}` | Mark a notification `read`/`dismissed` (owner only) |
| GET | `/api/v1/preferences` | The caller's shopping preferences (empty when unset) |
| PUT | `/api/v1/preferences` | Upsert the caller's shopping preferences |

## `POST /api/v1/search`

Searches configured providers and returns normalized products grouped into cards.

Request:
```json
{ "query": "nutella", "max_results": 20 }
```
- `query` (string, 1–500) required
- `max_results` (int, 1–100) optional, default 20

Response `200`:
```json
{
  "query": "sidi ali",
  "products": [
    {
      "canonical_product_id": "pp_gtin_...",
      "name": "Sidi Ali (33 cl)",
      "brand": "سيدي علي",
      "category": "Natural mineral waters",
      "image_url": "https://...",
      "variant": { "quantity": "330", "quantity_unit": "33 cl", "quantity_kind": "volume" },
      "match_confidence": 0.99,
      "match_method": "gtin",
      "offers": [
        {
          "provider": "openfoodfacts",
          "title": "Sidi Ali",
          "url": "https://...",
          "price_amount": null,
          "price_currency": "USD",
          "availability": null,
          "data_source": "openfoodfacts",
          "is_fixture": false,
          "identifiers": [ { "type": "gtin", "value": "6111035000430" } ],
          "raw": { "...": "..." }
        }
      ],
      "price_insight": { "current": null, "lowest_90d": null, "avg_90d": null,
                         "currency": "USD", "sample_count": 0 },
      "is_fixture": false
    }
  ],
  "providers": [ { "name": "openfoodfacts", "availability": "available", "reason": null } ],
  "total": 20,
  "generated_at": "2026-09-08T00:00:00Z",
  "notice": null
}
```

- Every `products[i]` is a **canonical product** (variant-level) carrying one or
  more merchant offers under `offers`. Duplicate listings that match (by GTIN or
  deterministic attribute matching) are grouped into one product — they never
  appear as separate rows.
- `variant` holds distinguishing attributes (storage_gb, quantity/unit, color) so
  "Sidi Ali 33 cl" and "Sidi Ali 2 L" stay distinct products.
- `match_confidence` + `match_method` explain how offers were grouped
  (`gtin` | `model` | `attributes` | `identifier` | `similarity`).
- `price_amount` is `null` when the provider has no real price — **never fabricated**.
- `notice` carries honest caveats (provider unavailable, no results, demo mode).

## Errors

All errors return a single envelope:
```json
{ "error": { "code": "provider_unavailable", "message": "...", "details": null } }
```

| Code | HTTP | Meaning |
|---|---|---|
| `validation_error` | 422 | Malformed request |
| `rate_limited` | 429 | Redis rate limit exceeded (30 req/min/IP default) |
| `provider_unavailable` | 503 | Provider slot not configured |
| `provider_error` | 502 | Upstream provider failed |
| `upstream_timeout` | 504 | Upstream timed out |
| `internal_error` | 500 | Internal failure (no stack traces exposed) |

Requests carry an `X-Request-Id` (echoed in responses) for log correlation.

---

## `POST /api/v1/shopping/search`

The AI shopping agent: parses intent, searches providers, canonicalizes products, analyzes real price/seller/review data, scores deals, and ranks recommendations.

Request:
```json
{ "query": "good 55 inch Samsung TV under 700", "use_llm": true }
```
- `query` (string, 1–500) required
- `use_llm` (bool, default true) — falls back to deterministic intent parser when AI key is missing

Response `200`:
```json
{
  "request_id": "req-…",
  "query": "good 55 inch Samsung TV under 700",
  "status": "completed",
  "intent": { "category": "TV", "budget_max": 700, "brands": ["samsung"], … },
  "products": [ { "canonical_product_id": "pp_…", "name": "…", "offers": [ … ], … } ],
  "recommendations": [
    { "product_id": "pp_…", "rank": 1, "matches_hard_constraints": true,
      "reasons": [ "within your budget (best 699.00)" ], "deal_score": 81, … }
  ],
  "price_analysis": { "pp_…": { "lowest_offer": 699, "price_position": "insufficient_history" } },
  "seller_analysis": { "pp_…": { "label": "verified_signal", "signals": ["available"] } },
  "deal_scores": { "pp_…": { "score": 81, "label": "Good Deal", "components": { "price_value": 60, … } } },
  "sibt": { "pp_…": { "verdict": "wait", "reasons": ["price 699 present but", "deal score 60/100 is weak"],
                     "confidence": 0.5, "generated_at": "…" } },
  "forecasts": { "pp_…": { "status": "insufficient_history", "samples": 0, "reason": "need at least 30 real price samples" } },
  "semantic": "keyword",
  "warnings": [ "No review provider configured" ],
  "confidence": 0.56,
  "answer": "Best match: Samsung 55\" QLED (best 699.00) (Deal Score 81/100)"
}
```

## `POST /api/v1/shopping/chat`

Multi-turn conversation. Request:
```json
{ "query": "only samsung", "session_id": "…" }
```
- `session_id` omitted on the first message → a new `shopping_sessions` row is
  created and returned.
- Deterministic refinements recognized: `only <brand>` (brand allow list),
  `no/not <brand>` (exclude), `cheaper`, `under <N>` (budget), `ignore
  refurbished`, `best rated`, `more` / `show more`. Anything else runs a fresh
  shopping search.
- Response includes `session_id`, `conversation` (message list), and
  `refinements` (what was understood) plus the normal agent envelope.

## `POST /api/v1/shopping/image`

Multipart upload (`file` + optional `max_matches`). Validates `image/jpeg|png|webp`
and ≤ 5 MB. Without a configured vision provider it returns HTTP 200 with:
```json
{ "status": "unavailable", "warnings": ["Vision provider is not configured …"], "products": [] }
```
With a provider it returns `possible matches` with confidence levels.

## Price monitoring (Phase 5)

Identity is deferred (Phase 1 decision): monitoring endpoints accept an
`X-User-Id` header in place of a JWT; a real auth layer plugs in later. The
contract today:

- `X-User-Id` **must be a valid UUID** (the schema keeps UUID FKs to
  `users.id`). A missing header → `401`; a present but malformed value → `400`,
  never a database 500.
- A **centralized identity resolver** (`pricepilot.services.identity`)
  validates the header and **idempotently creates the `users` row** for that
  UUID on first use, so tracking/alerts/preferences can reference it. Repeated
  requests are cheap (`ON CONFLICT (id) DO NOTHING`).
- Every tracking/alert/preference operation is scoped to that resolved UUID —
  records from other `X-User-Id`s are invisible (and 404 on direct access).
- When real Supabase authentication lands, the resolver is swapped for one that
  reads the JWT and returns the authenticated user UUID; routes and the service
  layer are unchanged. The frontend ships a fixed demo UUID
  (`11111111-1111-4111-8111-111111111111`) as the local demo identity until then.

### `GET /api/v1/monitoring/status`

```json
{ "enabled": true, "provider": "available", "interval_seconds": 3600,
  "tracked_products": 3, "message": null }
```
`provider` is `available` only when a real price source (OpenFoodFacts) is
configured — it will not claim availability without one.

### `POST /api/v1/tracking`

```json
{ "product_id": "pp_gtin_...", "target_price": 30.0, "target_currency": "EUR",
  "alert_preferences": { "price_drop": true, "new_low": true, "target_price": true } }
```
Returns `201` with `{ "status": "created", "id": "…" }` or `200` with
`{ "status": "already_tracked", "id": "…" }` when it already exists.

### `GET /api/v1/price-history/{product_id}`

```json
{ "product_id": "pp_…", "currency": "EUR",
  "analytics": { "status": "available", "current_price": 45.0, "previous_price": 50.0,
                 "percentage_change": -10.0, "lowest_observed": 45.0, "trend": "down",
                 "observation_count": 5 },
  "observations": [ { "amount": 45.0, "currency": "EUR", "observed_at": "…", "source": "openfoodfacts" } ] }
```
All observations are **real recorded polls**; `analytics.status` is
`insufficient_history` until ≥2 observations exist (never synthetic).

### `GET /api/v1/alerts?unread=true`

```json
[ { "id": "…", "title": "Price dropped", "body": "Price dropped from 50.00 to 45.00",
    "status": "unread", "kind": "percent_drop", "product_id": "pp_…",
    "target_amount": null, "percent_threshold": -10.0,
    "triggering_offer": { "event_type": "price_drop", "current_price": 45.0,
                           "previous_price": 50.0, "source": "openfoodfacts", "currency": "EUR" } } ]
```

### `GET/PUT /api/v1/preferences`

Partial upsert (missing fields are left unchanged). `max_budget: 0` clears the
budget (the same convention as `PATCH /tracking` target price).

```json
{ "preferred_brands": ["Acme"], "max_budget": 500,
  "preferred_stores": ["Store A"], "preferred_condition": ["new", "refurbished"],
  "price_vs_quality": 0.7, "currency_code": "USD", "shopping_locale": "en-US" }
```

## Architecture note

- Multi-agent runs and long scrape work execute in the **API/worker**, never in
  Vercel serverless functions.
- The search provider is cached in Redis for identical queries (TTL 300s),
  reducing provider load and rate-limit pressure.
- `PRICEPILOT_SEARCH_PROVIDER` may be a comma-separated list; providers are
  queried in parallel and results are canonicalized together (dedup across
  providers).
- Price history is captured by the platform's own worker polling (`prices` is
  append-only); the monitoring worker observes → dedupes → detects events →
  persists alerts → optional external delivery, with retry/backoff and a failure
  per offer never aborting a cycle.