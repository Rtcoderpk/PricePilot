"""Review theme extraction from REAL review text.

Deterministic keyword/negation-based clustering. Never fabricates quotes:
themes and sentiment are derived from actual review strings, and any direct
quote we emit is taken verbatim from a real review row.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# theme → list of trigger substrings (lower-cased)
_THEME_POS = {
    "battery": ["battery", "batteries", "battery life"],
    "screen": ["screen", "display", "resolution", "panel"],
    "performance": ["fast", "quick", "speed", "smooth", "snappy", "responsive", "powerful"],
    "build quality": ["build", "solid", "premium", "sturdy", "durable", "well-made", "quality"],
    "price": ["great value", "worth it", "good price", "affordable", "cheap", "budget", "value for money"],
    "delivery": ["fast delivery", "on time", "quick shipping", "arrived on time", "well packaged"],
    "support": ["support", "warranty", "customer service", "helpful", "responsive support"],
    "sound": ["sound", "audio", "loud", "clear sound", "speakers"],
    "camera": ["camera", "photos", "picture quality", "sharp photos", "video quality"],
    "comfort": ["comfortable", "comfy", "soft", "fits well", "ergonomic"],
}

_THEME_NEG = {
    "battery": ["poor battery", "bad battery", "battery drains", "battery life is bad", "short battery", "battery died"],
    "screen": ["screen broke", "dead pixel", "screen cracked", "flickering", "bad screen", "dim screen"],
    "performance": ["slow", "lag", "lags", "freezes", "crashes", "stutters", "unresponsive"],
    "build quality": ["cheap build", "flimsy", "broke quickly", "fell apart", "poor quality", "cracked easily"],
    "delivery": ["late delivery", "damaged in delivery", "poor packaging", "arrived broken", "shipping was slow"],
    "support": ["no support", "bad warranty", "ignored", "unhelpful", "no response", "return rejected"],
    "reliability": ["stopped working", "died after", "faulty", "defective", "never worked"],
    "price": ["overpriced", "not worth it", "too expensive", "waste of money", "price went up"],
    "sound": ["tinny", "crackling", "no sound", "quiet", "bad audio"],
    "camera": ["blurry", "bad camera", "noisy photos", "poor picture quality", "camera is bad"],
}

# negation marker: "not good", "doesn't work", "no battery" flip polarity
_NEG_PREFIX = re.compile(r"\b(not|no|doesn'?t|didn'?t|isn'?t|won'?t|never|can'?t)\b")


@dataclass
class ThemeSummary:
    positives: list[str] = field(default_factory=list)
    negatives: list[str] = field(default_factory=list)
    common_complaints: list[str] = field(default_factory=list)
    common_strengths: list[str] = field(default_factory=list)
    sentiment_summary: str | None = None
    positive_count: int = 0
    negative_count: int = 0


def extract_themes(review_bodies: list[str], *, ratings: list[float | None] | None = None) -> ThemeSummary:
    """Extract structured themes from a batch of real review texts."""
    pos_hits: dict[str, int] = {}
    neg_hits: dict[str, int] = {}

    for idx, body in enumerate(review_bodies):
        text = (body or "").lower()
        if not text:
            continue
        # polarity via rating when available (>=4 positive, <=2 negative), else text
        rating = ratings[idx] if ratings and idx < len(ratings) else None

        # detect specific negative triggers first so a broad positive trigger for
        # the same theme (e.g. "camera") is not counted when complaints exist
        neg_in_text = {
            theme for theme, triggers in _THEME_NEG.items()
            if any(trig in text for trig in triggers) and not (rating is not None and rating >= 4)
        }

        for theme, triggers in _THEME_POS.items():
            if theme in neg_in_text:
                continue  # negative evidence for this theme outranks the broad positive word
            for trig in triggers:
                if trig in text and not _negated(text, trig):
                    pos_hits[theme] = pos_hits.get(theme, 0) + 1
                    break  # one hit per theme per review

        for theme in neg_in_text:
            neg_hits[theme] = neg_hits.get(theme, 0) + 1

    # Convert counts to aggregated themes (only themes seen in at least 1 review)
    positives = [t for t, c in pos_hits.items() if c > 0]
    negatives = [t for t, c in neg_hits.items() if c > 0]
    complaints = _ranked(neg_hits)
    strengths = _ranked(pos_hits)

    n_pos = sum(pos_hits.values())
    n_neg = sum(neg_hits.values())
    sentiment = None
    if n_pos + n_neg > 0:
        ratio = n_pos / (n_pos + n_neg)
        if ratio >= 0.65:
            sentiment = "Mostly positive"
        elif ratio <= 0.35:
            sentiment = "Mostly negative"
        else:
            sentiment = "Mixed"

    return ThemeSummary(
        positives=positives,
        negatives=negatives,
        common_complaints=complaints,
        common_strengths=strengths,
        sentiment_summary=sentiment,
        positive_count=n_pos,
        negative_count=n_neg,
    )


def _ranked(hits: dict[str, int]) -> list[str]:
    ordered = sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))
    return [theme for theme, count in ordered if count > 0]


def _negated(text: str, trigger: str) -> bool:
    """Heuristic: is `trigger` preceded by a negation within a short window?"""
    idx = text.find(trigger)
    if idx < 0:
        return False
    window = text[max(0, idx - 20):idx]
    return bool(_NEG_PREFIX.search(window))