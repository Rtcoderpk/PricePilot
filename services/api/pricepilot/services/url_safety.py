"""SSRF boundary validator (Phase 7).

PricePilot does not currently fetch user-supplied URLs — outer providers build
requests to server-fixed origins. This module is the *required boundary* any
future code that takes a user-controlled URL must pass every request through,
so we never regress into allowing requests to internal infrastructure.

Rules enforced:
- scheme must be https (or http for explicitly-authorized public hosts only);
- hostname must resolve to PUBLIC, non-private addresses — loopback, link-local,
  CGNAT, reserved/metadata ranges are rejected;
- no hostname-only/port-only tricks (resolved via a small IP allow-check);
- no localhost aliases, decimal/IPv6 literals pointing inward.

The check is synchronous and dependency-light: it uses only stdlib. A real
fetch path should call `assert_public_https(url)` before issuing the request.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

from pricepilot.errors import ErrorCode, PricePilotError


class UnsafeUrlError(PricePilotError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message, status_code=400)


# Private / reserved ranges that must never be requested from server code.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("192.0.0.0/24"),  # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),  # TEST-NET
    ipaddress.ip_network("198.18.0.0/15"),  # benchmarking
    ipaddress.ip_network("198.51.100.0/24"),  # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),  # multicast
    ipaddress.ip_network("240.0.0.0/4"),  # reserved
    ipaddress.ip_network("255.255.255.255/32"),
    ipaddress.ip_network("::/128"),  # unspecified
    ipaddress.ip_network("::1/128"),  # loopback
    ipaddress.ip_network("fc00::/7"),  # unique local
    ipaddress.ip_network("fe80::/10"),  # link-local
    ipaddress.ip_network("ff00::/8"),  # multicast
]

# e.g. http, ftp, file, data, gopher, dict — anything not https.
_ALLOWED_SCHEMES = {"https"}
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$")


def _blocked(host: str) -> bool:
    """True if the host is an IP literal that maps into a private/reserved net."""
    host = host.strip().lower().rstrip(".").lstrip(".")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False  # not an IP literal → hostname, resolve at fetch time
    return any(addr in net for net in _BLOCKED_NETWORKS)


def assert_public_https(url: str, *, allow_http_hosts: frozenset[str] | None = None) -> None:
    """Reject any URL that is not an https URL to a public host.

    Raises UnsafeUrlError (a 400 validation error) when unsafe. This is the
    single choke point for any future user-URL fetch.
    """
    if not url or len(url) > 2048:
        raise UnsafeUrlError("URL is missing or too long.")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        # Optionally permit http for an explicit allow-list of public hosts.
        if allow_http_hosts and scheme == "http" and (parsed.hostname or "").lower() in allow_http_hosts:
            pass
        else:
            raise UnsafeUrlError("Only https URLs are allowed.")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no host.")
    if not _HOSTNAME_RE.match(host):
        raise UnsafeUrlError("URL host is malformed.")
    if _blocked(host):
        raise UnsafeUrlError("URL points to a private/reserved address.")


def assert_public_resolution(host: str) -> None:
    """Verify the hostname's DNS resolution contains no private/reserved IPs.

    Use this (in addition to `assert_public_https`) right before issuing a
    request to a hostname, as a DNS-rebinding and SSRF guard. Calls may block on
    DNS; callers run it in a threadpool if needed.
    """
    bare = host.strip().lower().rstrip(".")
    if _blocked(bare):
        raise UnsafeUrlError("URL resolves to a private/reserved address.")
    try:
        infos = socket.getaddrinfo(bare, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
    except OSError:
        raise UnsafeUrlError("URL host did not resolve.") from None
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise UnsafeUrlError("URL host resolved to no addresses.")
    for addr in addresses:
        if _blocked(addr):
            raise UnsafeUrlError("URL resolves to a private/reserved address.")