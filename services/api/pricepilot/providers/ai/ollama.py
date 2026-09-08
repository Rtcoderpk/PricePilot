"""Ollama local LLM provider (self-hosted, no API key required).

Talks to the local Ollama HTTP API (`/api/generate` or `/api/chat`) with JSON
format. Keeps the app dependency-free on paid cloud AI.
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

log = get_logger("providers.ai.ollama")

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model or settings.ai_model
        self.base_url = (base_url or settings.ai_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    async def available(self) -> bool:
        # A model must be set; no key required.
        if not self.model:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False

    async def generate_structured(
        self,
        prompt: str,
        schema: type[BaseModel],
        *,
        max_tokens: int | None = None,
    ) -> BaseModel:
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "num_predict": max_tokens or settings.ai_max_tokens,
                "temperature": settings.ai_temperature,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError("ollama", "LLM request timed out", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("ollama", f"LLM request failed: {exc.__class__.__name__}") from exc

        if resp.status_code != 200:
            raise ProviderError("ollama", f"provider error (status {resp.status_code})", status_code=502)

        try:
            data = resp.json()
            content = data.get("response", "")
        except (ValueError, AttributeError) as exc:
            raise ProviderError("ollama", "malformed provider response") from exc

        return _parse_json_to_schema(content, schema)


def _parse_json_to_schema(content: str, schema: type[BaseModel]) -> BaseModel:
    try:
        raw = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderError("ollama", "LLM returned malformed JSON") from exc
    try:
        return schema.model_validate(raw)
    except Exception as exc:
        raise ProviderError("ollama", f"LLM output failed validation: {exc.__class__.__name__}") from exc


async def provider() -> AIProvider:
    return OllamaProvider()