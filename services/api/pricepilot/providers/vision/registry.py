"""Vision provider registry (`PRICEPILOT_VISION_PROVIDER`).

`gemini` → Gemini multimodal vision (image → structured product extraction).
Anything else (or nothing) → honest `NoopVisionProvider`, never a fake result.
"""

from __future__ import annotations

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.vision import NoopVisionProvider, VisionMatch, VisionProvider

log = get_logger("providers.vision.registry")


class GeminiVisionProvider(VisionProvider):
    """Image → Gemini vision → structured product extraction text.

    The returned JSON is parsed into `ProductImageExtraction` by the research
    pipeline. Never invents data.
    """

    name = "gemini"

    def __init__(self) -> None:
        from pricepilot.providers.ai.gemini import GeminiProvider

        self._gemini = GeminiProvider()

    async def available(self) -> bool:
        return await self._gemini.available()

    async def identify(self, image_bytes: bytes, mime_type: str) -> list[VisionMatch]:
        text = await self._gemini.describe_image(image_bytes, mime_type)
        return [VisionMatch(description=text.strip()[:2000], confidence=1.0, candidate_query="")]


def build_vision_provider() -> VisionProvider:
    names = [n.strip().lower() for n in (settings.pricepilot_vision_provider or "").split(",") if n.strip()]
    if "gemini" in names:
        return GeminiVisionProvider()
    if names:
        # Unknown vision backend → honest no-op, never a fake.
        log.warning("vision provider %r not available; using honest no-op", names)
    return NoopVisionProvider()


def vision_provider_available() -> bool:
    provider = build_vision_provider()
    return not isinstance(provider, NoopVisionProvider) and provider.available()