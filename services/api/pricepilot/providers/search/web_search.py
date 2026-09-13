"""Web Product Search Provider.

Searches public search engines / product APIs for real live product listings across
any physical product category (electronics, GPUs, laptops, clothing, tools, appliances, etc.).
"""

from __future__ import annotations

import re
import urllib.parse
import httpx

from pricepilot.errors import ProviderError
from pricepilot.logging import get_logger
from pricepilot.models import ProductIdentifierRef, RawOffer
from pricepilot.providers.search import SearchProvider

log = get_logger("providers.search.web")


class WebSearchProvider(SearchProvider):
    name = "web_search"

    def __init__(
        self,
        *,
        timeout: float = 12.0,
        api_key: str | None = None,
        search_engine_url: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.api_key = api_key
        self.search_engine_url = search_engine_url or "https://html.duckduckgo.com/html/"

    async def available(self) -> bool:
        return True

    async def close(self) -> None:
        pass

    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        """Fetch real product web results matching `query`."""
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        offers: list[RawOffer] = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                resp = await client.post(
                    self.search_engine_url,
                    data={"q": clean_query + " buy price store"},
                )
                if resp.status_code == 200:
                    offers = self._parse_html_results(resp.text, clean_query, max_results)
        except Exception as exc:
            log.warning("web search failed for %r: %s", query, exc)

        return offers

    def _parse_html_results(self, html: str, original_query: str, max_results: int) -> list[RawOffer]:
        offers: list[RawOffer] = []
        # Find links and snippets in DDG HTML structure
        matches = re.findall(
            r'<a class="result__url" href="([^"]+)".*?>\s*(.*?)\s*</a>.*?<a class="result__snippet".*?>(.*?)</a>',
            html,
            re.DOTALL | re.IGNORECASE,
        )

        for raw_url, display_url, snippet in matches:
            if len(offers) >= max_results:
                break
            clean_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            clean_display = re.sub(r"<[^>]+>", "", display_url).strip()

            # Resolve actual destination URL from DDG redirect link if present
            url = clean_display
            if "uddg=" in raw_url:
                parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                if "uddg" in parsed_q:
                    url = parsed_q["uddg"][0]
            elif raw_url.startswith("http"):
                url = raw_url

            # Extract price if available in snippet (e.g., $999.99 or USD 500)
            price_match = re.search(r'(\$|USD\s*|€|£)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)', clean_snippet)
            price_val: float | None = None
            currency = "USD"
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

            # Extract merchant/domain name
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            merchant = domain_match.group(1) if domain_match else "Web Retailer"

            # Create offer title from snippet & query
            title = original_query.title()
            if len(clean_snippet) > 20:
                title_part = clean_snippet.split(".")[0]
                if len(title_part) < 80:
                    title = f"{original_query.title()} - {title_part}"

            offers.append(
                RawOffer(
                    provider="web_search",
                    title=title,
                    url=url if url.startswith("http") else f"https://{url}",
                    price_amount=price_val,
                    price_currency=currency,
                    availability="in_stock" if price_val is not None else "check_site",
                    data_source="web_search",
                    brand=merchant.split(".")[0].title(),
                    raw={"snippet": clean_snippet, "display_url": clean_display},
                )
            )

        return offers
