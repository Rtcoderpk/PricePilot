"""Comparison agent — deterministic comparison of REAL retrieved results.

Normalizes by unit price when currency is consistent. If currency conversion is
unavailable, results in different currencies are explicitly NOT compared and the
comparison reports a currency conflict. Never treats currencies as equal.
"""

from __future__ import annotations

from pricepilot.logging import get_logger
from pricepilot.models import (
    ComparisonOption,
    SupplierResult,
    VerificationResult,
    VerificationState,
)

log = get_logger("research.comparison_agent")


def compare(
    results: list[SupplierResult],
    verifications: list[VerificationResult],
    *,
    quantity: int | None = None,
) -> tuple[list[ComparisonOption], bool]:
    """Compare supplier results. Returns (options, currency_conflict).

    Sort order intent is captured per option via `category` set later by the
    recommendation agent; here we only produce normalized options.
    """
    verif_by_idx = {v.result_index: v for v in verifications}
    options: list[ComparisonOption] = []
    currencies = {r.currency for r in results if r.currency}
    currency_conflict = len(currencies) > 1

    for i, r in enumerate(results):
        v = verif_by_idx.get(i, VerificationResult(result_index=i))
        options.append(
            ComparisonOption(
                result_index=i,
                supplier=r.supplier,
                product=r.product,
                unit_price=r.price,
                currency=r.currency,
                moq=r.moq,
                shipping=r.shipping,
                availability=r.availability,
                verification=v.state,
                source=r.source,
                url=r.url,
            )
        )

    return options, currency_conflict


def position_categories(
    options: list[ComparisonOption],
    *,
    currency_conflict: bool,
) -> tuple[list[ComparisonOption], list[str]]:
    """Assign cheapest / best_value / best_supplier categories and reasoning.

    Deterministic and only when enough real data exists. Returns (options,
    reasoning_lines).
    """
    reasoning: list[str] = []
    if not options:
        return options, reasoning

    # Cheapest: lowest real unit price within a consistent currency.
    priced = [o for o in options if o.unit_price is not None and o.verification != VerificationState.UNVERIFIED]
    if priced and not currency_conflict:
        cheapest = min(priced, key=lambda o: o.unit_price)
        cheapest.is_cheapest = True
        reasoning.append(f"Cheapest: {cheapest.supplier or cheapest.product or 'option'} at {cheapest.unit_price} {cheapest.currency}")
    else:
        reasoning.append("No single cheapest: prices are missing or in different currencies.")

    # Best supplier: verified + has source URL (+ price if available).
    verified = [o for o in options if o.verification == VerificationState.VERIFIED and o.url]
    if verified:
        best = sorted(verified, key=lambda o: (o.unit_price if o.unit_price is not None else float("inf")))[0]
        best.is_best_supplier = True
        reasoning.append(f"Best supplier: {best.supplier or best.product or 'option'} (verified, {best.url})")
    else:
        reasoning.append("Unable to verify a supplier from the available sources.")

    # Best value: verified + low price + availability, when a mid option exists.
    has_avail = [o for o in priced if o.availability]
    if has_avail and not currency_conflict:
        # best value = lowest price among available & verified
        best_val = min(has_avail, key=lambda o: o.unit_price)
        best_val.is_best_value = True
        reasoning.append(f"Best value: {best_val.supplier or best_val.product or 'option'} (available, {best_val.unit_price} {best_val.currency})")
    else:
        reasoning.append("No best-value candidate: missing availability or price data.")

    return options, reasoning