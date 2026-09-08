# PricePilot — AI Agents

**Version 0.3 (Phase 3)**. The full implementation lives in
`services/api/pricepilot/agents/`. This doc reflects what is actually built —
nothing planned-but-fiction.

## 1. Design constraints (all enforced)

- **Agentic, but a single typed graph.** No uncontrolled loops; every node has a
  timeout, bounded retries, and validation. Nodes run concurrently where safe.
- **LLM output is never trusted raw.** Structured output is parsed, validated
  against Pydantic, retried-with-correction (bounded), then a fallback provider;
  if still invalid the node records a controlled error and the graph continues on
  deterministic branches.
- **Numbers come from data, not the model.** Price position, review themes, seller
  confidence, and Deal Score are derived from real persisted/provider data by
  deterministic rules. The LLM is only used for **intent parsing** (and optional
  explanation composition), both validated and bounded.
- **External text is data, not instructions.** Product titles, descriptions,
  reviews, and seller text are treated as untrusted content. Intent parsing gets
  only the user's query. Prompt-injection tests prove this.
- **Uncertainty is surfaced.** Missing data stays `null` / `unknown` /
  `insufficient_history` / `review_data_unavailable` — never filled by model
  knowledge.

## 2. Typed agent state

All agent nodes read/write a single **`AgentState`** (Pydantic) →
`agents/state.py`. Key fields:

```
request_id, user_id, original_query
intent              ShoppingIntent (structured; see below)
search_queries      list[str]
candidate_offers    list[RawOffer]
canonical_products  list[CanonicalProduct]
research_evidence   dict[product_id, ResearchEvidence]
price_analysis      dict[product_id, PriceAnalysis]
review_analysis     dict[product_id, ReviewAnalysis]
seller_analysis     dict[product_id, SellerAnalysis]
deal_scores         dict[product_id, DealScore]
recommendations     list[Recommendation]
warnings            list[str]
provider_errors     list[str]
confidence          float
final_answer        str | None
```

The state is immutable-ish (builder returns a new state), persisted as JSON to
`agent_runs.final_state` and per-event to `agent_events.output_state`.

### ShoppingIntent

```
category, product_type, brands[], budget_min, budget_max, currency, country,
required_features[], preferred_features[], excluded_features[], quantity,
condition, use_case, ranking_preference, urgency, explicit_preferences
```

Every field nullable. Never invented: an unmentioned brand is `None`, not
"unknown". `raw_uncertain_markers` records ambiguous values the intent parser
flagged so downstream agents don't assume them.

## 3. Agents

Each node is a small function over `AgentState` → `AgentState`, named:
`intent`, `search`, `matching`, `research`, `price`, `reviews`, `seller`,
`deal_score`, `recommendation`.

- **intent** — LLM-assisted structured parsing of the user query into
  `ShoppingIntent` with strict prompt-injection separation. Bounded retries;
  on provider failure falls back to a deterministic keyword parser (no model).
- **search** — derives 1–2 queries from intent (brand/category/budget keywords),
  runs configured SearchProviders **concurrently** with per-provider timeouts,
  collects `RawOffer`s; gracefully degrades when a provider fails.
- **matching** — calls the Phase 2 `services.canonical.canonicalize` to dedupe
  offers into canonical products. **Reuses the phase-2 engine**; variant
  conflicts and low confidence keep products separate.
- **research** — gathers real available evidence per product (specs/attributes,
  brand, quantity, offers, shipping, source) with `source` + `timestamp`; missing
  fields stay null.
- **price** — per canonical product computes lowest/highest/avg current offer,
  offer count, currency; `price_position` = below/around/above recent average
  **only when history exists**, else `insufficient_history`.
- **reviews** — from real reviews only (currently none configured in cell data)
  → returns `review_data_unavailable` honestly. Structure ready for a review
  provider.
- **seller** — from real seller/merchant signals present in offers (provider,
  availability, data_source) → `seller_analysis` with `label` in
  {`verified_signal`, `limited_information`, `insufficient_data`} + reasons.
- **deal_score** — deterministic, explainable 0–100 from real signals:
  price competitiveness, offer count, availability, seller signal, review signal
  (warned), missing-data warnings. Label ∈ {Excellent, Good, Fair, Weak,
  Insufficient Data}.
- **recommendation** — ranks products by intent (hard constraints enforced first,
  never silently bypassed), returns ordered recommendations each with
  `reasons[]`. If nothing satisfies hard constraints, explains and offers closest
  alternatives only where appropriate.

## 4. Node graph (directed acyclic)

```
intent ──▶ search ──▶ matching ──▶ research
                                     │
                  ┌──────────────────┼───────────────────┐
                  ▼                  ▼                   ▼
               price             reviews              seller
                  │                  │                   │
                  └──────────────────┼───────────────────┘
                                     ▼
                                 deal_score
                                     │
                                     ▼
                               recommendation
```

- `price`, `reviews`, `seller` run **concurrently** after `research`
  (`asyncio.gather`), bounded by node timeouts.
- Partial success: if `reviews` fails/empty, price+seller+deal_score complete
  (review signal reports `unavailable`).
- Bounded: each node has `max_retries` (default 0 for deterministic,
  2 for LLM calls) and a timeout; the orchestrator tracks per-run attempts and
  aborts on a global guard (no infinite loops).

## 5. AI provider behavior

`providers/ai/`:
- **contract**: `AIProvider.generate_structured(prompt, schema) -> BaseModel`,
  plus `available()`.
- **OpenAI-compatible** (`openai-compatible`): uses `OPENAI_API_KEY`/`AI_API_KEY`
  + `AI_MODEL` + `AI_BASE_URL`; `response_format=json_object` where supported.
- **Ollama** (`ollama`): local HTTP to `OLLAMA_BASE_URL` with `format=json`.
- **Noop**: honest unavailable — `available()=False`, raises controlled error.
- Registry resolves `AI_PROVIDER`; `AI_API_KEY` absent → Noop; nothing fakes an
  LLM.
- Structured-output pipeline (`agents/structured.py`): request → parse → validate
  (Pydantic) → on invalid, bounded corrected retry → fallback provider → final
  controlled `StructuredOutputError`. Never `json.loads` unchecked; never exposes
  raw model text or secrets.

## 6. Persistence

- `agent_runs`: one per shopping request (status `running` → `completed`/`failed`,
  `graph_name="shopping_intelligence"`, `final_state` JSON).
- `agent_events`: one per node transition (`agent`, `status`, `sequence`,
  `input_state`/`output_state` JSON, `latency_ms`). Writes are best-effort; a DB
  failure must not crash the request.

## 7. API

- `POST /api/v1/shopping/search` — body `{query, max_products?}`; returns the
  full structured answer envelope (see API.md). Same error envelope; Redis rate
  limit applied (same 30/min/IP budget as `/search`).
- `POST /api/v1/shopping/chat` — reserved for multi-turn (Phase 4); returns
  controlled "not implemented" today.

## 8. Security

- No secrets in state/events. `agent_events` stores **news that doesn't include
  the model prompt**; only inputs/outputs of nodes.
- External content (titles, descriptions, reviews, seller text) is isolated from
  any instruction context — intent and explanation prompts include only the user
  query and typed facts.
- Tests: prompt-injection via product title, review, and seller text must not
  change intent or recommendation output.

## 9. Known limitations (noted honestly for Phase 4)

- No real review data source is configured, so `reviews` returns
  `review_data_unavailable` by default. The node and schema are production-ready.
- Intent parsing needs an LLM key to reach full fidelity; without one it uses the
  deterministic parser (still typed and valid, lower recall). This is surfaced in
  `warnings`/`provider_errors`.
- `shopping/chat` multi-turn and image/voice shopping are intentionally Phase 4.

## 10. Phase 5: monitoring data feeding the price agent

The `price` agent's `price_position`/`insufficient_history` is fed by real
observations the Phase 5 worker collects (see `services/worker/main.py`):

- Worker polls tracked offers over time → `prices` (append-only, deduped within
  `MONITOR_OBSERVATION_WINDOW_SECONDS`).
- `price_series(product_id)` today reads the platform's own `prices` history —
  no external history provider is used or fabricated.
- Deterministic event detection (`new_low`, `target_price_reached`, `price_drop`,
  `availability_change`/back-in-stock) turns observations into alert/notification
  rows. Alerts are deduped by a unique `event_key`; observations are never
  synthesized — an absent price yields no event/row.
- The API exposes history/analytics (`GET /price-history/{id}`), tracking
  (`/tracking`), alerts (`/alerts`), preferences (`/preferences`), and monitoring
  status (`/monitoring/status`) — all `X-User-Id`-scoped until real JWT auth.
  The header must be a valid UUID; a centralized identity resolver idempotently
  creates the `users` row on first use (see `docs/API.md`).