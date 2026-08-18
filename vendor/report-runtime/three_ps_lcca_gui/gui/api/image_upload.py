"""
gui/api/image_upload.py

Lets a POST payload set an "upload_img" field (e.g. agency_logo) with a plain
http(s) image URL instead of requiring the caller to already have base64
bytes on hand. Downloads the URL to a temp file and reuses the exact same
image_file_to_base64() pipeline the GUI's own upload_img widget uses (same
compression preset, same output format), so there's no divergence between
what a user uploads by hand and what the API accepts.

Also validates raw (non-URL) base64 values the same way: the GUI's own
Browse button only ever writes base64 that already passed through
image_file_to_base64(), but an API caller can send any string directly, so
it gets the same Pillow-backed "is this actually a decodable image"
check - a caller can no longer smuggle in arbitrary garbage/binary data
through a field the GUI would only ever populate with a real image.

Format is restricted to JPEG/PNG (_ALLOWED_IMAGE_FORMATS) for both the URL
and raw-base64 paths - upload_img is currently only used for the report
cover-page organisation logo, so GIF and anything else Pillow can decode
but that isn't a sensible print-logo format is rejected.

Runs entirely on the calling (Flask worker) thread - it's plain network I/O
and PIL processing, no Qt/engine access, so it belongs before the request
ever reaches ApiBridge.
"""

import base64
import binascii
import io
import os
import tempfile
import urllib.request

from PIL import Image, UnidentifiedImageError

from three_ps_lcca_gui.gui.components.utils.form_builder.image_utils import image_file_to_base64

from .registry import CHUNK_PAGE_MAP

_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB - generous ceiling for a logo image
_ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}  # Pillow's own `.format` names


def _looks_like_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _assert_allowed_format(img: Image.Image) -> None:
    if img.format not in _ALLOWED_IMAGE_FORMATS:
        raise ValueError(
            f"unsupported image format {img.format!r} - only "
            f"{'/'.join(sorted(_ALLOWED_IMAGE_FORMATS))} logos are accepted"
        )


def _validate_base64_image(value: str) -> None:
    """Raises binascii.Error/ValueError/PIL errors if `value` isn't valid
    base64, doesn't decode to a real, fully-readable image, or isn't one of
    _ALLOWED_IMAGE_FORMATS. Deliberately does not re-encode/compress the
    result (unlike the URL path) - a caller supplying already-correct base64
    shouldn't have it silently rewritten; this only rejects what wasn't an
    acceptable image to begin with."""
    data = base64.b64decode(value, validate=True)
    if not data:
        raise ValueError("decoded to zero bytes")
    with Image.open(io.BytesIO(data)) as img:
        _assert_allowed_format(img)
        img.verify()


def resolve_image_urls(chunk: str, payload: dict) -> tuple[dict, list[str]]:
    """For every "upload_img" field in `payload`: an http(s) URL is
    downloaded and replaced with the base64-encoded, preset-compressed image
    - exactly what the field would contain if a user had used the GUI's own
    Browse button. Any other non-empty string is checked as base64-encoded
    image data (decodable + a real, readable JPEG/PNG) but left as-is if
    valid - only genuinely invalid/wrong-format data is rejected. An empty
    string clears the field. Absent/non-string values are left untouched
    (schema validation catches the wrong type).

    Returns (payload_with_images_resolved, errors). `errors` holds one entry
    per field that failed to download/decode/validate - the caller should
    treat any entry here as a full request failure (nothing partially
    applied), same as a schema validation error."""
    entry = CHUNK_PAGE_MAP.get(chunk)
    if entry is None or entry["field_defs"] is None:
        return payload, []

    field_defs = {fd.key: fd for fd in entry["field_defs"] if hasattr(fd, "field_type")}
    payload = dict(payload)
    errors: list[str] = []

    for key, value in list(payload.items()):
        fd = field_defs.get(key)
        if fd is None or fd.field_type != "upload_img":
            continue
        if not isinstance(value, str):
            continue  # wrong type - schema validation catches that
        if value == "":
            continue  # empty string clears the image - same as the GUI's Clear button

        if _looks_like_url(value):
            try:
                payload[key] = _download_and_encode(value, fd.options or "default")
            except Exception as e:
                errors.append(f"'{key}': failed to fetch/convert image from {value!r} - {e}")
            continue

        try:
            _validate_base64_image(value)
        except (binascii.Error, ValueError, UnidentifiedImageError, OSError) as e:
            errors.append(f"'{key}': not valid base64 image data - {e}")

    return payload, errors


def _download_and_encode(url: str, preset) -> str:
    tmp_path = None
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = resp.read(_MAX_DOWNLOAD_BYTES + 1)
        if len(data) > _MAX_DOWNLOAD_BYTES:
            raise ValueError(f"image exceeds {_MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB limit")

        suffix = os.path.splitext(url.split("?")[0])[1][:10] or ".img"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        with Image.open(tmp_path) as img:
            _assert_allowed_format(img)

        return image_file_to_base64(tmp_path, preset)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
