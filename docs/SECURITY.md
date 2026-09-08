# PricePilot — Security

> This documents the security posture as of Phase 1. Anything marked *planned*
> is not yet enforced and is a known gap, not a claim.

## Current (Phase 1)

- **Secrets**: all config via environment variables / `.env` (git-ignored).
  `.env.example` documents every key; no secrets committed.
- **Frontend**: only `NEXT_PUBLIC_*` vars ship to the browser — never API keys.
- **Error handling**: single structured error envelope; internal stack traces are
  never exposed to clients. `request_id` correlation on every response.
- **Provider input**: every provider response is validated (status + content-type
  before `.json()`); malformed upstream data is rejected, not trusted.
- **Rate limiting**: Redis-backed sliding window per IP on `/search`
  (30 req/min default), with graceful fallback ("allow") if Redis is down so
  limiting never becomes a new outage.
- **CORS**: restricted to `CORS_ORIGIN` (default localhost:3000).
- **SSRF posture**: no user-supplied URLs are fetched yet (this is planned and
  default-deny by design until enforced).
- **CI**: dependency audits (`pip-audit`, `npm audit`), gitleaks secret scan.
- **Logging**: structured JSON, request-scoped; secrets are never logged.

## Planned (later phases)

| Control | Phase | Notes |
|---|---|---|
| Authentication & authorization | deferred | Supabase Auth; JWT to API |
| Row-level security (RLS) | migration-ready | policies gated on Supabase roles (migration 0007) |
| SSRF-protected URL fetch | Phase 4+ | SIBT URL feature: allowlist, no private ranges, no redirect-follow to RFC1918/cloud metadata |
| Prompt injection hardening | Phase 3 | treat fetched text as data, not instructions; structured output validation |
| File-upload validation | Phase 4 | image shopping: type/size checks |
| Auth-free admin bootstrap | later | documented non-goal for v0 |

## Running a security pass

```bash
# Python dep audit
pip install pip-audit && pip-audit -r services/api/pyproject.toml
# npm dep audit
cd apps/web && npm audit --audit-level=high
# Secret scan
# gitleaks (or CI)
```

## Reporting

Open an issue; never post secrets or live credentials. Prefer describing a
suspected vulnerability with reproduction steps.