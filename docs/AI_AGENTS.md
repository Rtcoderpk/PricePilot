# PricePilot — AI AGENTS

**Version:** 0.1 (Phase 0 planning baseline) · **Date:** 2026-09-08

## 1. Design constraints

- **Agentic, but not "free agent."** One explicit DAG. No uncontrolled loops. No "keep going until the model says done."
- Every agent: typed input state → typed output state → validation → timeout → max-iterations → retry → fallback → structured logging to `agent_events`.
- **LLM output is never trusted raw.** It is parsed into a Pydantic schema, validated, and on invalid output retried-with-correction (bounded), else fallback.
- **Numbers come from data, not the model.** Deal Score and BUY/WAIT/AVOID are computed by rules over persisted `product_offers` / `prices` / `reviews` / `sellers` signals. The LLM produces explanations *over those computed values*, never the values themselves.
- **Uncertainty is surfaced.** Identifications/matches/forecasts carry confidence; missing data is "unknown," never invented.

## 2. Graph

```
                        ┌─────────────┐
    user request ──────▶│ intent      │  structured Requirements
                        └─────────────┘
                              │
                        ┌─────▼──────┐
                        │ search     │  providers fan-out, normalize
                        └─────┬──────┘
                              │ candidates
                        ┌─────▼──────┐
                        │ match      │  dedup canonical products + offers
                        └─────┬──────┘
                              │ canonical products
                        ┌─────▼──────┐
                        │ research   │  specs, features, gaps (no invention)
                        └─────┬──────┘
                              │
              ┌───────┬───────┼────────┬──────────┐
              ▼       ▼       ▼        ▼
           price    review  seller   deal-score
           intel    intel   intel
              │       │       │        │
              └───────┴───────┴────────┘
                              │ signals
                        ┌─────▼──────┐
                        │ recommend  │  Deal Score + BUY/WAIT/AVOID + narratives
                        └─────┬──────┘
                              │
                        final structured response
```

Branches (`price/review/seller`) run in parallel. `deal-score` consumes their outputs. `recommend` composes the final explanation.

## 3. Agent roles and state contracts

Each agent emits a typed Pydantic state. (Full schemas live in `services/ai/agents/schemas.py` in Phase 3; the contract below is authoritative-by-intent.)

### 3.1 Intent Agent
- Input: free-text query + optional URL/image meta + session prefs snapshot.
- Output: `Requirements{ category, currency, budget_min, budget_max, required_specs, preferences[], hard_constraints[], soft_preferences[], locale, condition, brands[] }`.
- Rules: unknown fields → `null` (never guessed); currency inferred only from explicit signals (symbol/country), never silently defaulted; recognized "gaming laptop under $1200" → category `laptop`, max_budget.

### 3.2 Search Agent
- Input: `Requirements`.
- Output: `SearchCandidates{ raw_offers[] }`, each raw offer = provider, url, title, raw_price, availability.
- Rules: providers run in parallel, each with deadline; adapter validates per-provider schema; unconfigured providers skipped and recorded.

### 3.3 Product Matching Agent
- Input: raw offers.
- Output: `MatchedProducts{ products[], offers[] }` mapping offers → canonical product.
- Rules: deterministic first (GTIN/UPC/EAN/model/MPN), then normalized-title + attributes, then semantic embeddings only as tiebreak; each match carries `confidence` and `method`; low-confidence → separate candidate row, never force-merged.

### 3.4 Research Agent
- Input: canonical products.
- Output: `Research{ specs[] }` per product with per-spec `source`, `confidence`; gaps recorded as `missing: true`.
- Rules: never invent spec values; if a provider returns specs, embed the source; otherwise blank.

### 3.5 Price Intelligence Agent
- Input: canonical products + `prices` series.
- Output: `PriceInsight{ current, lowest_90d, avg_90d, trend (up|down|flat), delta_vs_avg, discount_verified }`.
- Rules: computed from real `prices` rows only; `current` = latest live offer; no forecast in v1 unless explicitly implemented with range+confidence+methodology (see §6).

### 3.6 Review Intelligence Agent
- Input: reviews for product (permitted sources only).
- Output: `ReviewSummary{ positives[], negatives[], common_complaints[], suspicious_patterns[], stars, review_count, source_refs[] }`.
- Rules: no fabricated reviews; themes extracted from actual text; low volume → "limited data" label; source refs retained where possible.

### 3.7 Seller Intelligence Agent
- Input: sellers/offers for product.
- Output: `SellerAssessment{ seller_id, confidence (high|medium|low|limited), signals[] , flag }`.
- Rules: confidence derives from rating, count, marketplace status, return/warranty data; **never** "fraudulent" label without reliable evidence.

### 3.8 Deal Scoring Agent
- Input: PriceInsight, ReviewSummary, SellerAssessment, specs, total-cost, user preferences.
- Output: `DealScore{ overall 0-100, components{ price_value, product_quality, reviews, seller_reliability, total_cost, fit }, rationale[] }`.
- Rules: weight matrix from preferences (price_vs_quality); every component traceable to a signal with a human-readable reason; no magic numbers.

### 3.9 Recommendation Agent
- Input: DealScore + all above.
- Output: `Recommendation{ verdict (BUY|WAIT|AVOID), reasons[], best_alternative, explainable_notes[] }` (+ optional top-3 comparison).

## 4. Reliability controls

- Global executor: per-node `timeout_s`, `max_retries` (exponential backoff), circuit-break by provider, structured error taxonomy (`intent`, `search`, ... error codes).
- Malformed AI output → retry-with-correction (bounded, 2), else fallback (deterministic rule or explicit "unavailable").
- Concurrency: parallel branches capped; provider fan-out bounded by adapter limits.
- Logging: every node records `{run_id, node, status, latency_ms, input_state_hash, validation}`; cost metrics tracked per node.

## 5. Provider strategy (AI)

- Interface: `AIProvider.generate_structured(prompt, output_schema) -> ValidatedModel`.
- Config: `AI_PROVIDER` (`openai-compatible` default to `gpt-*`/`o1-*`; `ollama` for local/self-hosted), `AI_MODEL`, `AI_TEMPERATURE`, `AI_MAX_TOKENS`.
- **No key in env → provider marked unavailable**; app, worker, and chat degrade gracefully with an honest "AI provider not configured" instead of pretending.
- Provider failures → retry/backoff → fallback path → user-visible, non-exposure message.
- Reduce cost: preferences/brand constraints hit deterministic SQL before any LLM; semantic search only where it earns its inference spend.

## 6. Forecasting (only if/when implemented)

If a price-forecast feature ships, it will:
- Show range + confidence interval + methodology ("ARIMA over 90d of real samples" or similar), clearly communicate it is a model, not a guarantee.
- Never present a point-prediction as fact; include uncertainty; no forecasting over <N samples (configurable, default ≥30) — else "insufficient history."

## 7. Explanation & auditability

- Every Deal Score and SIBT verdict must be reproducible from `agent_runs` + `agent_events` (the consumer can replay a previous run).
- Explanations cite the actual sources: "current price $899 is ~10% below 90d avg $999 (data: prices table, 90d)".