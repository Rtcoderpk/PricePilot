"""Price Intelligence agent — real offer/history analysis per product.

Computes lowest/highest/average current offer from the offers actually present.
`price_position` is only meaningful when the stored price history supports it;
for live searches (no stored history yet) it returns `insufficient_history`
honestly. Never invents "lowest ever".
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

from pricepilot.agents.state import AgentState, PriceAnalysis, PricePosition, SourceRef
from pricepilot.logging import get_logger

log = get_logger("agents.price")


async def node(state: AgentState) -> AgentState:
    analysis = dict(state.price_analysis)
    for product in state.canonical_products:
        offers = product.get("offers", []) or []
        prices = [o["price_amount"] for o in offers if o.get("price_amount") is not None]
        currency = None
        shipping = None
        for offer in offers:
            if offer.get("price_currency"):
                currency = offer["price_currency"]
            if offer.get("shipping_amount") is not None and shipping is None:
                shipping = float(offer["shipping_amount"])
            break  # use first offer's currency/shipping; OFF is single-currency

        price_pos = PricePosition.NO_PRICE if not prices else PricePosition.INSUFFICIENT_HISTORY
        best, worst, avg = (None, None, None)
        if prices:
            best = min(prices)
            worst = max(prices)
            avg = round(statistics.mean(prices), 2)

        analysis[product["product_id"]] = PriceAnalysis(
            product_id=product["product_id"],
            lowest_offer=best,
            highest_offer=worst,
            average_offer=avg,
            offer_count=len(prices),
            currency=currency,
            price_timestamp=datetime.now(UTC),
            shipping_cost=shipping,
            total_known_cost=(best + shipping) if (best is not None and shipping) else None,
            price_position=price_pos,
            sources=[
                SourceRef(source=o.get("data_source") or o.get("provider") or "provider", url=o.get("url"))
                for o in offers
            ],
        )
    return state.model_copy(update={"price_analysis": analysis})