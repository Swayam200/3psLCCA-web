"""
Image processing utilities for form upload_img fields.
Handles compression preset resolution, settings validation, and image encoding.
"""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STRING_PRESETS = {"default", "no_compression"}

# key -> (expected_type, min_val, max_val, description)
IMG_SETTING_RULES: dict[str, tuple[type, int, int | None, str]] = {
    "max_px": (int, 1, 9999, "Maximum dimension (width or height) in pixels"),
    "max_width": (int, 1, 9999, "Maximum width in pixels"),
    "max_height": (int, 1, 9999, "Maximum height in pixels"),
    "quality": (int, 1, 95, "JPEG quality (1-95)"),
    "max_size_bytes": (int, 1, None, "Maximum output file size in bytes"),
}


# ---------------------------------------------------------------------------
# Settings validation
# ---------------------------------------------------------------------------


def _validate_img_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and coerce an image settings dict.

    Coercion is applied before type checking so that values loaded from
    text storage (where everything is a string) are handled transparently.

    Returns a new dict with all values coerced to their correct types.
    Raises TypeError or ValueError on any invalid entry.
    """
    unknown = settings.keys() - IMG_SETTING_RULES.keys()
    if unknown:
        raise ValueError(
            f"Unknown image setting(s): {unknown}. "
            f"Allowed keys: {set(IMG_SETTING_RULES)}"
        )

    if not settings:
        raise ValueError("Image settings dict cannot be empty.")

    coerced: dict[str, Any] = {}

    for key, value in settings.items():
        expected_type, min_val, max_val, description = IMG_SETTING_RULES[key]

        # Coerce from string (round-tripped through text storage)
        if not isinstance(value, expected_type):
            try:
                value = expected_type(value)
            except (ValueError, TypeError):
                raise TypeError(
                    f"'{key}' could not be converted to {expected_type.__name__} "
                    f"(got {type(value).__name__} {value!r}). "
                    f"Description: {description}"
                )

        # Reject bool even though it is a subclass of int
        if expected_type is int and isinstance(value, bool):
            raise TypeError(
                f"'{key}' must be an integer, not bool. " f"Description: {description}"
            )

        if value < min_val:
            raise ValueError(
                f"'{key}' must be >= {min_val}, got {value}. "
                f"Description: {description}"
            )

        if max_val is not None and value > max_val:
            raise ValueError(
                f"'{key}' must be <= {max_val}, got {value}. "
                f"Description: {description}"
            )

        coerced[key] = value

    return coerced


def resolve_img_settings(preset: str | dict[str, Any]) -> dict[str, Any] | None:
    """
    Resolve an image compression preset to a settings dict.

    Accepted values:
        "default"        -> {"max_px": 354, "quality": 85}
        "no_compression" -> None  (caller skips processing)
        dict             -> validated and coerced custom settings

    Raises ValueError / TypeError on invalid input.
    """
    if preset == "default":
        return {"max_px": 354, "quality": 85}

    elif preset == "no_compression":
        return None

    elif isinstance(preset, dict):
        return _validate_img_settings(preset)

    else:
        raise ValueError(
            f"Invalid image preset {preset!r}. "
            f"Expected one of {VALID_STRING_PRESETS} or a settings dict."
        )


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------


def compress_image(file_path: str, settings: dict[str, Any] | None) -> bytes:
    """
    Open, optionally resize/compress, and return image bytes.

    If settings is None (no_compression preset) the image is simply
    read and re-encoded as PNG or JPEG without any size changes.

    Settings keys used:
        max_px        - uniform cap on both width and height
        max_width     - cap on width only
        max_height    - cap on height only
        quality       - JPEG quality (1-95); ignored for PNG
        max_size_bytes - currently informational; not enforced via sweep
    """
    with Image.open(file_path) as img:
        img = img.convert("RGBA")

        if settings is not None:
            target_w = settings.get("max_width") or settings.get("max_px")
            target_h = settings.get("max_height") or settings.get("max_px")

            if target_w or target_h:
                # thumbnail keeps aspect ratio and never upscales
                cap_w = target_w or img.width
                cap_h = target_h or img.height
                img.thumbnail((cap_w, cap_h), Image.LANCZOS)

        quality = (settings or {}).get("quality", 85)
        has_alpha = img.getchannel("A").getextrema()[0] < 255

        buf = io.BytesIO()
        if has_alpha:
            img.save(buf, format="PNG", optimize=True)
        else:
            img.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True)

        return buf.getvalue()


def image_file_to_base64(
    file_path: str, preset: str | dict[str, Any] = "default"
) -> str:
    """
    Full pipeline: resolve preset -> compress -> base64 encode.
    Returns a UTF-8 base64 string ready for storage.
    """
    settings = resolve_img_settings(preset)
    img_bytes = compress_image(file_path, settings)
    return base64.b64encode(img_bytes).decode("utf-8")


