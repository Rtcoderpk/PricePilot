"""Wholesale & B2B Supplier Search Provider.

Searches wholesale platforms, B2B directories, and supplier databases for bulk products,
minimum order quantities (MOQ), and manufacturer listings.
"""

from __future__ import annotations

import re
import urllib.parse
import httpx

from pricepilot.logging import get_logger
from pricepilot.models import RawOffer
from pricepilot.providers.search import SearchProvider

log = get_logger("providers.search.wholesale")


class WholesaleSupplierProvider(SearchProvider):
    name = "wholesale_supplier"

    def __init__(
        self,
        *,
        timeout: float = 12.0,
    ) -> None:
        self.timeout = timeout
        self.search_url = "https://html.duckduckgo.com/html/"

    async def available(self) -> bool:
        return True

    async def close(self) -> None:
        pass

    async def search(self, query: str, *, max_results: int = 20) -> list[RawOffer]:
        """Search wholesale and supplier sources matching `query`."""
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
                    self.search_url,
                    data={"q": clean_query + " wholesale supplier manufacturer B2B MOQ"},
                )
                if resp.status_code == 200:
                    offers = self._parse_wholesale_results(resp.text, clean_query, max_results)
        except Exception as exc:
            log.warning("wholesale search failed for %r: %s", query, exc)

        return offers

    def _parse_wholesale_results(self, html: str, original_query: str, max_results: int) -> list[RawOffer]:
        offers: list[RawOffer] = []
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

            url = clean_display
            if "uddg=" in raw_url:
                parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(raw_url).query)
                if "uddg" in parsed_q:
                    url = parsed_q["uddg"][0]
            elif raw_url.startswith("http"):
                url = raw_url

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

            # Extract supplier/domain name
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            supplier_domain = domain_match.group(1) if domain_match else "Global Supplier"
            supplier_name = supplier_domain.split(".")[0].replace("-", " ").title() + " Wholesale"

            offers.append(
                RawOffer(
                    provider="wholesale_supplier",
                    title=f"{original_query.title()} (Wholesale Supplier)",
                    url=url if url.startswith("http") else f"https://{url}",
                    price_amount=price_val,
                    price_currency=currency,
                    availability="in_stock",
                    data_source="wholesale_supplier",
                    brand=supplier_name,
                    raw={"snippet": clean_snippet, "supplier_domain": supplier_domain},
                )
            )

        return offers
