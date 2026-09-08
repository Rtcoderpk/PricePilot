"""Deal Score agent — deterministic, explainable 0–100 score.

Components (each 0–100), combined with weights:
  price_value     - based on number of offers + cheapest completeness
                    (no history → mred to 50 so we don't overclaim)
  offer_competition - 100 if ≥3 offers, 70 if 2, 45 if 1, 20 if 0 (missing data)
  availability    - 100 if available, else 40
  seller_signal   - from SellerAnalysis label: 90/65/40/30
  review_signal   - 50 always when unavailable (warned via missing-data)

The label is driven by score bands. If too little data exists (e.g. no price,
no offers), the score is None/label "Insufficient Data" — never pretend.
"""

from __future__ import annotations

from pricepilot.agents.state import (
    AgentState,
    DealScore,
    SellerSignalLabel,
)
from pricepilot.logging import get_logger

log = get_logger("agents.deal_score")

_WEIGHTS = {
    "price_value": 0.35,
    "offer_competition": 0.20,
    "availability": 0.15,
    "seller_signal": 0.20,
    "review_signal": 0.10,
}


def _seller_score(label: SellerSignalLabel) -> float:
    return {
        SellerSignalLabel.VERIFIED_SIGNAL: 90.0,
        SellerSignalLabel.LIMITED_INFORMATION: 60.0,
        SellerSignalLabel.INSUFFICIENT_DATA: 35.0,
    }[label]


def _band(score: float) -> str:
    if score is None:
        return "Insufficient Data"
    if score >= 80:
        return "Excellent Deal"
    if score >= 65:
        return "Good Deal"
    if score >= 50:
        return "Fair Deal"
    return "Weak Deal"


async def node(state: AgentState) -> AgentState:
    scores = dict(state.deal_scores)
    for product in state.canonical_products:
        pid = product["product_id"]
        price = state.price_analysis.get(pid)
        seller = state.seller_analysis.get(pid)
        review = state.review_analysis.get(pid)

        offers_avail = product.get("offers", []) or []
        have_price = bool(price and price.lowest_offer is not None)
        n_offers = len(offers_avail)

        missing: list[str] = []
        if not have_price:
            missing.append("no price available")
        if not n_offers:
            missing.append("no offers")
        if not seller or seller.label == SellerSignalLabel.INSUFFICIENT_DATA:
            missing.append("insufficient seller data")
        if review and review.status != "available":
            missing.append("review data unavailable")

        # Component scores (each 0..100)
        price_value = 50.0  # neutral baseline (no history → don't over/under-claim)
        if have_price:
            # more offers → higher implied confidence in the real price
            price_value = min(90.0, 50.0 + (n_offers * 10.0))

        offer_comp = {0: 20.0, 1: 45.0, 2: 70.0}.get(n_offers, 100.0)

        availability = 100.0 if (seller and seller.offer_availability) else 60.0

        seller_score = _seller_score(seller.label) if seller else 35.0

        review_score = 50.0  # neutral; unavailable is surfaced in missing-data

        components = {
            "price_value": round(price_value, 1),
            "offer_competition": offer_comp,
            "availability": round(availability, 1),
            "seller_signal": round(seller_score, 1),
            "review_signal": review_score,
        }
        weighted = sum(components[k] * _WEIGHTS[k] for k in _WEIGHTS)
        decided = round(weighted, 1)

        # If we essentially have no data, don't present a score as meaningful.
        if not have_price and n_offers == 0:
            scores[pid] = DealScore(
                product_id=pid, score=None, label="Insufficient Data",
                components={}, reasons=[], missing_data_warnings=missing,
            )
            continue

        reasons = [
            f"{len(price.sources) if price else 1} real offer{'s' if (price and price.offer_count != 1) else ''} considered"
            if (price and price.offer_count) else "no price present",
            f"price value score {components['price_value']:.0f}/100",
            f"offer competition {components['offer_competition']:.0f}/100",
            f"seller signal {components['seller_signal']:.0f}/100",
        ]
        scores[pid] = DealScore(
            product_id=pid,
            score=decided,
            label=_band(decided),
            components=components,
            reasons=reasons,
            missing_data_warnings=missing,
        )
    return state.model_copy(update={"deal_scores": scores})