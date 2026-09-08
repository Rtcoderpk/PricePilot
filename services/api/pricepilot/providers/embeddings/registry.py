"""Embedding provider registry (comma-separated `PRICEPILOT_EMBEDDING_PROVIDER`).

Unset/unknown → honest NoopEmbeddingProvider; semantic search degrades to
keyword matching.
"""

from __future__ import annotations

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.embeddings import EmbeddingProvider, NoopEmbeddingProvider
from pricepilot.providers.embeddings.openai_compatible import OpenAIEmbeddingProvider

log = get_logger("providers.embeddings.registry")


def _configured_names() -> list[str]:
    raw = (settings.pricepilot_embedding_provider or "").strip().lower()
    return [name.strip() for name in raw.split(",") if name.strip()]


def build_embedding_provider() -> EmbeddingProvider:
    for name in _configured_names():
        if name == "openai-compatible":
            # requires an AI key; if absent the provider reports available()=False
            return OpenAIEmbeddingProvider()
        log.warning("unknown embedding provider %r; ignored", name)
    log.info("no embedding provider configured; using honest no-op")
    return NoopEmbeddingProvider()


def embedding_provider_available() -> bool:
    provider = build_embedding_provider()
    return not isinstance(provider, NoopEmbeddingProvider) and provider.available()