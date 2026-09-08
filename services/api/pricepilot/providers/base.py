"""Base contracts for provider adapters and the shared HTTP JSON client.

Providers are never tightly coupled to the app: every slot is an interface in
this package, resolved through the registry in `_registry.py`. Unconfigured
slots are reported as `unavailable` rather than synthesizing data.
"""

from __future__ import annotations

import httpx

from pricepilot.errors import ProviderError
from pricepilot.logging import get_logger
from pricepilot.models import ProviderAvailability, ProviderStatus

log = get_logger("providers.base")


class JsonClient:
    """Small JSON HTTP helper with strict status handling.

    Never blindly calls `response.json()`: checks status and content-type first
    and raises `ProviderError` with a stable code on every failure mode.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
            follow_redirects=False,
        )
        self.base_url = base_url
        self.timeout = timeout

    async def get_json(self, path: str, *, params: dict | None = None) -> dict:
        try:
            resp = await self._client.get(path, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderError(
                "upstream",
                f"request timed out ({self.timeout}s)",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("upstream", f"request failed: {exc.__class__.__name__}") from exc

        if resp.status_code == 429:
            raise ProviderError("upstream", "rate limited (429)", status_code=503)
        if resp.status_code in (401, 403):
            raise ProviderError("upstream", "authentication or authorization failed", status_code=401)
        if resp.status_code >= 500:
            raise ProviderError(
                "upstream",
                f"upstream error (status {resp.status_code})",
                status_code=502,
            )
        if resp.status_code < 200 or resp.status_code >= 300:
            raise ProviderError(
                "upstream",
                f"unexpected status {resp.status_code}",
                status_code=502,
            )

        content_type = resp.headers.get("content-type", "")
        if "json" not in content_type:
            raise ProviderError("upstream", "response was not JSON")

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderError("upstream", "malformed JSON in response") from exc
        if not isinstance(data, dict):
            raise ProviderError("upstream", "response JSON was not an object")
        return data

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


def provider_status(name: str, *, available: bool, reason: str | None = None) -> ProviderStatus:
    return ProviderStatus(
        name=name,
        availability=provider_availability(available),
        reason=reason,
    )


def provider_availability(available: bool) -> ProviderAvailability:
    return ProviderAvailability.AVAILABLE if available else ProviderAvailability.UNAVAILABLE