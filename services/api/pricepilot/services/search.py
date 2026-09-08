"""Search orchestration service.

Coordinates configured search providers in parallel, normalizes results, and
produces the response envelope. Provider availability is always reported
honestly — unconfigured slots do not fabricate data.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from pricepilot.logging import get_logger
from pricepilot.models import ProviderStatus, RawOffer, SearchResponse
from pricepilot.providers.registry import build_search_provider, search_provider_status
from pricepilot.providers.search.openfoodfacts import OpenFoodFactsProvider

log = get_logger("services.search")


class SearchService:
    def __init__(self, *, cache=None) -> None:
        self.provider = build_search_provider()
        self.cache = cache  # optional redis cache client

    async def run_search(
        self,
        query: str,
        *,
        max_results: int = 20,
        cache_keys: tuple[str, int] | None = None,
    ) -> SearchResponse:
        """Run a provider search, honoring an optional Redis cache.

        `cache_keys` is `(query, max_results)`; when a cache client is present,
        identical queries are served from cache for its TTL (reduces provider
        load / rate-limit pressure and speeds repeated UI renders).
        """
        cache_key = f"search:{query}:{max_results}" if self.cache is not None and cache_keys else None
        if cache_key:
            cached = await self._get_cached(cache_key)
            if cached is not None:
                log.info("search cache hit for %r", query)
                return cached
            log.info("search cache miss for %r", query)

        result = await self._run_search_once(query, max_results=max_results)

        if cache_key and result.products and cache_ok(result):
            await self._set_cached(cache_key, result)
        return result

    async def _run_search_once(self, query: str, *, max_results: int) -> SearchResponse:
        provider = self.provider
        status = search_provider_status()

        if not isinstance(provider, OpenFoodFactsProvider):
            # Not yet a real configured source; keep the interface intact, report
            # honestly, and return an empty envelope rather than fake results.
            log.info("search provider not enabled; returning empty result for %r", query)
            return SearchResponse(
                query=query,
                products=[],
                providers=[status],
                total=0,
                generated_at=datetime.utcnow(),
                notice="Search provider is not configured — configure a search provider to get results.",
            )

        offers: list[RawOffer] = []
        try:
            offers = await asyncio.wait_for(
                provider.search(query, max_results=max_results),
                timeout=20,
            )
        except TimeoutError:
            log.warning("search timed out for query %r", query)
            offers = []
        except Exception:
            log.exception("search provider error for query %r", query)
            offers = []

        status = ProviderStatus(
            name="search",
            availability="available",
            reason=None,
        )

        products = _group_offers_into_products(offers)
        notice = None
        if is_fixture_mode(offers):
            notice = "Demo mode: showing fixture data, not live prices."
        if not offers:
            notice = "No offers returned — the provider may rate-limit or have no results."

        return SearchResponse(
            query=query,
            products=products,
            providers=[status],
            total=len(products),
            generated_at=datetime.utcnow(),
            notice=notice,
        )

    async def _get_cached(self, key: str) -> SearchResponse | None:
        try:
            raw = await self.cache.get(key)
            if raw is None:
                return None
            return SearchResponse.model_validate_json(raw)
        except Exception:
            log.warning("search cache read failed for %s", key)
            return None

    async def _set_cached(self, key: str, result: SearchResponse) -> None:
        try:
            await self.cache.set(key, result.model_dump_json(), ex=300)
        except Exception:
            log.warning("search cache write failed for %s", key)

    async def close(self) -> None:
        await self.provider.close()


def cache_ok(result: SearchResponse) -> bool:
    """Don't cache transient empty/failed envelopes for 5 minutes."""
    from pricepilot.models import ProviderAvailability

    return bool(result.products) and all(
        p.availability != ProviderAvailability.UNAVAILABLE for p in result.providers
    )


def _group_offers_into_products(offers: list[RawOffer]) -> list:
    """Group raw offers into per-product results.

    Phase 1 keeps offers as provider-shaped items; TRUE dedup/matching across
    canonical identities lands in Phase 2 (`product_matching`). Here we simply
    bucket offers that share the same OFF barcode code so the UI can render
    one card per real product.
    """
    from pricepilot.models import PriceInsight, ProductResult

    grouped: dict[str, list[RawOffer]] = {}
    for offer in offers:
        code = offer.raw.get("code")
        key = str(code) if code else offer.title
        grouped.setdefault(key, []).append(offer)

    products: list[ProductResult] = []
    for _key, bucket in grouped.items():
        first = bucket[0]
        priced = [o.price_amount for o in bucket if o.price_amount is not None]
        insight = PriceInsight(
            current=min(priced) if priced else None,
            currency=bucket[0].price_currency,
            sample_count=len(priced),
        )
        products.append(
            ProductResult(
                canonical_product_id=str(first.raw.get("code") or _slugify(first.title)),
                name=first.title,
                brand=first.raw.get("brands"),
                category=first.raw.get("categories"),
                image_url=first.raw.get("image_small_url"),
                description=None,
                offers=bucket,
                price_insight=insight,
                is_fixture=False,
            )
        )
    return products


def is_fixture_mode(offers: list[RawOffer]) -> bool:
    return bool(offers) and all(o.is_fixture for o in offers)


def _slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "product"