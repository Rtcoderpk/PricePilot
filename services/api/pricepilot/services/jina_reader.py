"""Jina Reader Service with SSRF Protection.

Fetches live webpage contents for candidate product URLs using Jina Reader API (`https://r.jina.ai/{url}`).
Extracts structured product evidence (price, stock, MOQ, specifications, seller information).
Strictly enforces SSRF security rules — blocks private IP ranges and internal hostnames.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.parse
from datetime import UTC, datetime
import httpx

from pricepilot.config import settings
from pricepilot.logging import get_logger

log = get_logger("services.jina_reader")

_JINA_READER_BASE = "https://r.jina.ai/"

# Private / reserved IP networks blocked for SSRF protection
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def is_url_safe(target_url: str) -> bool:
    """Validate that `target_url` is a public HTTP/HTTPS URL and not an SSRF attempt."""
    if not target_url or not isinstance(target_url, str):
        return False

    parsed = urllib.parse.urlparse(target_url.strip())
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    hostname_lower = hostname.lower()
    if hostname_lower in ("localhost", "loopback") or hostname_lower.endswith(".local") or hostname_lower.endswith(".internal"):
        return False

    # Resolve IP address and check against blocked private networks
    try:
        ip_addr = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip_addr)
        for net in _BLOCKED_NETWORKS:
            if ip_obj in net:
                log.warning("SSRF blocked: %s resolves to private IP %s", target_url, ip_addr)
                return False
    except socket.error:
        # If hostname resolution fails, do not allow unsafe request
        log.warning("SSRF blocked: could not resolve hostname %s", hostname)
        return False

    return True


async def read_live_page(target_url: str, *, timeout: float = 12.0) -> dict:
    """Read a live webpage using Jina Reader API and return extracted evidence.

    Returns dict with fields:
      - status: "success" | "inaccessible" | "blocked"
      - target_url: str
      - title: str | None
      - price: float | None
      - currency: str
      - stock: str | None
      - price_evidence: str | None
      - checked_at: str
      - content: str
    """
    checked_at = datetime.now(UTC).isoformat()

    if not is_url_safe(target_url):
        return {
            "status": "inaccessible",
            "reason": "URL failed SSRF validation check",
            "target_url": target_url,
            "checked_at": checked_at,
        }

    jina_url = f"{_JINA_READER_BASE}{target_url}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "PricePilot-Agent/1.0",
    }
    if settings.jina_api_key:
        headers["Authorization"] = f"Bearer {settings.jina_api_key}"

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(jina_url, headers=headers)
            if resp.status_code == 200:
                raw_text = resp.text
                evidence = _parse_jina_content(raw_text, target_url, checked_at)
                evidence["status"] = "success"
                return evidence
            elif resp.status_code in (401, 403, 429, 503):
                return {
                    "status": "inaccessible",
                    "reason": f"Page access blocked or rate limited (HTTP {resp.status_code})",
                    "target_url": target_url,
                    "checked_at": checked_at,
                }
            else:
                return {
                    "status": "inaccessible",
                    "reason": f"Unexpected status {resp.status_code}",
                    "target_url": target_url,
                    "checked_at": checked_at,
                }
    except Exception as exc:
        log.warning("Jina page reader failed for %s: %s", target_url, exc)
        return {
            "status": "inaccessible",
            "reason": str(exc),
            "target_url": target_url,
            "checked_at": checked_at,
        }


def _parse_jina_content(text: str, target_url: str, checked_at: str) -> dict:
    title: str | None = None
    title_match = re.search(r"Title:\s*(.*?)\n", text, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()

    price_val: float | None = None
    currency = "USD"
    price_evidence: str | None = None

    price_match = re.search(r"(\$|USD\s*|€|£)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{2})?)", text)
    if price_match:
        symbol, num_str = price_match.group(1), price_match.group(2)
        if symbol == "€":
            currency = "EUR"
        elif symbol == "£":
            currency = "GBP"
        try:
            price_val = float(num_str.replace(",", ""))
            start_idx = max(0, price_match.start() - 30)
            end_idx = min(len(text), price_match.end() + 50)
            price_evidence = text[start_idx:end_idx].replace("\n", " ").strip()
        except ValueError:
            price_val = None

    stock = "unknown"
    lower_text = text.lower()
    if "in stock" in lower_text or "available" in lower_text:
        stock = "in_stock"
    elif "out of stock" in lower_text or "sold out" in lower_text:
        stock = "out_of_stock"

    return {
        "target_url": target_url,
        "title": title,
        "price": price_val,
        "currency": currency,
        "price_evidence": price_evidence,
        "stock": stock,
        "checked_at": checked_at,
        "content_excerpt": text[:500],
    }
