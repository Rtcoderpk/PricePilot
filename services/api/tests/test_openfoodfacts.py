"""Unit tests for the OpenFoodFacts search adapter.

Uses httpx.MockTransport to keep tests offline and deterministic while still
exercising the real JSON client (status/content-type checks, normalization).
"""

from __future__ import annotations

import httpx
import pytest

from pricepilot.errors import ProviderError
from pricepilot.providers.base import JsonClient
from pricepilot.providers.search.openfoodfacts import OpenFoodFactsProvider


def _client(handler) -> JsonClient:
    transport = httpx.MockTransport(handler)
    inner = httpx.AsyncClient(transport=transport, base_url="https://world.openfoodfacts.org")
    return JsonClient(
        base_url="https://world.openfoodfacts.org",
        timeout=10,
        client=inner,
    )


@pytest.fixture
def sample_payload() -> dict:
    return {
        "products": [
            {
                "code": "3017620422003",
                "product_name": "Nutella",
                "brands": "Ferrero",
                "categories": "en:spreads",
                "url": "https://world.openfoodfacts.org/product/3017620422003",
                "product_price": 4.5,
                "product_available": True,
                "image_small_url": "https://images.openfoodfacts.org/x.jpg",
            },
            {
                "code": "1234",
                "product_name": "Cheap Stuff",
                "brands": "Acme",
            },
        ]
    }


async def test_search_normalizes_offers(sample_payload):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sample_payload, headers={"content-type": "application/json"})

    provider = OpenFoodFactsProvider(client=_client(handler))
    offers = await provider.search("nutella", max_results=20)
    await provider.close()

    assert len(offers) == 2
    first = offers[0]
    assert first.provider == "openfoodfacts"
    assert first.title == "Nutella"
    assert first.price_amount == 4.5
    assert first.price_currency == "EUR"  # OFF product_price is EUR
    assert first.raw["code"] == "3017620422003"
    # second offer has no price → price_amount None (never fabricated)
    assert offers[1].price_amount is None


async def test_search_returns_empty_on_no_products():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"products": []}, headers={"content-type": "application/json"})

    provider = OpenFoodFactsProvider(client=_client(handler))
    offers = await provider.search("nothing")
    await provider.close()
    assert offers == []


async def test_malformed_json_raises_provider_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>", headers={"content-type": "text/html"})

    provider = OpenFoodFactsProvider(client=_client(handler))
    with pytest.raises(ProviderError):
        await provider.search("x")
    await provider.close()


async def test_http_error_propagates():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"}, headers={"content-type": "application/json"})

    provider = OpenFoodFactsProvider(client=_client(handler))
    with pytest.raises(ProviderError):
        await provider.search("x")
    await provider.close()