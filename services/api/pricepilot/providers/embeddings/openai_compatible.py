"""OpenAI-compatible embeddings provider.

Talks to `/embeddings` using the same base URL / key as the chat provider. The
`product_embeddings` table is 1536-dim, matching `text-embedding-3-small`'s
default `size=1536`.
"""

from __future__ import annotations

import httpx

from pricepilot.config import settings
from pricepilot.errors import ProviderError
from pricepilot.logging import get_logger
from pricepilot.providers.embeddings import EmbeddingProvider

log = get_logger("providers.embeddings.openai")

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or settings.ai_api_key
        self.model = model or settings.ai_embedding_model
        self.base_url = (base_url or settings.ai_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    async def available(self) -> bool:
        return bool(self.api_key and self.model)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        body = {
            "model": self.model,
            "input": texts,
            "encoding_format": "float",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/embeddings", json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError("embeddings", "request timed out", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("embeddings", f"request failed: {exc.__class__.__name__}") from exc

        if resp.status_code == 401:
            raise ProviderError("embeddings", "invalid API key (401)", status_code=401)
        if resp.status_code >= 400:
            raise ProviderError("embeddings", f"provider error (status {resp.status_code})", status_code=502)

        try:
            payload = resp.json()
            items = payload["data"]
            vectors = [item["embedding"] for item in items]
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise ProviderError("embeddings", "malformed provider response") from exc

        if len(vectors) != len(texts):
            raise ProviderError("embeddings", "provider returned wrong number of embeddings")
        return vectors