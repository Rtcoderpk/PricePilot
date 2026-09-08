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
  "query": "nutella",
  "products": [
    {
      "canonical_product_id": "3017620422003",
      "name": "Nutella",
      "brand": "Ferrero",
      "category": "Spreads",
      "image_url": "https://...",
      "offers": [
        {
          "provider": "openfoodfacts",
          "title": "Nutella",
          "url": "https://...",
          "price_amount": 4.5,
          "price_currency": "EUR",
          "availability": null,
          "data_source": "openfoodfacts",
          "is_fixture": false,
          "raw": { "code": "3017620422003", "brands": "...", "categories": "..." }
        }
      ],
      "price_insight": { "current": 4.5, "lowest_90d": null, "avg_90d": null,
                         "currency": "EUR", "sample_count": 1 },
      "is_fixture": false
    }
  ],
  "providers": [ { "name": "search", "availability": "available", "reason": null } ],
  "total": 1,
  "generated_at": "2026-09-08T00:00:00Z",
  "notice": null
}
```

- `price_amount` is `null` when the provider has no price — **never fabricated**.
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