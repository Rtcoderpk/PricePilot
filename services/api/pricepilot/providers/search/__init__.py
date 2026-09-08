"""Search provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pricepilot.models import RawOffer


class SearchProvider(ABC):
    """A source of candidate products for an arbitrary query.

    Implementations normalize raw results into `RawOffer` and are responsible
    for their own requests, timeouts, parsing, and rate limiting.
    """

    name: str = "search"

    @abstractmethod
    async def available(self) -> bool:
        """Whether this provider is configured and usable right now."""

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        """Search for products matching `query` and return normalized offers."""

    @abstractmethod
    async def close(self) -> None:
        """Release any held resources (HTTP clients, etc.)."""


class NoopSearchProvider(SearchProvider):
    """Honest no-op used when no search provider is configured.

    Returns zero results and is reported as unavailable — it never fabricates
    products or prices.
    """

    name = "unavailable"

    async def available(self) -> bool:
        return False

    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        return []

    async def close(self) -> None:
        return None