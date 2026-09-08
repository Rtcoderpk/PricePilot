"""AI provider contract for structured generation.

Every AI provider returns *validated* Pydantic output and never raw text. An
"unavailable" provider is honest (`available()==False`), letting the structured
pipeline delegate to the fallback or a controlled degrade.
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
        """Whether an LLM backend is configured and usable."""

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
    ) -> BaseModel:
        """Generate output conforming to `schema`.

        Implementations MUST validate against `schema` and raise ProviderError on
        malformed/invalid output rather than returning raw text.
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
        from pricepilot.errors import ProviderUnavailableError

        raise ProviderUnavailableError(
            "ai", "No AI provider is configured (set AI_PROVIDER and AI_API_KEY)."
        )