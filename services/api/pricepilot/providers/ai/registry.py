"""AI provider registry — resolves the configured AI provider from settings.

Supports a comma-separated `AI_PROVIDER` (primary, optional fallback), e.g.
`openai-compatible` or `ollama` or `openai-compatible,ollama`. When no provider
is configured/usable, the honest no-op is returned — nothing ever fakes an LLM.
"""

from __future__ import annotations

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.ai import AIProvider, NoopAIProvider
from pricepilot.providers.ai.gemini import GeminiProvider
from pricepilot.providers.ai.ollama import OllamaProvider
from pricepilot.providers.ai.openai_compatible import OpenAICompatibleProvider

log = get_logger("providers.ai.registry")


def _configured_names() -> list[str]:
    raw = (settings.ai_provider or "").strip().lower()
    if not raw:
        return []
    return [name.strip() for name in raw.split(",") if name.strip()]


def build_ai_providers() -> list[AIProvider]:
    """Build all configured AI providers, best-first for fallback ordering."""
    providers: list[AIProvider] = []
    for name in _configured_names():
        if name == "gemini":
            providers.append(GeminiProvider())
        elif name == "openai-compatible":
            providers.append(OpenAICompatibleProvider())
        elif name == "ollama":
            providers.append(OllamaProvider())
        else:
            log.warning("unknown AI provider %r; ignoring", name)
    if not providers:
        log.warning("no AI provider configured; using honest no-op")
        providers.append(NoopAIProvider())
    return providers


def primary_ai_provider() -> AIProvider:
    """The first configured AI provider (or no-op)."""
    return build_ai_providers()[0]


def ai_providers_available() -> bool:
    return any(not isinstance(provider, NoopAIProvider) for provider in build_ai_providers())