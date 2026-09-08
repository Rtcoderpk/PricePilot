"""Search orchestration service.

Coordinates configured search providers in parallel, canonicalizes raw offers
into deduplicated products (see services/canonical), and produces the response
envelope. Provider availability is always reported honestly — unconfigured
slots do not fabricate data.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from pricepilot.logging import get_logger
from pricepilot.models import PriceInsight, ProductResult, RawOffer, SearchResponse
from pricepilot.providers.registry import build_providers, search_provider_statuses
from pricepilot.providers.search import NoopSearchProvider
from pricepilot.services.canonical import canonicalize

log = get_logger("services.search")

# Per-provider request budget; one slow provider must not block the rest.
PROVIDER_TIMEOUT_SECONDS = 20


class SearchService:
    def __init__(self, *, cache=None) -> None:
        self.providers = build_providers()
        self._single_provider = self.providers[0] if self.providers else None
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
        statuses = search_provider_statuses()
        live = [p for p in self.providers if not isinstance(p, NoopSearchProvider)]

        if not live:
            log.info("no search provider enabled; returning empty result for %r", query)
            return SearchResponse(
                query=query,
                products=[],
                providers=statuses,
                total=0,
                generated_at=datetime.utcnow(),
                notice="Search provider is not configured — configure a search provider to get results.",
            )

        offers = await self._call_providers(live, query, max_results=max_results)
        notice = None
        if is_fixture_mode(offers):
            notice = "Demo mode: showing fixture data, not live prices."
        if not offers:
            notice = "No offers returned — the provider may rate-limit or have no results."

        products = canonicalize(offers)
        products = _to_results(products)

        return SearchResponse(
            query=query,
            products=products,
            providers=statuses,
            total=len(products),
            generated_at=datetime.utcnow(),
            notice=notice,
        )

    async def _call_providers(
        self,
        providers: list,
        query: str,
        *,
        max_results: int,
    ) -> list[RawOffer]:
        """Call all live providers in parallel, collecting offers with graceful
        per-provider timeout/error handling."""
        per_provider = max(1, max_results // len(providers))

        async def _one(provider) -> list[RawOffer]:
            try:
                return await asyncio.wait_for(
                    provider.search(query, max_results=per_provider),
                    timeout=PROVIDER_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                log.warning("search timed out for provider %s query %r", provider.name, query)
                return []
            except Exception:
                log.exception("search provider error for %s query %r", provider.name, query)
                return []

        results = await asyncio.gather(*(_one(p) for p in providers))
        return [offer for batch in results for offer in batch]

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
        import contextlib

        for provider in self.providers:
            with contextlib.suppress(Exception):
                await provider.close()

    @property
    def provider(self):
        """Backward-compatible single-provider view (tests use this)."""
        return self._single_provider

    @provider.setter
    def provider(self, value) -> None:
        self._single_provider = value
        self.providers = [value]


def _to_results(products) -> list[ProductResult]:
    results: list[ProductResult] = []
    for p in products:
        priced = [o.price_amount for o in p.offers if o.price_amount is not None]
        insight = PriceInsight(
            current=min(priced) if priced else None,
            currency=p.offers[0].price_currency if p.offers else "USD",
            sample_count=len(priced),
        )
        results.append(
            ProductResult(
                canonical_product_id=p.product_id,
                name=p.name,
                brand=p.brand,
                category=p.category,
                image_url=p.image_url,
                variant=p.variant,
                match_confidence=p.match_confidence,
                match_method=p.match_method,
                offers=p.offers,
                price_insight=insight,
                is_fixture=bool(p.offers) and all(o.is_fixture for o in p.offers),
            )
        )
    return results


def cache_ok(result: SearchResponse) -> bool:
    """Don't cache transient empty/failed envelopes for 5 minutes."""
    from pricepilot.models import ProviderAvailability

    return bool(result.products) and all(
        p.availability != ProviderAvailability.UNAVAILABLE for p in result.providers
    )


def is_fixture_mode(offers: list[RawOffer]) -> bool:
    return bool(offers) and all(o.is_fixture for o in offers)