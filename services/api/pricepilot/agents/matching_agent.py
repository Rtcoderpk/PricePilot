"""Matching agent — reuses the Phase 2 canonical engine verbatim.

Consumes `candidate_offers` and produces `canonical_products`. Never merges
contradictory variants; low-confidence pairs stay separate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pricepilot.agents.state import AgentState
from pricepilot.logging import get_logger
from pricepilot.services.canonical import canonicalize

log = get_logger("agents.matching")


async def node(state: AgentState) -> AgentState:
    offers = state.candidate_offers
    if not offers:
        return state.model_copy(
            update={
                "warnings": state.warnings + ["No offers to match — nothing to recommend"],
            }
        )

    products = canonicalize(offers)
    canonical = [_serialize_product(p) for p in products]
    log.info("matching grouped %d offers into %d canonical products", len(offers), len(products))
    return state.model_copy(update={"canonical_products": canonical})


def _serialize_product(product) -> dict:
    """Serialize a CanonicalProduct (dataclass) into a JSON-safe dict."""

    offers = [o.model_dump(mode="json") for o in product.offers] if product.offers else []
    return {
        "product_id": product.product_id,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "image_url": product.image_url,
        "variant": product.variant,
        "match_confidence": product.match_confidence,
        "match_method": product.match_method,
        "offers": offers,
        "best_price": product.best_price,
        "provider_count": product.provider_count,
    }