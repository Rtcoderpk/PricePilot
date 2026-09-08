"""Vision provider registry (`PRICEPILOT_VISION_PROVIDER`).

Currently the only pluggable vision backend needs a key (OpenAI-compatible,
with `images` input) — left unconfigured by default so uploads degrade honestly
to `identifications=[]` + notice.
"""

from __future__ import annotations

from pricepilot.config import settings
from pricepilot.logging import get_logger
from pricepilot.providers.vision import NoopVisionProvider, VisionProvider

log = get_logger("providers.vision.registry")


def build_vision_provider() -> VisionProvider:
    names = [n.strip().lower() for n in (settings.pricepilot_vision_provider or "").split(",") if n.strip()]
    if names:
        # Placeholder: real vision backends (OpenAI-compatible multimodal,
        # CLIP, etc.) plug in here.
        log.warning("vision provider %r requested but not yet implemented; using honest no-op", names)
    return NoopVisionProvider()


def vision_provider_available() -> bool:
    provider = build_vision_provider()
    return not isinstance(provider, NoopVisionProvider) and provider.available()