"""Product Matching Agent.

Compares candidate products against the requested canonical product query.
Computes match status: `exact`, `high_confidence`, `partial`, `alternative`, `not_match`.
Prevents comparing non-matching products (e.g. iPhone 15 128GB vs 256GB).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

MatchStatus = Literal["exact", "high_confidence", "partial", "alternative", "not_match", "unknown"]


@dataclass
class MatchResult:
    status: MatchStatus
    score: float  # 0.0 to 1.0
    reason: str


def match_product(query_title: str | None, offer_title: str | None, *, brand: str | None = None, model: str | None = None) -> MatchResult:
    """Compare query product identity against retrieved offer product title."""
    if not query_title or not offer_title:
        return MatchResult("unknown", 0.5, "Missing title details")

    q_lower = query_title.lower()
    o_lower = offer_title.lower()

    # Exact title match
    if q_lower == o_lower:
        return MatchResult("exact", 1.0, "Exact title match")

    score = 0.0
    tokens = [t for t in re.split(r"\W+", q_lower) if len(t) > 2]
    if not tokens:
        return MatchResult("partial", 0.6, "Partial keyword match")

    matched_tokens = [t for t in tokens if t in o_lower]
    ratio = len(matched_tokens) / len(tokens)

    # Brand check
    if brand and brand.lower() not in o_lower and brand.lower() in q_lower:
        return MatchResult("not_match", 0.2, "Brand mismatch")

    # Spec mismatch check (e.g., 128gb vs 256gb)
    q_specs = set(re.findall(r"\b\d+(?:gb|tb|mb|hz)\b", q_lower))
    o_specs = set(re.findall(r"\b\d+(?:gb|tb|mb|hz)\b", o_lower))
    if q_specs and o_specs and not q_specs.intersection(o_specs):
        return MatchResult("alternative", 0.4, "Specification mismatch (variant/alternative)")

    if ratio >= 0.9:
        return MatchResult("exact", 0.95, "High token match")
    elif ratio >= 0.7:
        return MatchResult("high_confidence", 0.8, "Strong title match")
    elif ratio >= 0.4:
        return MatchResult("partial", 0.6, "Partial spec/brand match")
    else:
        return MatchResult("not_match", 0.3, "Low relevance match")
