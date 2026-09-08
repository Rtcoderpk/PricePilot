"""Image shopping service.

Validates uploaded images strictly (mimetype + size + content sniff), calls the
configured VisionProvider, and returns `possible matches` with confidence. When
no vision backend is configured it degrades honestly to an empty identification
list + notice (NOT an error). Never pretends uncertain identification is exact.
"""

from __future__ import annotations

from pricepilot.logging import get_logger
from pricepilot.providers.vision import NoopVisionProvider, VisionMatch
from pricepilot.providers.vision.registry import build_vision_provider

log = get_logger("services.image")

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


class ImageValidationError(ValueError):
    pass


def validate_image(mime_type: str | None, size_bytes: int, content: bytes) -> None:
    if mime_type not in ALLOWED_MIME:
        raise ImageValidationError(
            f"Unsupported image type {mime_type!r}; allowed: {', '.join(sorted(ALLOWED_MIME))}."
        )
    if size_bytes > MAX_BYTES:
        raise ImageValidationError("Image exceeds the 5 MB limit.")
    if not content:
        raise ImageValidationError("Empty file upload.")


async def identify_image(
    image_bytes: bytes,
    mime_type: str,
) -> tuple[list[VisionMatch], str]:
    """Return (matches, notice). Empty matches + notice when vision is unconfigured."""
    provider = build_vision_provider()
    if isinstance(provider, NoopVisionProvider):
        return [], "Vision provider is not configured — enable PRICEPILOT_VISION_PROVIDER to identify this image."
    try:
        if not await provider.available():
            return [], "Vision provider is configured but not currently available."
        return await provider.identify(image_bytes, mime_type), ""
    except Exception:
        log.exception("vision identification failed")
        return [], "Vision provider failed to identify the image."