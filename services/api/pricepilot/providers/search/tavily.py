"""Tavily Search Provider.

Fallback 1 search provider. Uses Tavily API for LLM-optimized real web product search.
"""

from __future__ import annotations

import re
import httpx

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.models import RawOffer
from pricepilot.providers.search import SearchProvider

log = get_logger("providers.search.tavily")

_TAVILY_URL = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
    name = "tavily"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 12.0,
    ) -> None:
        self.api_key = api_key or settings.tavily_api_key
        self.timeout = timeout

    async def available(self) -> bool:
        return bool(self.api_key)

    async def close(self) -> None:
        pass

    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        """Search Tavily for product listings matching `query`."""
        if not await self.available() or not query.strip():
            return []

        clean_query = query.strip()
        offers: list[RawOffer] = []

        payload = {
            "api_key": self.api_key,
            "query": clean_query,
            "search_depth": "basic",
            "include_answer": False,
            "max_results": min(max_results, 10),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.post(_TAVILY_URL, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    offers = self._parse_tavily_results(data.get("results", []), clean_query)
                else:
                    log.warning("Tavily API returned status %d: %s", resp.status_code, resp.text)
        except Exception as exc:
            log.warning("Tavily search failed for %r: %s", query, exc)

        return offers

    def _parse_tavily_results(self, results: list[dict], original_query: str) -> list[RawOffer]:
        offers: list[RawOffer] = []

        for item in results:
            title = item.get("title") or original_query
            url = item.get("url")
            content = item.get("content", "")

            if not url:
                continue

            # Price extraction
            price_val: float | None = None
            currency = "USD"
            price_match = re.search(r'(\$|USD\s*|€|£)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)', content)
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

            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            brand_name = domain_match.group(1).split(".")[0].title() if domain_match else "Retailer"

            offers.append(
                RawOffer(
                    provider="tavily",
                    title=title,
                    url=url,
                    price_amount=price_val,
                    price_currency=currency,
                    availability="in_stock" if price_val is not None else "check_site",
                    data_source="tavily",
                    brand=brand_name,
                    raw={"content": content},
                )
            )

        return offers
