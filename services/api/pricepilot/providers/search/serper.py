"""Serper Google Search Provider.

Fallback 2 search provider. Uses Serper.dev API for fast Google search indexing.
"""

from __future__ import annotations

import re
import httpx

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.models import RawOffer
from pricepilot.providers.search import SearchProvider

log = get_logger("providers.search.serper")

_SERPER_URL = "https://google.serper.dev/search"


class SerperSearchProvider(SearchProvider):
    name = "serper"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 12.0,
    ) -> None:
        self.api_key = api_key or settings.serper_api_key
        self.timeout = timeout

    async def available(self) -> bool:
        return bool(self.api_key)

    async def close(self) -> None:
        pass

    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        """Search Serper.dev for product listings matching `query`."""
        if not await self.available() or not query.strip():
            return []

        clean_query = query.strip()
        offers: list[RawOffer] = []

        headers = {
            "X-API-KEY": self.api_key or "",
            "Content-Type": "application/json",
        }
        payload = {
            "q": clean_query,
            "num": min(max_results, 10),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(_SERPER_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    offers = self._parse_organic_results(data.get("organic", []), clean_query)
                else:
                    log.warning("Serper API returned status %d: %s", resp.status_code, resp.text)
        except Exception as exc:
            log.warning("Serper search failed for %r: %s", query, exc)

        return offers

    def _parse_organic_results(self, organic: list[dict], original_query: str) -> list[RawOffer]:
        offers: list[RawOffer] = []

        for item in organic:
            title = item.get("title") or original_query
            link = item.get("link")
            snippet = item.get("snippet", "")

            if not link:
                continue

            price_val: float | None = None
            currency = "USD"
            price_match = re.search(r'(\$|USD\s*|€|£)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)', snippet)
            if price_match:
                symbol, num_str = price_match.group(1), price_match.group(2)
                if symbol == "€":
                    currency = "EUR"
                elif symbol == "£":
                    currency = "GBP"
                try:
                    price_val = float(num_str.replace(",", ""))
                except ValueError:
                    price_val = None

            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', link)
            brand_name = domain_match.group(1).split(".")[0].title() if domain_match else "Retailer"

            offers.append(
                RawOffer(
                    provider="serper",
                    title=title,
                    url=link,
                    price_amount=price_val,
                    price_currency=currency,
                    availability="in_stock" if price_val is not None else "check_site",
                    data_source="serper",
                    brand=brand_name,
                    raw={"snippet": snippet},
                )
            )

        return offers
