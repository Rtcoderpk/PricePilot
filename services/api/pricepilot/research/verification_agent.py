"""Verification agent — checks retrieved data before recommendation.

Assigns a state based purely on what the source actually provided:
- VERIFIED: source identity + product + price + currency are all present
- PARTIALLY_VERIFIED: at least source + product present
- UNVERIFIED: not enough real data

Never upgrades an unverified source to verified without evidence; never invents
verification.
"""

from __future__ import annotations

from pricepilot.logging import get_logger
from pricepilot.models import SupplierResult, VerificationResult, VerificationState

log = get_logger("research.verification_agent")


def verify_results(results: list[SupplierResult]) -> list[VerificationResult]:
    return [verify_one(i, r) for i, r in enumerate(results)]


def verify_one(index: int, r: SupplierResult) -> VerificationResult:
    checks: list[str] = []
    notes: list[str] = []

    if r.supplier:
        checks.append("supplier_identified")
    if r.product:
        checks.append("product_present")
    if r.price is not None:
        checks.append("price_present")
    if r.currency:
        checks.append("currency_known")
    if r.url:
        checks.append("source_url_present")
    if r.moq is not None:
        checks.append("moq_present")
    if r.availability:
        checks.append("availability_present")

    if r.supplier is None:
        notes.append("No supplier identity in the source data.")
    if r.price is None:
        notes.append("No price available from the source.")
    if r.currency is None:
        notes.append("Currency not specified.")

    if r.supplier and r.product and r.price is not None and r.currency:
        state = VerificationState.VERIFIED
    elif r.supplier and r.product:
        state = VerificationState.PARTIALLY_VERIFIED
    else:
        state = VerificationState.UNVERIFIED

    return VerificationResult(result_index=index, state=state, checks=checks, notes=notes)