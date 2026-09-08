"""Intent extraction: natural language → structured ShoppingIntent.

Tries the configured LLM for high-fidelity parsing; on AI unavailable/failure,
falls back to an honest deterministic keyword parser (no fabrication — it only
extracts recognizable tokens). Both paths validate against `ShoppingIntent`.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from pricepilot.agents.state import (
    Condition,
    RankingPreference,
    ShoppingIntent,
    Urgency,
)
from pricepilot.agents.structured import StructuredOutputError, generate_structured
from pricepilot.logging import get_logger

log = get_logger("agents.intent")


class _IntentLLM(BaseModel):
    category: str | None = None
    product_type: str | None = None
    brands: list[str] = []
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str | None = None
    country: str | None = None
    required_features: list[str] = []
    preferred_features: list[str] = []
    excluded_features: list[str] = []
    quantity: int | None = None
    condition: str | None = None
    use_case: str | None = None
    ranking_preference: str | None = None
    urgency: str | None = None
    explicit_preferences: list[str] = []
    uncertain_fields: list[str] = []


_CURRENCY_HINTS = {
    "$": "USD", "usd": "USD", "dollar": "USD",
    "€": "EUR", "eur": "EUR", "euro": "EUR",
    "£": "GBP", "gbp": "GBP", "pound": "GBP",
    "₹": "INR", "inr": "INR", "rupee": "INR", "rs.": "INR", "rs ": "INR",
}

_BRAND_HINTS = {
    "samsung", "apple", "iphone", "lg", "sony", "lenovo", "dell", "hp",
    "asus", "acer", "xiaomi", "oneplus", "google", "nokia", "motorola",
    "nike", "adidas", "ferrero", "nestlé", "nutella", "sidi", "perly",
}


async def extract_intent(query: str, *, use_llm: bool = True) -> ShoppingIntent:
    """Extract structured intent from a free-text query.

    Always returns a valid ShoppingIntent (never raises on AI failure). When the
    AI is unavailable it degrades to the deterministic parser and records a
    warning via `uncertain_fields`/empty fields — no invented values.
    """
    if use_llm:
        try:
            llm = await generate_structured(_INTENT_PROMPT.format(query=query), _IntentLLM)
            return _to_intent(llm, query)
        except StructuredOutputError:
            log.info("intent LLM unavailable; using deterministic parser")
        except Exception:
            log.exception("intent LLM unexpected failure; using deterministic parser")

    return _parse_deterministic(query)


# --- deterministic parser -------------------------------------------------- #

def _parse_deterministic(query: str) -> ShoppingIntent:
    intent = ShoppingIntent(raw_query=query)
    tokens = query.lower().split()

    # currency — detect both symbol-prefixed tokens ("$700") and word forms
    # ("dollars"), plus the presence of a symbol anywhere in the query.
    matched_currency = None
    lower_q = query.lower()
    if any(sym in query for sym in ("$", "usd")):
        matched_currency = "USD"
    elif any(sym in query for sym in ("€", "eur")):
        matched_currency = "EUR"
    elif any(sym in query for sym in ("£", "gbp")):
        matched_currency = "GBP"
    elif any(sym in query for sym in ("₹", "inr", "rupee", "rs.")):
        matched_currency = "INR"
    else:
        for word in ("dollar", "dollars"):
            if word in lower_q:
                matched_currency = "USD"
                break
        if matched_currency is None:
            for word in ("euro", "euros"):
                if word in lower_q:
                    matched_currency = "EUR"
                    break
        if matched_currency is None:
            for word in ("pound", "pounds"):
                if word in lower_q:
                    matched_currency = "GBP"
                    break
    if matched_currency:
        intent.currency = matched_currency

    # budget: "under 700", "below 1000", "$700", "< 1200", "between 500 and 800"
    m = re.search(r"(?:under|below|less than|max|up to|budget of)\s*[\$€£₹]?\s*([\d,]+[.]?\d*)", query.lower())
    if m:
        intent.budget_max = _num(m.group(1))
    m = re.search(r"(?:above|more than|min(?:imum)?|over)\s*[\$€£₹]?\s*([\d,]+[.]?\d*)", query.lower())
    if m:
        intent.budget_min = _num(m.group(1))
    m = re.search(r"between\s*([\d,]+)\s*and\s*([\d,]+)", query.lower())
    if m:
        intent.budget_min = _num(m.group(1))
        intent.budget_max = _num(m.group(2))

    # brands
    brands = [b for b in _BRAND_HINTS if any(tok in b for tok in tokens) or b in tokens]
    if brands:
        intent.brands = sorted(brands)

    # condition
    if any(w in tokens for w in ("refurbished",)):
        intent.condition = Condition.REFURBISHED
    elif any(w in tokens for w in ("used", "second-hand", "second hand")):
        intent.condition = Condition.USED
    elif any(w in tokens for w in ("new",)):
        intent.condition = Condition.NEW

    # urgency
    if any(w in tokens for w in ("soon", "quickly", "fast")):
        intent.urgency = Urgency.SOON
    elif any(w in tokens for w in ("right now", "now", "urgent")):
        intent.urgency = Urgency.NOW

    # ranking preference
    if any(w in tokens for w in ("cheapest", "lowest price")):
        intent.ranking_preference = RankingPreference.CHEAPEST
    elif any(w in tokens for w in ("best value", "value")):
        intent.ranking_preference = RankingPreference.BEST_VALUE
    elif any(w in tokens for w in ("highest rated", "best rated", "rating")):
        intent.ranking_preference = RankingPreference.HIGHEST_RATED
    elif any(w in tokens for w in ("best deal", "deal")):
        intent.ranking_preference = RankingPreference.BEST_DEAL

    # use_case: rough heuristic
    for use in ("gaming", "ai", "development", "school", "work", "editing", "photography"):
        if use in tokens:
            intent.use_case = use
            break

    # explicit preferences = known brand names + concrete attribute terms
    intent.explicit_preferences = list(intent.brands)

    return intent


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _to_intent(data: _IntentLLM, query: str) -> ShoppingIntent:
    """Map validated LLM output → ShoppingIntent, normalizing enums."""
    condition = data.condition.strip().lower() if data.condition else None
    try:
        cond = Condition(condition) if condition else Condition.UNKNOWN
    except ValueError:
        cond = Condition.UNKNOWN
    try:
        pref = RankingPreference(data.ranking_preference) if data.ranking_preference else RankingPreference.UNSPECIFIED
    except ValueError:
        pref = RankingPreference.UNSPECIFIED
    try:
        urg = Urgency(data.urgency) if data.urgency else Urgency.UNSPECIFIED
    except ValueError:
        urg = Urgency.UNSPECIFIED
    return ShoppingIntent(
        raw_query=query,
        category=data.category,
        product_type=data.product_type,
        brands=data.brands or [],
        budget_min=data.budget_min,
        budget_max=data.budget_max,
        currency=(data.currency or "").upper() or None,
        country=data.country,
        required_features=data.required_features or [],
        preferred_features=data.preferred_features or [],
        excluded_features=data.excluded_features or [],
        quantity=data.quantity,
        condition=cond,
        use_case=data.use_case,
        ranking_preference=pref,
        urgency=urg,
        explicit_preferences=data.explicit_preferences or [],
        uncertain_fields=data.uncertain_fields or [],
    )


_INTENT_PROMPT = """Extract a structured shopping intent from the user's query.

Rules:
- Only include information the user explicitly provided. Never invent.
- If something is ambiguous, put the field name in "uncertain_fields".
- budget_max is the upper budget cap the user stated; budget_min the lower.
- currency should be a 3-letter code if determinable (USD, EUR, GBP, INR).
- ranking_preference: one of "best_value", "cheapest", "highest_rated", "best_deal".
- urgency: one of "now", "soon", "later".
- condition: one of "new", "refurbished", "used", "any".

User query:
{query}

Return ONLY valid JSON matching this schema.
"""