"""OpenAI-compatible LLM provider (also covers Azure/OpenRouter/Mistral etc.).

Uses HTTP directly via the `/chat/completions` JSON API with
`response_format={"type": "json_object"}` where supported, then parses and
validates the structured output against the requested Pydantic schema.

Requires `AI_API_KEY` and `AI_MODEL`. `AI_BASE_URL` allows third-party
OpenAI-compatible endpoints or a self-hosted gateway. Provided as an
HTTP adapter so no heavy SDK is required and any compatible endpoint works.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx

from pricepilot.config import settings
from pricepilot.errors import ProviderError
from pricepilot.logging import get_logger
from pricepilot.providers.ai import AIProvider

if TYPE_CHECKING:
    from pydantic import BaseModel

log = get_logger("providers.ai.openai")

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAICompatibleProvider(AIProvider):
    name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or settings.ai_api_key
        self.model = model or settings.ai_model
        self.base_url = (base_url or settings.ai_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.temperature = temperature if temperature is not None else settings.ai_temperature
        self.max_tokens = max_tokens or settings.ai_max_tokens
        self.timeout = timeout

    async def available(self) -> bool:
        # A key + model are required. `AI_BASE_URL` is optional (defaults to OpenAI).
        return bool(self.api_key and self.model)

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
    ) -> BaseModel:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You extract and return ONLY valid JSON that strictly follows the "
                    "caller's requested JSON schema. Never add commentary.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "response_format": {"type": "json_object"},
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError("openai-compatible", "LLM request timed out", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("openai-compatible", f"LLM request failed: {exc.__class__.__name__}") from exc

        if resp.status_code == 401:
            raise ProviderError("openai-compatible", "invalid API key (401)", status_code=401)
        if resp.status_code == 429:
            raise ProviderError("openai-compatible", "rate limited (429)", status_code=503)
        if resp.status_code >= 500:
            raise ProviderError(
                "openai-compatible",
                f"provider error (status {resp.status_code})",
                status_code=502,
            )
        if resp.status_code != 200:
            raise ProviderError(
                "openai-compatible",
                f"unexpected status {resp.status_code}",
                status_code=502,
            )

        try:
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("openai-compatible", "malformed provider response") from exc

        return _parse_json_to_schema(content, schema)


def _parse_json_to_schema(content: str, schema: type[BaseModel]) -> BaseModel:
    """Parse + validate LLM JSON text into the requested schema.

    Raises ProviderError on malformed/invalid output; does NOT trust raw text.
    """
    if isinstance(content, dict | list):
        raw: object = content
    elif isinstance(content, str):
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "openai-compatible", "LLM returned malformed JSON"
            ) from exc
    else:
        raise ProviderError("openai-compatible", "LLM returned unexpected output type")

    try:
        return schema.model_validate(raw)
    except Exception as exc:  # Pydantic ValidationError etc.
        raise ProviderError(
            "openai-compatible", f"LLM output failed validation: {exc.__class__.__name__}"
        ) from exc


async def provider() -> AIProvider:
    return OpenAICompatibleProvider()