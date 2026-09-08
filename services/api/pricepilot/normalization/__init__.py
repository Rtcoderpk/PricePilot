"""Normalization utilities for product data.

Normalizes titles, brands, models, and variant attributes so that structurally
different strings ("Apple iPhone 17 Pro 256 GB Black" vs "iPhone 17 Pro 256GB -
Black") collapse into the same comparable representation WITHOUT destroying
meaningful variant information (storage, RAM, color, quantity/pack size, ...).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Units we understand in quantity strings. Values are normalized to a canonical
# base token with a numeric factor so "1 kg" == "1000 g" is *not* wrongly
# assumed equal, but "1 kg" vs "1 L" is distinguishable.
_QUANTITY_RE = re.compile(
    r"^(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|cl|l|oz|fl oz|lb|gb|tb|mb|kb)?$",
    re.IGNORECASE,
)
_WEIGHT_G = {"kg": 1000.0, "g": 1.0, "lb": 453.592, "oz": 28.3495}
_VOLUME_ML = {"l": 1000.0, "ml": 1.0, "cl": 10.0, "fl oz": 29.5735}
_STORAGE = {"gb": 1, "tb": 1024, "mb": 1 / 1024, "kb": 1 / 1048576}

_WORD_SPLIT = re.compile(r"[\s\-_/]+")
# Also split digit/unit boundaries so "256GB" == "256 GB" == "256 gb",
# including decimals: "1.5L" -> "1.5 l".
_UNIT_SPLIT = re.compile(r"(\d+(?:\.\d+)?)(?=[a-z])", re.IGNORECASE)
_STRIP_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
# Glue words that carry no identity information in titles.
_STOPWORDS = {
    "a", "an", "the", "of", "with", "for", "and", "in", "on", "by",
    "plus", "new", "official", "original", "genuine",
}


class NormalizeError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedQuantity:
    raw: str
    kind: str  # "weight" | "volume" | "storage" | "count" | None
    value: float
    unit: str  # canonical size token, e.g. "1 kg", "250 ml"


@dataclass
class ProductAttributes:
    """Extracted, normalized product attribute bag used for matching."""

    title: str = ""
    brand: str | None = None
    model: str | None = None
    quantity: NormalizedQuantity | None = None
    storage_gb: float | None = None       # RAM or disk in GB where unambiguous
    color: str | None = None
    condition: str | None = None
    extras: dict[str, str] = field(default_factory=dict)

    @property
    def variant_key(self) -> tuple | None:
        """Deterministic key capturing only attributes that split variants.

        Returns None when no variant attribute is present. Two products with
        the same variant_key are considered the same *variant* (same storage,
        same quantity, same color, ...). A differing value → different variant.
        """
        parts: list = []
        if self.storage_gb is not None:
            parts.append(("storage_gb", self.storage_gb))
        if self.quantity is not None:
            parts.append(("quantity", f"{self.quantity.kind}:{self.quantity.value}:{self.quantity.unit}"))
        if self.color:
            parts.append(("color", self.color))
        return tuple(parts) if parts else None


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/whitespace, drop stopwords, sort tokens.

    Keeps meaningful words, so "iPhone 17 Pro 256GB Black" and
    "iPhone 17 Pro 256GB - Black" normalize identically.
    """
    s = unicodedata.normalize("NFKC", title or "").lower()
    s = _STRIP_PUNCT.sub(" ", s)
    s = _UNIT_SPLIT.sub(r"\1 ", s)  # "256gb" -> "256 gb"
    tokens = [w for w in _WORD_SPLIT.split(s) if w and w not in _STOPWORDS]
    return " ".join(sorted(tokens))


def normalize_brand(brand: str | None) -> str | None:
    if not brand:
        return None
    return _normalize_word(brand)


def normalize_model(model: str | None) -> str | None:
    if not model:
        return None
    s = _STRIP_PUNCT.sub(" ", model.lower())
    return " ".join(_WORD_SPLIT.split(s)).strip().lower() or None


def _normalize_word(value: str) -> str:
    s = unicodedata.normalize("NFKC", value or "").lower()
    return " ".join(_WORD_SPLIT.split(_STRIP_PUNCT.sub(" ", s))).strip() or None


def parse_quantity(text: str | None) -> NormalizedQuantity | None:
    """Parse a quantity/pack-size string into a comparable normalized form.

    Treats only unit-bounded forms as meaningful; returns None for free text.
    """
    if not text:
        return None
    m = _QUANTITY_RE.match(text.strip())
    if not m:
        return None
    value = float(m.group("value").replace(",", "."))
    unit = (m.group("unit") or "").lower()

    kind, canonical = None, None
    if unit in _WEIGHT_G:
        kind, canonical = "weight", value * _WEIGHT_G[unit]
        unit_label = f"{value:g} {unit}"
    elif unit in _VOLUME_ML:
        kind, canonical = "volume", value * _VOLUME_ML[unit]
        unit_label = f"{value:g} {unit}"
    elif unit in _STORAGE:
        kind, canonical = "storage", value * _STORAGE[unit]
        unit_label = f"{value:g} {unit}"
    else:
        # A bare number (e.g. "12") with no unit → a count of something; keep
        # it but mark as "count" only if it looks like a pack count.
        kind, canonical, unit_label = "count", value, f"{value:g}"

    return NormalizedQuantity(raw=text.strip(), kind=kind, value=canonical, unit=unit_label)


def parse_storage_gb(text: str | None) -> float | None:
    """Extract a GB value for RAM/disk tokens like "16GB", "512GB", "1TB"."""
    if not text:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(gb|tb)", text.lower())
    if not m:
        return None
    return float(m.group(1).replace(",", ".")) * _STORAGE[m.group(2)]


def extract_color(text: str | None) -> str | None:
    if not text:
        return None
    found = re.findall(r"\b(black|white|silver|gold|blue|red|green|graphite|space black|midnight|starlight|rose)\b", text.lower())
    return _normalize_word(",".join(found)) if found else None


def fnv1a(text: str) -> str:
    """Deterministic non-cryptographic hash for candidate-group keys."""
    h = 2166136261
    for byte in text.encode("utf-8"):
        h ^= byte
        h = (h * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"