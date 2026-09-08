# PricePilot — Contributing

## Principles

- **No fake data.** No invented products, prices, reviews, sellers, or APIs.
- Unavailable providers are reported as unavailable, never simulated.
- Fix root causes, not symptoms. Don't suppress type/lint errors to make builds pass.
- Keep frontend/backend/AI separate: UI never embeds provider or agent logic.

## Setup

```bash
git clone <repo>
docker compose up --build          # db, redis, api, worker (auto-migrates)
cd apps/web && npm install && npm run dev
```

## Backend (services/api)

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
ruff check pricepilot tests                      # lint
pytest                                           # tests (needs docker DB+Redis)
```

Migrations: `cd services/db && alembic upgrade head`.

## Web (apps/web)

```bash
npm run lint && npm run typecheck && npm run test && npm run build
```

## CI

`.github/workflows/ci.yml` runs backend (lint/migrate/test), web
(lint/typecheck/test/build), security (pip/npm audit + secret scan), and Docker
image builds. **No deployment when critical checks fail.**

## Definition of done

A feature is done only when it is implemented, provider-marked (real or
unavailable), tested, linted, typechecked, documented, and shows no regressions.
Docs must reflect reality — never document a feature that does not exist.

## Phases

Follow the phase plan in `docs/`. Stop for approval between phases; never skip
verification (lint → typecheck → tests → build).