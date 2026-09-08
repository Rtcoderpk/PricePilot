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

# Canonical search-provider names → builders.
_PROVIDER_BUILDERS = {
    "openfoodfacts": OpenFoodFactsProvider,
}


def _configured_names() -> list[str]:
    raw = (settings.pricepilot_search_provider or "").strip().lower()
    if not raw:
        return []
    return [name.strip() for name in raw.split(",") if name.strip()]


def build_providers() -> list[SearchProvider]:
    """Build all configured search providers.

    Supports a comma-separated `PRICEPILOT_SEARCH_PROVIDER` (e.g.
    "openfoodfacts"). Unknown/empty names are logged and dropped; an empty
    config yields the honest no-op.
    """
    names = _configured_names()
    providers: list[SearchProvider] = []
    for name in names:
        builder = _PROVIDER_BUILDERS.get(name)
        if builder is None:
            log.warning("unknown search provider %r; ignoring", name)
            continue
        providers.append(builder())
    if not providers:
        log.warning("no search provider configured; using honest no-op")
        providers.append(NoopSearchProvider())
    return providers


def build_search_provider() -> SearchProvider:
    """Backward-compatible single-provider accessor.

    Returns the first configured provider, or the honest no-op.
    """
    return build_providers()[0]


def search_provider_statuses() -> list[ProviderStatus]:
    """A status per configured provider (and an honest unavailable when none)."""
    providers = build_providers()
    statuses: list[ProviderStatus] = []
    for provider in providers:
        if isinstance(provider, NoopSearchProvider):
            statuses.append(
                ProviderStatus(
                    name="search",
                    availability="unavailable",
                    reason="PRICEPILOT_SEARCH_PROVIDER not configured to a live provider",
                )
            )
        else:
            statuses.append(ProviderStatus(name=provider.name, availability="available", reason=None))
    return statuses


def search_provider_status() -> ProviderStatus:
    """Backward-compatible single status (first result or honest unavailable)."""
    return search_provider_statuses()[0]


@lru_cache
def get_search_provider() -> SearchProvider:
    return build_search_provider()