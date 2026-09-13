"""Google Custom Search Engine (CSE) Provider.

Primary search provider. Uses Google Custom Search JSON API to retrieve real live product
listings, prices, snippets, and source URLs.
"""

from __future__ import annotations

import re
import httpx

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.models import RawOffer
from pricepilot.providers.search import SearchProvider

log = get_logger("providers.search.google_cse")

_GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"


class GoogleCSEProvider(SearchProvider):
    name = "google_cse"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        cx: str | None = None,
        timeout: float = 12.0,
    ) -> None:
        self.api_key = api_key or settings.google_cse_api_key
        self.cx = cx or settings.google_cse_cx
        self.timeout = timeout

    async def available(self) -> bool:
        return bool(self.api_key and self.cx)

    async def close(self) -> None:
        pass

    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        """Search Google CSE for real product listings matching `query`."""
        if not await self.available() or not query.strip():
            return []

        clean_query = query.strip()
        offers: list[RawOffer] = []

        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": clean_query,
            "num": min(max_results, 10),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(_GOOGLE_CSE_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    offers = self._parse_items(data.get("items", []), clean_query)
                elif resp.status_code == 429:
                    log.warning("Google CSE API rate limited (429)")
                else:
                    log.warning("Google CSE API returned status %d: %s", resp.status_code, resp.text)
        except Exception as exc:
            log.warning("Google CSE search failed for %r: %s", query, exc)

        return offers

    def _parse_items(self, items: list[dict], original_query: str) -> list[RawOffer]:
        offers: list[RawOffer] = []

        for item in items:
            title = item.get("title") or original_query
            link = item.get("link")
            snippet = item.get("snippet", "")
            pagemap = item.get("pagemap", {})

            if not link:
                continue

            # Extract price & currency from pagemap metatags or snippet
            price_val: float | None = None
            currency = "USD"

            # Check metatags in pagemap
            metatags = pagemap.get("metatags", [{}])[0] if pagemap.get("metatags") else {}
            meta_price = metatags.get("og:price:amount") or metatags.get("product:price:amount")
            meta_currency = metatags.get("og:price:currency") or metatags.get("product:price:currency")

            if meta_price:
                try:
                    price_val = float(str(meta_price).replace(",", ""))
                except ValueError:
                    price_val = None
            if meta_currency:
                currency = str(meta_currency).upper()

            # Fallback snippet price parsing
            if price_val is None:
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

            # Domain / Seller
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', link)
            brand_name = domain_match.group(1).split(".")[0].title() if domain_match else "Retailer"

            offers.append(
                RawOffer(
                    provider="google_cse",
                    title=title,
                    url=link,
                    price_amount=price_val,
                    price_currency=currency,
                    availability="in_stock" if price_val is not None else "check_site",
                    data_source="google_cse",
                    brand=brand_name,
                    raw={"snippet": snippet, "pagemap": pagemap},
                )
            )

        return offers
