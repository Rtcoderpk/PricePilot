"""Recommendation agent — picks best/cheapest/best-value from comparison ONLY.

The recommendation is a pure selection over retrieved, compared options; an LLM
is never used to invent a candidate. `reasoning` explains the selection.
"""

from __future__ import annotations

from pricepilot.logging import get_logger
from pricepilot.models import ComparisonOption, Recommendation

log = get_logger("research.recommendation_agent")


def recommend(
    options: list[ComparisonOption],
    *,
    currency_conflict: bool,
    reasoning: list[str] | None = None,
) -> Recommendation:
    if not options:
        return Recommendation(reasoning=["No supplier options were retrieved."], confidence=0.0)

    reasons = list(reasoning or [])
    best_supplier = next((o for o in options if o.is_best_supplier), None)
    cheapest = next((o for o in options if o.is_cheapest), None)
    best_value = next((o for o in options if o.is_best_value), None)
    verified_count = sum(1 for o in options if o.verification == "verified")
    priced_count = sum(1 for o in options if o.unit_price is not None)

    # Confidence is derived purely from how much real data exists.
    base = 0.0
    if options:
        base += 0.3
    if priced_count:
        base += 0.3
    if verified_count:
        base += min(0.4, verified_count * 0.1)
    confidence = round(min(1.0, base), 2)

    return Recommendation(
        best_supplier=best_supplier,
        cheapest_option=cheapest,
        best_value=best_value,
        reasoning=reasons,
        confidence=confidence,
        currency_conflict=currency_conflict,
    )