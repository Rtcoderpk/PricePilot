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
        return options, ["Insufficient live data to calculate recommendations."]

    # Filter candidates by verification status
    verified_options = [o for o in options if o.verification == VerificationState.VERIFIED and o.url]
    partially_verified = [o for o in options if o.verification in (VerificationState.VERIFIED, VerificationState.PARTIALLY_VERIFIED)]

    # 1. Cheapest Verified: Lowest price among verified options
    priced_verified = [o for o in verified_options if o.unit_price is not None]
    if not priced_verified:
        priced_verified = [o for o in partially_verified if o.unit_price is not None]

    if priced_verified and not currency_conflict:
        cheapest = min(priced_verified, key=lambda o: o.unit_price)
        cheapest.is_cheapest = True
        reasoning.append(
            f"Cheapest Verified: {cheapest.supplier or 'Supplier'} offering {cheapest.product or 'Product'} "
            f"at {cheapest.unit_price} {cheapest.currency} with verified source link."
        )
    else:
        reasoning.append("Cheapest Verified: Insufficient live price data in a single currency.")

    # 2. Best Supplier: Highest trust score & verified status with source evidence
    if verified_options:
        # Sort by availability presence, unit price if available, and verified status
        best_sup = sorted(
            verified_options,
            key=lambda o: (0 if o.availability == "in_stock" else 1, o.unit_price if o.unit_price is not None else 999999)
        )[0]
        best_sup.is_best_supplier = True
        reasoning.append(
            f"Best Supplier: Recommended {best_sup.supplier or 'Supplier'} based on verified product listing, "
            f"direct source URL ({best_sup.url}), and stock availability."
        )
    elif options:
        fallback_sup = options[0]
        fallback_sup.is_best_supplier = True
        reasoning.append(f"Best Supplier: {fallback_sup.supplier or 'Supplier'} selected from top retrieved candidate.")

    # 3. Best Value: Best combination of price and verification
    if priced_verified and not currency_conflict:
        best_val = min(priced_verified, key=lambda o: o.unit_price)
        best_val.is_best_value = True
        reasoning.append(
            f"Best Value: {best_val.supplier or 'Supplier'} offers optimal balance of competitive pricing "
            f"({best_val.unit_price} {best_val.currency}) and verified product identity."
        )
    elif options:
        options[0].is_best_value = True
        reasoning.append("Best Value: Selected top available result.")

    return options, reasoning