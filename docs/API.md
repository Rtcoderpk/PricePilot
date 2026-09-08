# PricePilot — API

Base: `http://localhost:8000` (dev) · OpenAPI schema at `/docs`.

## Service endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness probe (200 when process is up) |
| GET | `/readyz` | Readiness (DB required, Redis degradable) |
| POST | `/api/v1/search` | Run a shopping search |

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

## Architecture note

- Multi-agent runs and long scrape work execute in the **API/worker**, never in
  Vercel serverless functions.
- The search provider is cached in Redis for identical queries (TTL 300s),
  reducing provider load and rate-limit pressure.
- `PRICEPILOT_SEARCH_PROVIDER` may be a comma-separated list; providers are
  queried in parallel and results are canonicalized together (dedup across
  providers).