"""Provider registry.

Resolves configured provider slots (search, ai, ...) at runtime from
environment-based settings. Missing configuration is surfaced as an explicit
`unavailable` status — never silently fabricated.
"""

from __future__ import annotations

from functools import lru_cache

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.models import ProviderStatus
from pricepilot.providers.search import NoopSearchProvider, SearchProvider
from pricepilot.providers.search.openfoodfacts import OpenFoodFactsProvider

log = get_logger("providers.registry")


def build_search_provider() -> SearchProvider:
    selected = (settings.pricepilot_search_provider or "").strip().lower()
    if selected == "openfoodfacts":
        log.info("search provider: openfoodfacts")
        return OpenFoodFactsProvider()
    if selected == "":
        log.warning("no search provider configured; using honest no-op")
        return NoopSearchProvider()
    log.warning("unknown search provider %r; using honest no-op", selected)
    return NoopSearchProvider()


def search_provider_status() -> ProviderStatus:
    provider = build_search_provider()
    # availability is determined per-status so callers don't await a network call
    if isinstance(provider, OpenFoodFactsProvider):
        return ProviderStatus(name="search", availability="available", reason=None)
    return ProviderStatus(
        name="search",
        availability="unavailable",
        reason="PRICEPILOT_SEARCH_PROVIDER not configured to a live provider",
    )


@lru_cache
def get_search_provider() -> SearchProvider:
    return build_search_provider()