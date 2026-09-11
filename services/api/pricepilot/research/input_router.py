"""Input router — normalize image / voice / text into one ProductQuery.

- IMAGE: Gemini vision → structured ProductImageExtraction → ProductQuery
- VOICE: STT already produced text in the frontend → treated as TEXT here
- TEXT: parsed deterministically (and via Gemini only to improve understanding)

Only fields the input actually contained are set; nothing is invented. Missing
critical info is recorded so the UI can ask a clarifying question.
"""

from __future__ import annotations

import logging
import re

from pricepilot.models import ProductImageExtraction, ProductQuery
from pricepilot.research.image import extract_product_from_image

log = logging.getLogger("pricepilot.research.input_router")

# Currency symbols → 3-letter codes (deterministic).
_CURRENCY_HINTS = {
    "$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD",
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "£": "GBP", "gbp": "GBP", "pound": "GBP",
    "₹": "INR", "inr": "INR", "rupee": "INR",
}

# Terms signalling wholesale / reseller intent.
_WHOLESALE_HINTS = ("wholesale", "wholesaler", "bulk", "supplier", "suppliers", "moq", "minimum order")
_RETAIL_HINTS = ("retail", "store", "shop", "buy one", "single")

_QUANTITY_RE = re.compile(r"\b(\d{2,6})\b")


def route_text(text: str, *, use_gemini: bool = False) -> ProductQuery:
    """Build a ProductQuery from typed text (also used for voice-transcribed text).

    Deterministic extraction covers the common cases; `use_gemini` may be set in
    the future to refine, but the fallback must always return usable structured
    data without a network/AI call.
    """
    cleaned = (text or "").strip()
    lower = cleaned.lower()
    missing: list[str] = []
    if not cleaned:
        return ProductQuery(confidence=0.0, missing_information=["request"])

    # quantity
    quantity = None
    m = re.search(r"(\d{2,6})\s*(?:units|pcs|pieces|pairs|packs?)", lower)
    if not m:
        m = _QUANTITY_RE.search(lower)
    if m:
        try:
            q = int(m.group(1))
            if 1 <= q <= 100000:
                quantity = q
        except ValueError:
            q = None

    # budget + currency
    budget = None
    currency = None
    for sym, code in _CURRENCY_HINTS.items():
        if sym in cleaned:
            currency = code
            break
    if currency and "$" in cleaned:
        m = re.search(r"\$\s*(\d+(?:\.\d+)?)", cleaned)
        if m:
            budget = float(m.group(1))

    # wholesale vs retail
    wholesale = any(h in lower for h in _WHOLESALE_HINTS)
    if not wholesale:
        retail = any(h in lower for h in _RETAIL_HINTS)
        wholesale = not retail

    # category/brand best-effort tokens
    category = None
    brand = None
    for tok in ("shoes", "running shoes", "phone", "laptop", "tv", "tshirt", "t-shirt", "bottle"):
        if tok in lower:
            category = tok
            break
    for b in ("nike", "adidas", "samsumg", "apple", "xiaomi", "samsung"):
        if b.lower() in lower:
            brand = b
            break

    # search queries
    search_queries: list[str] = []
    if brand:
        search_queries.append(f"{brand} {category or ''}".strip())
        if wholesale:
            search_queries.append(f"{brand} {category or ''} wholesale".strip())
        if quantity:
            search_queries.append(f"{brand} {category or ''} {quantity}".strip())
    elif category:
        search_queries.append(category)
        if wholesale:
            search_queries.append(f"{category} wholesale".strip())
            search_queries.append(f"{category} supplier".strip())
    if not search_queries:
        search_queries.append(cleaned)

    if not category and not brand:
        missing.append("product_type")
    if quantity is None:
        missing.append("quantity")

    return ProductQuery(
        category=category,
        product_name=cleaned,
        brand=brand,
        quantity=quantity,
        wholesale_required=wholesale,
        budget=budget,
        search_queries=search_queries,
        confidence=0.6,
        missing_information=missing,
    )


async def route_text_with_gemini(text: str, provider) -> ProductQuery:
    """Optional Gemini refinement. Falls back to deterministic on any failure."""
    try:
        from pricepilot.research.text import refine_with_gemini

        return await refine_with_gemini(text, provider)
    except Exception:
        log.warning("gemini text refinement failed; using deterministic route", exc_info=True)
        return route_text(text)


async def route_image(image_bytes: bytes, mime_type: str, *, vision_required: bool) -> tuple[ProductImageExtraction, str]:
    """IMAGE input. Returns (extraction, notice). If Gemini vision is not
    configured or fails, returns an empty extraction + honest notice."""
    return await extract_product_from_image(image_bytes, mime_type, vision_required=vision_required)


def extraction_to_query(extraction: ProductImageExtraction, raw_text: str | None = None) -> ProductQuery:
    """Convert a vision extraction into a ProductQuery."""
    queries = list(extraction.search_terms)
    if raw_text:
        q = route_text(raw_text, use_gemini=False)
        if q.search_queries:
            queries = queries + [sq for sq in q.search_queries if sq not in queries]
    if not queries:
        base = " ".join(x for x in (extraction.brand, extraction.product_name, extraction.category) if x)
        if base:
            queries = [base]
    missing: list[str] = []
    if not extraction.category and not extraction.product_name:
        missing.append("product_type")
    return ProductQuery(
        category=extraction.category,
        product_name=extraction.product_name,
        brand=extraction.brand,
        model=extraction.model,
        sku=extraction.sku,
        attributes=extraction.attributes,
        quantity=extraction.quantity,
        search_queries=queries,
        confidence=extraction.confidence,
        missing_information=missing,
    )