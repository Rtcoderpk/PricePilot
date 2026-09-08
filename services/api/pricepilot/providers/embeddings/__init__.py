"""Embedding provider contract for semantic search / RAG.

Unmeasured provider is honest (`available()==False`); `NoopEmbeddingProvider`
makes `embed` raise a controlled ProviderUnavailableError so callers degrade to
the keyword fallback. Never fabricates vectors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pricepilot.errors import ProviderUnavailableError


class EmbeddingProvider(ABC):
    name: str = "embeddings"

    @abstractmethod
    async def available(self) -> bool:
        """Whether an embedding backend is configured and usable."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of short strings into vectors (same order)."""


class NoopEmbeddingProvider(EmbeddingProvider):
    name = "embeddings_unavailable"

    async def available(self) -> bool:
        return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise ProviderUnavailableError(
            "embeddings", "No embedding provider configured (set PRICEPILOT_EMBEDDING_PROVIDER)."
        )