# PricePilot — PRODUCT SPEC

**Version:** 0.1 (Phase 0 planning baseline)
**Status:** Planned — nothing described as "live" is implemented. See column "Phase" for when a feature is scheduled.
**Date:** 2026-09-08

---

## 1. Product vision

PricePilot is an **autonomous AI shopping intelligence platform**. A user describes what they want to buy in natural language and PricePilot researches products, compares offers across stores, analyzes prices and review text, evaluates sellers, calculates total cost, and returns an **explainable recommendation** (BUY / WAIT / AVOID) with a componentized Deal Score.

The experience is intended to sit between Google Shopping, ChatGPT/Perplexity answer engines, and a price tracker — but with explicit multi-agent orchestration underneath.

Example queries the product must support:

- "I need a good laptop for AI/ML under $1000."
- "Find me the best phone under Rs. 100,000."
- "Is this laptop worth buying?" (URL or pasted product)
- "Compare this product across stores."
- "Find me the cheapest genuine option."
- "Should I buy this now or wait?"
- "Find a product with good battery, camera and performance."

## 2. Non-negotiables (honesty rules)

These constraints override all feature ambition:

1. **No fake data.** No invented products, prices, reviews, sellers, or APIs.
2. **Real data only** from: licensed/legitimate APIs, official feeds, marketplace APIs the user supplies credentials for, or compliant web extraction that respects robots.txt, terms, rate limits, and law.
3. **Unavailable providers are marked unavailable** behind a clean provider interface — never simulated.
4. **Uncertainty is disclosed.** Uncertain product identification → "possible matches" with confidence. Price forecasts → range + confidence + methodology, never a fake guarantee. Missing specs → shown as missing, never invented.
5. **Sellers are never labeled fraudulent without reliable evidence.** Confidence wording only: High / Medium / Low / Limited data.

## 3. Personas

| Persona | Goals | Key features |
|---|---|---|
| Casual shopper | Buy the right thing cheaply, quickly | NL search, best-price, recommendations |
| Price-conscious tracker | Wait for the dip | Price history, alerts, BUY/WAIT/AVOID |
| Researcher/student (portfolio demo) | Deconstruct the platform | Agents, providers, observability, docs |
| Developer (self-hosts) | Add a store/LLM provider | Provider abstraction, env config |

## 4. Feature inventory

| Feature | Description | Phase |
|---|---|---|
| NL intent parsing | Budget, category, specs, currency/locale, hard vs soft constraints → structured intent | P3 |
| Product search | Parallel queries across configured providers, normalization, dedup | P2 ✅ |
| Product matching | Same product across stores (SKU/GTIN/UPC/EAN, model #, normalized attrs, embeddings) | P2 ✅ |
| Price intelligence | Current/lowest/average, trend, discount vs baseline; forecast only with explicit uncertainty | P3–P5 |
| Total-cost engine | Price + shipping + est. tax + fees − verified discount; estimated vs confirmed clearly separated | P3 |
| Review intelligence | Theme extraction (positive/negative, battery, fan, durability, delivery…), review summary; text mined only on permitted sources; no fabrication | P4 |
| Seller intelligence | Transparent confidence from rating/count/return/warranty/authenticity; never "fraud" without evidence | P3–P4 |
| Should I buy this? | BUY / WAIT / AVOID with bullet reasons from real signals | P4 |
| Deal Score | Explainable componentized score (price value, quality, reviews, seller, total cost, fit) | P3 |
| Personalized recs | Brand/budget/spec/coupon/condition preferences; importance weights | P4 |
| Price history & charts | 30d/90d/6m/1y — only data that exists | P5 |
| Price alerts | Target price, % drop, back-in-stock (where supported); worker-monitored | P5 |
| Image shopping | Upload → identification (uncertain ⇒ possible matches) → match → compare → recommend | P4 |
| Voice shopping | Web Speech API transcription (disablable), reuse NL pipeline | P4 |
| AI shopping chat | Multi-turn context, follow-ups, persistent session filters | P4 |
| Comparison | Side-by-side specs/price/cost/reviews/seller + "Best Overall / Value / Cheapest / Premium" | P4 |
| Dedup UI | One product, many offers/merchants (canonical cards w/ store comparison) | P2 ✅ |
| Search | NL, keyword, category, filters, sort, semantic (pgvector) | P2/P4 |
| RAG/vector | Only where semantic similarity earns it (match, similarity, review themes, preferences) | P4 |
| Dashboard / track / alerts / history / settings | Personalization surface | P5/P6 |

## 5. Page map

| Route | Purpose | Phase | Status |
|---|---|---|---|
| `/` | Landing: hero input → AI search | P6 | done |
| `/search` | Results from an intent run | P6 | done |
| `/product/[id]` | Detail + price history + analytics + track | P6 | done (history/analytics; full offers+reviews surface pending provider data) |
| `/compare` | Side-by-side price intelligence | P6 | done (real recorded observation analytics) |
| `/track` | Tracked products | P6 | done |
| `/alerts` | Price alerts | P6 | done |
| `/history` | Price history charts | P6 | done |
| `/shopping` | AI shopping chat | P6 | done |
| `/settings` | Preferences/profile | P6 | done |
| `/dashboard` | Personalized overview | P6 | done |

## 6. Product cards (search results) must show

Image, name, best price, price comparison, store(s), seller, rating + count, Deal Score (breakdown), price trend, AI recommendation badge, actions: Compare / View / Track / Ask AI.

## 7. Explicit non-goals (this release)

- Impulse "instant checkout" — out of scope; PricePilot recommends, it does not transact.
- Free 24/7 crawl of every retailer on earth — provider-set, rate-limited, term-compliant.
- Guaranteed future prices — forecasts show uncertainty or are omitted.
- Fake placeholder catalog to make the UI look populated — the catalog is whatever providers return, plus a clearly-labeled offline demo mode for UI development only.

## 8. Demo mode (kept honest)

The repository ships a **demo mode** for UI development without network/keys:

- It returns a static **fixture corpus** (products marked `data_source: fixture`, `is_fixture: true`).
- Fixture results are **clearly labeled "Demo data — not live prices"** in the UI whenever rendered.
- Fixture data is never served in a production build without an explicit `PRICEPILOT_ENABLE_FIXTURES=true` override.
- Fixtures are tiny and mechanical — they exist to make the UI testable, not to fake shopping results.

## 9. Acceptance criteria for a shipped feature

A feature is "done" only when: implemented, provider-marked (real or unavailable), tested, linted, typechecked, documented, and no regressions. This matches the Phase Execution Rule in the master spec (§41).