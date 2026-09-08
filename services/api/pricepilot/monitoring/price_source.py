"""Price source for the monitoring worker.

Wraps the configured search/price provider to return a CURRENT real price/offer
observation for a monitored product. Honest contraction:

- When the provider is a real one (OpenFoodFacts) it fetches live data.
- It only emits a price when the provider actually supplies a `product_price`;
  otherwise returns `amount=None` (no fabricated price).
- Unavailable/error → `status="provider_unavailable"` / `"provider_failed"`.

Offers are matched to a monitored product via its canonical `products.id` and a
known barcode from `product_identifiers`. Real barcode → real OFF product.
"""

from __future__ import annotations

from dataclasses import dataclass

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.base import JsonClient

log = get_logger("monitoring.price_source")


@dataclass
class FetchResult:
    status: str  # "ok" | "no_price" | "provider_unavailable" | "provider_failed"
    amount: float | None = None
    currency: str | None = None
    available: bool | None = None
    barcode: str | None = None
    reason: str | None = None


class PriceSource:
    def __init__(self) -> None:
        self._client: JsonClient | None = None

    async def _client_or_none(self):
        if self._client is None:
            self._client = JsonClient(
                base_url=settings.off_api_base_url,
                timeout=settings.monitor_provider_timeout_seconds,
                headers={"User-Agent": "PricePilotBot/0.1 (AI shopping agent)"},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_current_price(self, barcode: str) -> FetchResult:
        """Fetch the current price for an OFF barcode (real evidence only)."""
        if not barcode:
            return FetchResult("provider_failed", reason="no barcode for monitored product")
        client = await self._client_or_none()
        try:
            data = await client.get_json(f"/api/v0/product/{barcode}.json")
        except Exception as exc:
            # 404 means the barcode isn't in OFF (no fabrication); other errors =
            # provider outage.
            msg = getattr(exc, "code", "?")
            log.warning("monitor price fetch failed for %s (%s)", barcode, msg)
            if isinstance(exc, Exception) and getattr(exc, "status_code", None) == 404:
                return FetchResult("no_price", reason="barcode not found in provider", barcode=barcode)
            return FetchResult("provider_failed", reason="provider error", barcode=barcode)

        product = data.get("product") if isinstance(data, dict) else None
        if not isinstance(product, dict):
            return FetchResult("no_price", reason="no product payload", barcode=barcode)

        amount = product.get("product_price")
        available = product.get("product_available")
        if amount is None:
            return FetchResult("no_price", reason="provider supplies no price", barcode=barcode)
        try:
            amount_f = float(amount)
        except (TypeError, ValueError):
            return FetchResult("no_price", reason="invalid price payload", barcode=barcode)
        return FetchResult(
            "ok",
            amount=amount_f,
            currency="EUR",
            available=bool(available) if available is not None else None,
            barcode=barcode,
        )


def price_source_status() -> str:
    """Honest capability: monitoring depends on the configured search provider
    being a real one (currently OpenFoodFacts). Returns 'available'|'unavailable'."""
    name = (settings.pricepilot_search_provider or "").strip().lower()
    if "openfoodfacts" in name:
        return "available"
    return "unavailable"