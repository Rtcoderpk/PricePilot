"""Structured identification of a product candidate.

Extracts known identifiers (GTIN/EAN/UPC barcode, MPN, model number) from
provider data using an explicit priority: strong global identifiers first,
manufacturer numbers next, then inferred brand+model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pricepilot.normalization import normalize_model

# GTIN-8/12/13/14 (EAN/UPC) are pure digit strings of fixed length.
_GTIN_RE = re.compile(r"^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$")
_LENIENT_GTIN_RE = re.compile(r"^\d{6,14}$")


@dataclass
class ProductIdentifierSet:
    """Strong identifiers associated with a candidate."""

    gtin: str | None = None
    mpn: str | None = None
    brand: str | None = None
    model: str | None = None
    title: str = ""

    @property
    def has_strong(self) -> bool:
        return bool(self.gtin)

    @property
    def natural_key(self) -> str:
        """Prefer strong identifiers for natural identity keys."""
        if self.gtin:
            return f"gtin:{self.gtin}"
        if self.mpn:
            return f"mpn:{self.mpn}"
        return ""


def extract_identifiers(
    *,
    raw: dict,
    title: str,
    brand: str | None = None,
    model: str | None = None,
) -> ProductIdentifierSet:
    """Extract identifiers from a provider's raw result dict.

    `raw` may contain provider-specific keys (e.g. OFF `code`). Callers can run
    provider adapters' own extraction by passing already-populated fields.
    """
    gtin = _coerce_gtin(raw.get("code") or raw.get("gtin") or raw.get("barcode") or raw.get("ean"))
    mpn = _coerce_mpn(raw.get("mpn") or raw.get("manufacturer_part_number"))
    return ProductIdentifierSet(
        gtin=gtin,
        mpn=mpn,
        brand=normalize_model(brand) or None,
        model=normalize_model(model),
        title=title,
    )


def _coerce_gtin(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not _GTIN_RE.match(s):
        return None
    return s


def _coerce_mpn(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or len(s) > 32:
        return None
    return s.upper()