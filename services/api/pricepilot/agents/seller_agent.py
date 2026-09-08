"""Seller Intelligence agent — confidence from real seller/offer signals.

Never labels a seller fraudulent without verified evidence. Uses neutral labels
(verified_signal / limited_information / insufficient_data) with reasons.
"""

from __future__ import annotations

from pricepilot.agents.state import AgentState, SellerAnalysis, SellerSignalLabel
from pricepilot.logging import get_logger

log = get_logger("agents.seller")


async def node(state: AgentState) -> AgentState:
    analysis = dict(state.seller_analysis)
    for product in state.canonical_products:
        offers = product.get("offers", []) or []
        signals: list[str] = []
        availability = None
        price_vals = [o["price_amount"] for o in offers if o.get("price_amount") is not None]

        for offer in offers:
            if offer.get("availability"):
                availability = True
                signals.append(f"available from {offer.get('provider') or offer.get('data_source')}")
                break

        if len(price_vals) >= 2:
            spread = (max(price_vals) - min(price_vals)) / (min(price_vals) or 1)
            signals.append(
                f"price consistency across {len(price_vals)} offers"
                + (" (stable)" if spread < 0.05 else " (variable)")
            )
        elif price_vals:
            signals.append("single offer price present")

        if not offers:
            label = SellerSignalLabel.INSUFFICIENT_DATA
            reason = "no offer/seller data for this product"
        elif signals:
            label = SellerSignalLabel.VERIFIED_SIGNAL
            reason = " | ".join(signals[:4])
        else:
            label = SellerSignalLabel.LIMITED_INFORMATION
            reason = "offers present but no seller-rating signals available"

        analysis[product["product_id"]] = SellerAnalysis(
            product_id=product["product_id"],
            seller_name=offers[0].get("provider") if offers else None,
            label=label,
            signals=signals,
            offer_availability=availability,
            price_consistency="stable" if (len(price_vals) >= 2 and max(price_vals) != min(price_vals) and (max(price_vals) - min(price_vals)) / (min(price_vals) or 1) < 0.05) else ("variable" if len(price_vals) >= 2 else "unknown"),
            reason=reason,
        )
    return state.model_copy(update={"seller_analysis": analysis})