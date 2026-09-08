"""Vision provider contract for image shopping.

Performs visual/product identification on uploaded image bytes. Results are
`possible matches` with confidence — never presented as certain unless the
provider is authoritative AND confirms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from pricepilot.errors import ProviderUnavailableError


@dataclass
class VisionMatch:
    description: str
    confidence: float  # 0..1
    candidate_query: str = ""  # search query that could find it in providers


class VisionProvider(ABC):
    name: str = "vision"

    @abstractmethod
    async def available(self) -> bool:
        """Whether a vision backend is configured."""

    @abstractmethod
    async def identify(self, image_bytes: bytes, mime_type: str) -> list[VisionMatch]:
        """Identify possible products in an uploaded image."""


class NoopVisionProvider(VisionProvider):
    name = "vision_unavailable"

    async def available(self) -> bool:
        return False

    async def identify(self, image_bytes: bytes, mime_type: str) -> list[VisionMatch]:
        raise ProviderUnavailableError("vision", "No vision provider configured (set PRICEPILOT_VISION_PROVIDER).")