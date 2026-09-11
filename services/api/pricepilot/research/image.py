"""Image → structured product extraction via Gemini vision.

Uses the vision provider registry (`PRICEPILOT_VISION_PROVIDER=gemini`). If no
vision backend is configured, degrades honestly to an empty extraction + notice.
Never invents data not visible in the image.
"""

from __future__ import annotations

import json

from pricepilot.logging import get_logger
from pricepilot.models import ProductImageExtraction
from pricepilot.providers.vision.registry import build_vision_provider

log = get_logger("research.image")

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
_MAX_BYTES = 5 * 1024 * 1024


async def extract_product_from_image(
    image_bytes: bytes,
    mime_type: str,
    *,
    vision_required: bool = True,
) -> tuple[ProductImageExtraction, str]:
    """Extract structured product data from an image.

    Returns (extraction, notice). When vision is unavailable/fails and
    `vision_required` is True, the provided image path must handle it as a
    controlled error; otherwise returns an honest empty extraction + notice.
    """
    mime = (mime_type or "").lower()
    if mime not in _ALLOWED_MIME:
        return ProductImageExtraction(confidence=0.0), "Unsupported image type — use JPEG, PNG, or WebP."
    if not image_bytes:
        return ProductImageExtraction(confidence=0.0), "Empty image upload."
    if len(image_bytes) > _MAX_BYTES:
        return ProductImageExtraction(confidence=0.0), "Image exceeds the 5 MB limit."

    provider = build_vision_provider()
    try:
        if not await provider.available():
            notice = "Vision provider is not configured (set PRICEPILOT_VISION_PROVIDER=gemini)."
            return ProductImageExtraction(confidence=0.0), notice
        matches = await provider.identify(image_bytes, mime)
    except Exception:
        log.exception("vision extraction failed for image")
        return ProductImageExtraction(confidence=0.0), "Vision provider failed to analyze the image."

    if not matches or not matches[0].description:
        return ProductImageExtraction(confidence=0.0), "Vision provider returned no usable description."

    text = matches[0].description
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Not JSON → use as a basic text description (no structured fields).
        return ProductImageExtraction(
            product_name=text.strip()[:500], confidence=0.3, search_terms=[text.strip()[:200]]
        ), "Vision returned a plain description (could not parse structured fields)."

    try:
        return ProductImageExtraction.model_validate(data), "OK"
    except Exception:
        log.warning("vision output failed schema validation; using raw fields", exc_info=True)
        return ProductImageExtraction(
            product_name=str(data.get("product_name") or data.get("description") or "")[:500] or None,
            category=str(data.get("category") or "") or None,
            brand=str(data.get("brand") or "") or None,
            confidence=float(data.get("confidence") or 0.0),
            search_terms=[str(x) for x in (data.get("search_terms") or [])][:5],
        ), "Vision output was partial."