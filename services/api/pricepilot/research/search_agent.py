"""Search agent — turns a ProductQuery into real retrieved supplier/product results.

Uses the configured SearchProvider(s) (e.g. OpenFoodFacts) through the existing
`SearchService` orchestration. Results are normalized into `SupplierResult` with
null values for anything the provider did not supply. The agent NEVER constructs
supplier names, prices, MOQs, URLs, etc. from nothing.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from pricepilot.logging import get_logger
from pricepilot.models import SupplierResult

log = get_logger("research.search_agent")


async def search_suppliers(query: str, *, max_results: int = 20) -> list[SupplierResult]:
    """Run a real provider search and normalize to SupplierResult list.

    `query` may be a single phrase; the caller (research pipeline) can iterate
    over `ProductQuery.search_queries`.
    """
    from pricepilot.providers.registry import build_providers
    from pricepilot.providers.search import NoopSearchProvider

    providers = [p for p in build_providers() if not isinstance(p, NoopSearchProvider)]
    if not providers:
        return []

    per_provider = max(1, max_results // len(providers))
    results: list[SupplierResult] = []

    async def _one(provider) -> None:
        try:
            offers = await asyncio.wait_for(
                provider.search(query, max_results=per_provider), timeout=20
            )
        except TimeoutError:
            log.warning("provider %s timed out for %r", provider.name, query)
            return
        except Exception:
            log.exception("provider %s failed for %r", provider.name, query)
            return
        for o in offers:
            results.append(_offer_to_supplier(o, provider.name))

    await asyncio.gather(*(_one(p) for p in providers))
    return results


def _offer_to_supplier(offer, source: str) -> SupplierResult:
    """Normalize a RawOffer into a SupplierResult (nulls for missing data)."""
    return SupplierResult(
        title=offer.title,
        supplier=offer.brand or offer.provider,
        product=offer.title,
        price=offer.price_amount,
        currency=offer.price_currency,
        url=offer.url,
        source=source,
        moq=None,  # providers don't supply MOQ; never invent
        availability=offer.availability,
        shipping=None,
        rating=None,
        source_timestamp=datetime.now(UTC).isoformat(),
        match_info={"data_source": offer.data_source, "is_fixture": offer.is_fixture},
    )