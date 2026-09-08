"""OpenFoodFacts search adapter.

OpenFoodFacts is a free, keyless, openly-licensed public product database
(foods). It is used here as the first *real* provider so the full search path
(run endpoint → provider → normalization → response) is exercised with actual
data rather than placeholders. It respects the API by using the brand/user-agent
contract and a bounded page size.

Prices: OFF reports store price as `stores` metadata or `product_price` when
available; most food products carry no price, so offers may be price-less — the
platform shows them honestly as such rather than inventing amounts.
"""

from __future__ import annotations

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pricepilot.config import settings
from pricepilot.errors import ProviderError
from pricepilot.logging import get_logger
from pricepilot.models import RawOffer
from pricepilot.providers.base import JsonClient
from pricepilot.providers.search import SearchProvider

log = get_logger("providers.search.openfoodfacts")


def _transient(exc: BaseException) -> bool:
    """OFF intermittently returns 503 under load; retry only those, with backoff."""
    return isinstance(exc, ProviderError) and exc.status_code in (503, 429)


class OpenFoodFactsProvider(SearchProvider):
    name = "openfoodfacts"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float | None = None,
        product_id_prefix: str = "off",
        client: JsonClient | None = None,
    ) -> None:
        self.base_url = base_url or settings.off_api_base_url
        self.timeout = timeout or settings.off_timeout_seconds
        self.product_id_prefix = product_id_prefix
        self._client = client or JsonClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"User-Agent": "PricePilotBot/0.1 (AI shopping agent)"},
        )

    async def available(self) -> bool:
        return True  # keyless public API; availability is a request-time concern

    @retry(
        retry=retry_if_exception(_transient),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=6),
        reraise=True,
    )
    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        page_size = min(max_results, settings.off_max_page_size)
        data = await self._client.get_json(
            "/api/v2/search",
            params={"search_terms": query, "page_size": page_size, "json": True},
        )
        products = data.get("products")
        if not isinstance(products, list):
            log.warning("openfoodfacts search returned no products list")
            return []

        offers: list[RawOffer] = []
        for raw in products:
            title = raw.get("product_name") or raw.get("generic_name") or "Unnamed product"
            price = raw.get("product_price")
            offers.append(
                RawOffer(
                    provider=self.name,
                    title=str(title)[:512],
                    url=raw.get("url"),
                    price_amount=_to_float(price),
                    price_currency="EUR" if price is not None else "USD",
                    availability="in_stock" if raw.get("product_available") else None,
                    data_source=self.name,
                    is_fixture=False,
                    raw={
                        "code": raw.get("code"),
                        "brands": raw.get("brands"),
                        "categories": raw.get("categories"),
                        "image_small_url": raw.get("image_small_url"),
                        "nutriscore": raw.get("nutriscore_grade"),
                    },
                )
            )
        log.info("openfoodfacts returned %d offers for %r", len(offers), query)
        return offers

    async def close(self) -> None:
        await self._client.aclose()


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None