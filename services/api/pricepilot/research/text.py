"""Optional Gemini refinement of free-text product requests.

Converts typed/voice text into a strict ProductQuery when a Gemini provider is
available; otherwise callers fall back to the deterministic parser. Never
invents fields the user did not mention.
"""

from __future__ import annotations

from pricepilot.logging import get_logger
from pricepilot.models import ProductQuery

log = get_logger("research.text")


async def refine_with_gemini(text: str, provider) -> ProductQuery:
    """Ask Gemini for a structured ProductQuery from `text`.

    Only used to improve understanding; the model output is schema-validated and
    any factual gap stays null. Raises on failure so callers can fall back.
    """
    prompt = (
        "Convert the user's product request into strict JSON matching this schema: "
        "category, product_name, brand, model, sku, attributes (object), quantity, "
        "wholesale_required (bool), budget, destination, search_queries (array of "
        "2-3 supplier/product search queries), confidence (0..1), missing_information "
        "(array). Only include information the user explicitly provided. Never invent "
        "brands, prices, suppliers, or specs. Return ONLY valid JSON.\n\n"
        f"User request: {text}"
    )
    from pricepilot.providers.ai.gemini import _ProductUnderstandingSchema

    out = await provider.generate_structured(prompt, _ProductUnderstandingSchema)
    data = out.model_dump(exclude_unset=True)
    # search queries fallback
    queries = data.get("search_queries") or []
    if not queries:
        base = " ".join(x for x in (data.get("brand"), data.get("category"), data.get("product_name")) if x)
        queries = [base] if base else [text.strip()]
    data["search_queries"] = queries
    return ProductQuery.model_validate(data)