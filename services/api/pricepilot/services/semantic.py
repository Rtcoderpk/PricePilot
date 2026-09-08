"""Semantic search / RAG service over pgvector.

Wraps the EmbeddingProvider registry. When an embedding backend is configured it
can embed text and query `product_embeddings` (HNSW cosine). When unconfigured,
`available()` is False and all methods degrade honestly (embed raises a provider
error; `nearest` returns []). Keyword/trigram matching remains the fallback path
elsewhere in the codebase.
"""

from __future__ import annotations

from sqlalchemy import text

from pricepilot.logging import get_logger
from pricepilot.providers.embeddings import NoopEmbeddingProvider
from pricepilot.providers.embeddings.registry import build_embedding_provider

log = get_logger("services.semantic")


class EmbeddingService:
    def __init__(self, provider=None, *, session=None) -> None:
        self.provider = provider if provider is not None else build_embedding_provider()
        self.session = session  # optional sqlalchemy session

    async def available(self) -> bool:
        if isinstance(self.provider, NoopEmbeddingProvider):
            return False
        try:
            return await self.provider.available()
        except Exception:
            return False

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if isinstance(self.provider, NoopEmbeddingProvider):
            return []
        try:
            if not await self.provider.available():
                return []
            return await self.provider.embed(texts)
        except Exception:
            log.exception("embedding failed; returning empty (caller falls back to keyword)")
            return []

    async def persist_product(
        self,
        product_id: str,
        name: str,
        brand: str | None,
        model: str | None,
        model_name: str,
    ) -> bool:
        """Compute an embedding for a product and upsert into `product_embeddings`.

        Returns True if a vector was stored, False otherwise (unconfigured/failed).
        """
        if not await self.available() or self.session is None:
            return False
        text = " ".join(x for x in (brand, model, name) if x)
        if not text:
            return False
        vectors = await self.embed([text])
        if not vectors or not vectors[0]:
            return False
        vec = vectors[0]
        try:
            await self.session.execute(
                text(
                    "INSERT INTO product_embeddings (product_id, embedding, model, created_at) "
                    "VALUES (:pid, :vec::vector, :model, now()) "
                    "ON CONFLICT (product_id) DO UPDATE SET embedding=EXCLUDED.embedding, "
                    "model=EXCLUDED.model, created_at=now()"
                ),
                {"pid": product_id, "vec": _vec_sql(vec), "model": model_name},
            )
            await self.session.commit()
            return True
        except Exception:
            log.exception("embedding persist failed for %s", product_id)
            return False

    async def nearest(self, product_id: str, *, k: int = 5) -> list[str]:
        """Return k nearest product_ids by cosine similarity, or [] if unavailable."""
        if not await self.available() or self.session is None:
            return []
        try:
            result = await self.session.execute(
                text(
                    "SELECT product_id FROM product_embeddings "
                    "WHERE product_id != :pid "
                    "ORDER BY embedding <=> (SELECT embedding FROM product_embeddings WHERE product_id = :pid) "
                    "LIMIT :k"
                ),
                {"pid": product_id, "k": k},
            )
            return [row.product_id for row in result]
        except Exception:
            log.exception("embedding nearest failed for %s", product_id)
            return []


def _vec_sql(floats: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in floats) + "]"