"""AI provider contract for structured generation.

In Phase 1 the contract exists so the agent graph can type-check and run with a
honest no-op when no API key is configured. Real implementations (openai-
compatible, ollama) attach in Phase 3.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel


class AIProvider(ABC):
    name: str = "ai"

    @abstractmethod
    async def available(self) -> bool:
        """Whether an LLM backend is configured."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
    ) -> BaseModel:
        """Generate output conforming to `schema`.

        Implementations must validate against `schema` and raise provider
        errors on malformed output rather than returning raw text.
        """


class NoopAIProvider(AIProvider):
    """Honest no-op used when no AI provider is configured.

    Raises rather than fabricating a fake LLM response, so callers can degrade
    gracefully to the configured fallback path.
    """

    name = "ai_unavailable"

    async def available(self) -> bool:
        return False

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
    ) -> BaseModel:
        raise NotImplementedError("AI provider not configured; callers must use available()")