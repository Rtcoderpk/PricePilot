"""Research agent — gathers REAL evidence per canonical product.

Every fact preserves its source. Missing fields stay None/unknown; nothing is
filled by model knowledge.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pricepilot.agents.state import AgentState, ResearchEvidence, SourceRef
from pricepilot.logging import get_logger

log = get_logger("agents.research")


async def node(state: AgentState) -> AgentState:
    evidence = dict(state.research_evidence)
    for product in state.canonical_products:
        offers = product.get("offers", []) or []
        identifiers = []
        for offer in offers:
            for ident in offer.get("identifiers", []) or []:
                if ident.get("type") in ("gtin", "ean", "upc", "mpn") and ident.get("value"):
                    identifiers.append({"type": ident["type"], "value": ident["value"]})
        # dedupe identifiers
        seen = set()
        unique_ids = []
        for ident in identifiers:
            key = (ident["type"], ident["value"])
            if key not in seen:
                seen.add(key)
                unique_ids.append(ident)

        first_offer = offers[0] if offers else {}
        evidence[product["product_id"]] = ResearchEvidence(
            product_id=product["product_id"],
            name=product.get("name", ""),
            brand=product.get("brand") or first_offer.get("brand"),
            category=product.get("category") or first_offer.get("category"),
            quantity=first_offer.get("quantity"),
            storage=first_offer.get("storage"),
            image_url=product.get("image_url") or first_offer.get("image_url"),
            identifiers=unique_ids,
            offer_count=len(offers),
            sources=[
                SourceRef(
                    source=offer.get("data_source") or offer.get("provider") or "provider",
                    provider=offer.get("provider"),
                    url=offer.get("url"),
                    timestamp=datetime.now(UTC),
                )
                for offer in offers
            ],
        )
    return state.model_copy(update={"research_evidence": evidence})