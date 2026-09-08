"""Deterministic chat refinement parser.

Recognizes common shopping follow-ups WITHOUT needing an LLM:
  - "only <brand>"          → brand allowlist
  - "not <brand>" / "no <brand>" → brand exclusion
  - "cheaper"               → re-rank by lowest price (price tightener)
  - "under <N>"             → budget override (hard constraint)
  - "ignore refurbished" / "no refurbished" / "new only" → condition filter
  - "best rated" / "top rated" → rank preference
  - "more results" / "show more" → ask for more candidates
Anything unrecognized passes through unchanged (the graph still runs; the chat
summary node may note it).

Every recognized refinement is surfaced as a structured `ChatRefinement` so the
caller can show the user what was understood (no silent behavior).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_BRAND_KNOWN = {
    "samsung", "apple", "iphone", "lg", "sony", "lenovo", "dell", "hp",
    "asus", "acer", "xiaomi", "oneplus", "google", "nokia", "motorola",
    "nike", "adidas", "sidi", "perly", "ferrero", "nestle", "nutella", "acme",
}


@dataclass
class ChatRefinement:
    query: str
    kind: str  # "brand_allow" | "brand_block" | "cheaper" | "budget" | "condition" | "rank" | "more" | "pass"
    value: str | None = None
    applied: bool = True
    note: str | None = None
    recognized_tokens: list[str] = field(default_factory=list)


def parse_refinement(query: str) -> ChatRefinement:
    q = query.lower().strip()
    tokens = q.split()
    recognized: list[str] = []

    # brand allow
    m_allow = re.search(r"\bonly\s+(.+)$", q)
    if m_allow:
        brand = _extract_brand(m_allow.group(1))
        if brand:
            recognized.append("only")
            return ChatRefinement(query, "brand_allow", brand, recognized_tokens=recognized,
                                  note=f"Will prefer {brand}.")

    # brand block: "not samsung" / "no samsung"
    m_block = re.search(r"\b(?:not|no|exclude|without)\s+([a-z ]+)", q)
    if m_block:
        brand = _extract_brand(m_block.group(1))
        if brand:
            recognized.append("brand_block")
            return ChatRefinement(query, "brand_block", brand, recognized_tokens=recognized,
                                  note=f"Will exclude {brand}.")

    # cheaper
    if any(w in tokens for w in ("cheaper", "cheapest", "lower price", "less expensive")):
        recognized.append("cheaper")
        return ChatRefinement(query, "cheaper", recognized_tokens=recognized,
                              note="Will prioritize lower prices.")

    # budget: under N
    m_budget = re.search(r"\bunder\s+([\d,]+(?:\.\d+)?)\b", q)
    if m_budget:
        recognized.append("budget")
        try:
            amount = float(m_budget.group(1).replace(",", ""))
        except ValueError:
            amount = 0.0
        return ChatRefinement(query, "budget", value=str(amount), recognized_tokens=recognized,
                              note=f"Hard budget set to {amount:g}.")

    # condition
    if any(w in tokens for w in ("refurbished", "used", "second-hand", "open box")):
        # "ignore/no refurbished" → exclude refurbished
        negated = any(w in tokens for w in ("ignore", "no", "not", "without", "avoid"))
        recognized.append("condition")
        if negated:
            return ChatRefinement(query, "condition", value="exclude_refurbished",
                                  recognized_tokens=recognized,
                                  note="Will exclude refurbished items.")
        return ChatRefinement(query, "condition", value="exclude_refurbished" if negated else "forbid_used",
                              recognized_tokens=recognized, note="Condition preference applied.")
    if "new only" in q or "only new" in q:
        recognized.append("condition")
        return ChatRefinement(query, "condition", value="new_only", recognized_tokens=recognized,
                              note="Only new items.")

    # rank
    if any(w in tokens for w in ("best rated", "top rated", "highest rated")):
        recognized.append("rank")
        return ChatRefinement(query, "rank", value="highest_rated", recognized_tokens=recognized,
                              note="Ranking by rating.")

    # more results
    if any(w in tokens for w in ("more", "show more", "others", "other options", "next")):
        recognized.append("more")
        return ChatRefinement(query, "more", recognized_tokens=recognized,
                              note="Fetching more options.")

    return ChatRefinement(query, "pass", applied=False, note="No refinement detected — running a fresh search.")


def _extract_brand(text: str) -> str | None:
    """Pick the first known brand token from a phrase (best-effort)."""
    for b in sorted(_BRAND_KNOWN, key=len, reverse=True):
        if b in text:
            return "" + b.capitalize()
    # fall back to first meaningful word
    for w in text.split():
        if w.isalnum() and len(w) > 2:
            return w.capitalize()
    return None