"""Gemini provider — OpenAI-compatible text + multimodal vision.

Uses Gemini's OpenAI-compatible endpoint for structured text generation and its
native `generateContent` vision endpoint for image understanding. Keeps the
PricePilot rule: never treat the model as a source of truth for supplier data.
The model only extracts/understands; retrieval data must come from providers.

Config (env):
  AI_API_KEY       — Google AI Studio API key
  AI_MODEL         — Gemini model id (e.g. gemini-2.0-flash)
  AI_BASE_URL      — defaults to https://generativelanguage.googleapis.com/v1beta/openai
"""

from __future__ import annotations

import base64
import json

import httpx
from pydantic import BaseModel, Field

from pricepilot.config import settings
from pricepilot.errors import ProviderError
from pricepilot.logging import get_logger
from pricepilot.providers.ai import AIProvider


class _ProductUnderstandingSchema(BaseModel):
    """Strict schema for Gemini text → ProductQuery refinement."""

    model_config = {"extra": "ignore"}
    category: str | None = None
    product_name: str | None = None
    brand: str | None = None
    model: str | None = None
    sku: str | None = None
    attributes: dict[str, str] | None = None
    quantity: int | None = Field(default=None, ge=1)
    wholesale_required: bool | None = None
    budget: float | None = Field(default=None, ge=0)
    destination: str | None = None
    search_queries: list[str] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_information: list[str] | None = None

log = get_logger("providers.ai.gemini")

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
_VISION_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or settings.ai_api_key
        self.model = model or settings.ai_model or "gemini-2.0-flash"
        self.base_url = (base_url or settings.ai_base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    async def available(self) -> bool:
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
                    "content": (
                        "You extract and return ONLY valid JSON that strictly follows the "
                        "caller's requested JSON schema. Never add commentary. Never invent "
                        "facts that are not present in the input."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens or settings.ai_max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        except httpx.TimeoutException as exc:
            raise ProviderError("gemini", "request timed out", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("gemini", f"request failed: {exc.__class__.__name__}") from exc

        if resp.status_code == 401:
            raise ProviderError("gemini", "invalid API key (401)", status_code=401)
        if resp.status_code == 429:
            raise ProviderError("gemini", "rate limited (429)", status_code=503)
        if resp.status_code >= 500:
            raise ProviderError("gemini", f"provider error (status {resp.status_code})", status_code=502)
        if resp.status_code != 200:
            raise ProviderError("gemini", f"unexpected status {resp.status_code}", status_code=502)

        try:
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("gemini", "malformed provider response") from exc

        return _parse_json_to_schema(content, schema)

    async def describe_image(self, image_bytes: bytes, mime_type: str) -> str:
        """Ask Gemini to describe/identify a product image. Returns raw text.

        Only used for product understanding — the returned facts are validated
        against a schema by the caller, never trusted as supplier truth.
        """
        if not self.api_key:
            raise ProviderError("gemini", "no API key configured", status_code=400)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        url = f"{_VISION_URL}/{self.model}:generateContent?key={self.api_key}"
        body = {
            "contents": [
                {
                    "parts": [
                        {"inline_data": {"mime_type": mime_type, "data": b64}},
                        {
                            "text": (
                                "Identify the product in this image. Return ONLY JSON "
                                "matching this schema: category, product_name, brand, model, "
                                "visible_model_number, sku, color, size, material, "
                                "attributes (object), approximate_product_type, quantity, "
                                "confidence (0..1), search_terms (array of 2-4 search "
                                "queries). Leave unknown fields null/empty. Never invent "
                                "details not visible in the image."
                            )
                        },
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
                resp = await client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError("gemini", "vision request timed out", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("gemini", f"vision request failed: {exc.__class__.__name__}") from exc

        if resp.status_code != 200:
            raise ProviderError("gemini", f"vision error (status {resp.status_code})", status_code=502)

        try:
            payload = resp.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("gemini", "malformed vision response") from exc

        # Gemini may wrap JSON in ```json fences — strip them.
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        return cleaned


def _parse_json_to_schema(content: str, schema: type[BaseModel]) -> BaseModel:
    if isinstance(content, dict | list):
        raw: object = content
    elif isinstance(content, str):
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderError("gemini", "model returned malformed JSON") from exc
    else:
        raise ProviderError("gemini", "model returned unexpected output type")
    try:
        return schema.model_validate(raw)
    except Exception as exc:
        raise ProviderError("gemini", f"model output failed validation: {exc.__class__.__name__}") from exc
        try:
            raw = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderError("gemini", "model returned malformed JSON") from exc
    else:
        raise ProviderError("gemini", "model returned unexpected output type")
    try:
        return schema.model_validate(raw)
    except Exception as exc:
        raise ProviderError("gemini", f"model output failed validation: {exc.__class__.__name__}") from exc


async def provider() -> AIProvider:
    return GeminiProvider()