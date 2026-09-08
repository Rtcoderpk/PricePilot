"""Structured-output pipeline for LLM calls.

Never trusts raw model text:
  request → parse/validate (Pydantic) → on invalid/malformed → bounded corrected
  retry → fallback provider → final controlled `StructuredOutputError`.

The caller decides at its level whether to degrade deterministically. This
module ensures a malformed LLM response can never crash the API and never
exposes raw model text or secrets.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pricepilot.errors import PricePilotError, ProviderUnavailableError
from pricepilot.logging import get_logger
from pricepilot.providers.ai import AIProvider, NoopAIProvider
from pricepilot.providers.ai.registry import build_ai_providers

if TYPE_CHECKING:
    from pydantic import BaseModel


log = get_logger("agents.structured")

MAX_ATTEMPTS = 3
ATTEMPT_TIMEOUT_SECONDS = 40


class StructuredOutputError(PricePilotError):
    def __init__(self, message: str = "AI provider could not produce valid structured output.") -> None:
        super().__init__("provider_unavailable", message, status_code=503)


async def generate_structured(
    prompt: str,
    schema: type[BaseModel],
    *,
    max_tokens: int | None = None,
    providers: list[AIProvider] | None = None,
) -> BaseModel:
    """Produce a validated structured model from an AI provider.

    Parallel contract: takes `providers` (best-first). Tries the primary with
    bounded corrected retries; on failure attempts the next fallback; if all
    fail, raises `StructuredOutputError`.
    """
    providers = providers or build_ai_providers()
    try:
        result = await _attempt_providers(prompt, schema, max_tokens=max_tokens, providers=providers)
        return result
    except ProviderUnavailableError as exc:
        # No net/LLM available at all.
        raise StructuredOutputError(str(exc)) from exc
    except PricePilotError as exc:
        raise StructuredOutputError(str(exc)) from exc


async def _attempt_providers(
    prompt: str,
    schema: type[BaseModel],
    *,
    max_tokens: int | None,
    providers: list[AIProvider],
) -> BaseModel:
    fallbacks = [p for p in providers if not isinstance(p, NoopAIProvider)]
    if not fallbacks:
        # Nothing configured → controlled error (caller will degrade).
        raise ProviderUnavailableError("ai", "No configured AI provider (set AI_PROVIDER).")

    last_error: Exception | None = None
    for index, provider in enumerate(fallbacks):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if not await provider.available():
                log.info("ai provider %s unavailable; skipping", provider.name)
                break  # this provider is down → try fallback
            try:
                return await asyncio.wait_for(
                    provider.generate_structured(prompt, schema, max_tokens=max_tokens),
                    timeout=ATTEMPT_TIMEOUT_SECONDS,
                )
            except TimeoutError as exc:
                last_error = exc
                log.warning("ai %s attempt %d timed out", provider.name, attempt)
            except PricePilotError as exc:
                last_error = exc
                log.warning("ai %s attempt %d failed: %s", provider.name, attempt, exc.code.value)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(0.3 * attempt)  # small bounded backoff
        # try next provider
        if index < len(fallbacks) - 1:
            log.info("trying fallback AI provider")
        else:
            break

    if isinstance(last_error, PricePilotError):
        raise last_error
    raise ProviderUnavailableError("ai", "AI provider failed or is not reachable")