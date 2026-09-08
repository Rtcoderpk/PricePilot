"""Unit tests for the search orchestration service.

Stubs the real provider via dependency-ish subclassing so we never hit the
network in unit tests; the API integration test covers the HTTP layer.
"""

from __future__ import annotations

from pricepilot.models import RawOffer, SearchResponse
from pricepilot.providers.search.openfoodfacts import OpenFoodFactsProvider
from pricepilot.services.search import SearchService, is_fixture_mode


class StubOFF(OpenFoodFactsProvider):
    """Mimics the adapter shape without network I/O."""

    def __init__(self, offers: list[RawOffer], *, raises: bool = False) -> None:
        self._offers = offers
        self._raises = raises

    async def available(self) -> bool:
        return True

    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        if self._raises:
            raise RuntimeError("upstream exploded")
        return self._offers

    async def close(self) -> None:
        return None


def _offer(title: str, code: str, price: float | None = None) -> RawOffer:
    return RawOffer(
        provider="openfoodfacts",
        title=title,
        url=f"https://example/{code}",
        price_amount=price,
        price_currency="EUR" if price is not None else "USD",
        data_source="openfoodfacts",
        raw={"code": code},
    )


async def test_grouping_and_insight() -> None:
    offers = [
        _offer("Nutella", "AAA", 4.0),
        _offer("Nutella Jar", "AAA", 4.5),
        _offer("Other", "BBB", 3.0),
    ]
    svc = SearchService()
    svc.provider = StubOFF(offers)
    result: SearchResponse = await svc.run_search("nutella")
    await svc.close()

    assert result.total == 2
    by_name = {p.name for p in result.products}
    assert {"Nutella", "Other"} == by_name
    grouped = next(p for p in result.products if p.name == "Nutella")
    assert len(grouped.offers) == 2
    assert grouped.price_insight is not None
    assert grouped.price_insight.current == 4.0  # min of [4.0, 4.5]
    assert grouped.price_insight.sample_count == 2
    assert result.generated_at is not None


async def test_provider_error_degrades_to_empty() -> None:
    svc = SearchService()
    svc.provider = StubOFF([], raises=True)
    result: SearchResponse = await svc.run_search("x")
    await svc.close()
    assert result.total == 0
    assert result.products == []
    assert result.providers[0].availability.value == "available"


def test_fixture_detection() -> None:
    assert is_fixture_mode([_offer("a", "1").model_copy(update={"is_fixture": True})])
    assert not is_fixture_mode([_offer("a", "1")])
    assert not is_fixture_mode([])