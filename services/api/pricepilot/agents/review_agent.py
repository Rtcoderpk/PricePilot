"""Review Intelligence agent — uses only REAL reviews from a review provider.

The review schema/nodes are production-ready, but no review data source is
configured at present, so this returns `review_data_unavailable` honestly.
No fabricated reviews, quotes, or sentiment.
"""

from __future__ import annotations

from pricepilot.agents.state import AgentState, ReviewAnalysis
from pricepilot.logging import get_logger

log = get_logger("agents.review")


async def node(state: AgentState) -> AgentState:
    analysis = dict(state.review_analysis)
    for product in state.canonical_products:
        # TODO(phase 4): call a configured ReviewProvider and populate themes from
        # real review text. Until one is configured, remain honest.
        analysis[product["product_id"]] = ReviewAnalysis(
            product_id=product["product_id"],
            status="review_data_unavailable",
        )
    return state.model_copy(update={"review_analysis": analysis})