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

    # quantity — parse only when explicit quantity context/keywords exist
    quantity = None
    m = re.search(r"\b(\d{1,6})\s*(?:units|pcs|pieces|pairs|packs?|items?|qty|quantity)\b", lower)
    if not m:
        m = re.search(r"\b(?:qty|quantity|count|buy|order|need)\s*(?:of\s*)?(\d{1,6})\b", lower)
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

    # intelligent cross-mode intent detection (Section 8)
    wholesale = any(h in lower for h in _WHOLESALE_HINTS)
    if quantity and quantity >= 10:
        wholesale = True
    elif not wholesale:
        retail = any(h in lower for h in _RETAIL_HINTS)
        if retail:
            wholesale = False

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

    # multi-query search planner strategy (Section 7)
    base_phrase = f"{brand or ''} {category or cleaned}".strip()
    search_queries: list[str] = [
        base_phrase,  # Primary
        f"{base_phrase} buy price store".strip(),  # Retail
        f"{base_phrase} wholesale supplier B2B".strip(),  # Wholesale
        f"{base_phrase} official manufacturer".strip(),  # Manufacturer
    ]
    if "pakistan" in lower or "pk" in lower:
        search_queries.append(f"{base_phrase} Pakistan".strip())

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