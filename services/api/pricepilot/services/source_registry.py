"""Configurable Source Registry.

Classifies domains into Source Tiers (Tier 1–5), trust levels, and category intent.
Prevents unverified independent websites from pretending to be established marketplaces.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Literal

SourceType = Literal["retail", "wholesale", "manufacturer", "marketplace", "unknown"]
TrustLevel = Literal["tier1_established", "tier2_wholesale", "tier3_retailer", "tier4_independent", "tier5_manufacturer", "unverified"]


@dataclass
class SourceProfile:
    domain: str
    tier: int  # 1 to 5
    source_type: SourceType
    trust_level: TrustLevel
    priority: int
    country: str = "US"


_REGISTRY_DOMAINS: dict[str, SourceProfile] = {
    "amazon.com": SourceProfile("amazon.com", 1, "marketplace", "tier1_established", 100),
    "ebay.com": SourceProfile("ebay.com", 1, "marketplace", "tier1_established", 90),
    "walmart.com": SourceProfile("walmart.com", 1, "marketplace", "tier1_established", 85),
    "aliexpress.com": SourceProfile("aliexpress.com", 1, "marketplace", "tier1_established", 80),
    "alibaba.com": SourceProfile("alibaba.com", 2, "wholesale", "tier2_wholesale", 95),
    "globalsources.com": SourceProfile("globalsources.com", 2, "wholesale", "tier2_wholesale", 90),
    "thomasnet.com": SourceProfile("thomasnet.com", 2, "wholesale", "tier2_wholesale", 85),
    "target.com": SourceProfile("target.com", 3, "retail", "tier3_retailer", 80),
    "bestbuy.com": SourceProfile("bestbuy.com", 3, "retail", "tier3_retailer", 80),
    "apple.com": SourceProfile("apple.com", 5, "manufacturer", "tier5_manufacturer", 95),
    "nike.com": SourceProfile("nike.com", 5, "manufacturer", "tier5_manufacturer", 95),
    "asus.com": SourceProfile("asus.com", 5, "manufacturer", "tier5_manufacturer", 95),
}


def lookup_source(url: str) -> SourceProfile:
    """Look up domain profile in Source Registry; defaults to Tier 4 Independent."""
    if not url:
        return SourceProfile("unknown", 4, "unknown", "unverified", 10)

    try:
        parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
    except Exception:
        host = "unknown"

    if host in _REGISTRY_DOMAINS:
        return _REGISTRY_DOMAINS[host]

    # Check for domain suffix matches
    for domain, profile in _REGISTRY_DOMAINS.items():
        if host.endswith(f".{domain}"):
            return profile

    return SourceProfile(host or "unknown", 4, "retail", "tier4_independent", 30)
