"""Response agent — turns structured results into a clean user-facing response.

Never guesses; missing data is rendered as "Not available". Every result with a
URL is clickable. Used by the API to build the JSON the frontend renders.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pricepilot.logging import get_logger
from pricepilot.research.comparison_agent import (
    compare,
    position_categories,
)
from pricepilot.research.recommendation_agent import recommend
from pricepilot.research.verification_agent import verify_results

if TYPE_CHECKING:
    from pricepilot.models import Recommendation

log = get_logger("research.response_agent")


def build_response(results, *, query=None, quantity=None) -> dict:
    """Orchestrate verification → comparison → recommendation → response dict.

    Returns the full structured envelope consumed by the API route and frontend.
    """
    verifications = verify_results(results)
    options, currency_conflict = compare(
        results, verifications, quantity=quantity
    )
    options, reasoning = position_categories(options, currency_conflict=currency_conflict)
    rec = recommend(options, currency_conflict=currency_conflict, reasoning=reasoning)
    return {
        "query": query.model_dump(mode="json") if query else None,
        "product_understanding": query.model_dump(mode="json") if query else None,
        "suppliers": [r.model_dump(mode="json") for r in results],
        "verifications": [v.model_dump(mode="json") for v in verifications],
        "comparison": [o.model_dump(mode="json") for o in options],
        "recommendation": rec.model_dump(mode="json"),
        "currency_conflict": currency_conflict,
        "response_text": build_text(rec, options),
    }


def build_text(rec: Recommendation, options: list) -> str:
    lines: list[str] = ["Here are the strongest options I found."]
    sections = [
        ("BEST SUPPLIER", rec.best_supplier),
        ("CHEAPEST", rec.cheapest_option),
        ("BEST VALUE", rec.best_value),
    ]
    for label, opt in sections:
        if opt is None:
            lines.append(f"{label}: Not available")
            continue
        lines.append(
            f"{label}: Supplier: {opt.supplier or 'Not available'} | "
            f"Product: {opt.product or 'Not available'} | "
            f"Price: {_fmt_price(opt.unit_price, opt.currency)} | "
            f"MOQ: {opt.moq if opt.moq is not None else 'Not available'} | "
            f"Source: {opt.url or 'Not available'} | "
            f"Verification: {opt.verification}"
        )
    if rec.reasoning:
        lines.append("Why: " + " ".join(rec.reasoning))
    if rec.currency_conflict:
        lines.append(
            "Note: prices are shown in different currencies and were not directly compared."
        )
    return "\n".join(lines)


def _fmt_price(price, currency):
    if price is None:
        return "Not available"
    return f"{price} {currency or '?'}".strip()