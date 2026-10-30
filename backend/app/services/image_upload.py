"""Validation for untrusted image uploads used by inference APIs."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_MIME_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/bmp"}
)
FORMAT_SUFFIXES = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "BMP": ".bmp",
}


class InvalidUploadedImageError(ValueError):
    """Raised when an uploaded file cannot safely be used as an image."""


def validate_uploaded_image(
    content: bytes,
    *,
    content_type: str | None,
    max_bytes: int,
    max_pixels: int,
) -> str:
    """Validate MIME, encoded size, actual format, decode, and dimensions."""
    if content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise InvalidUploadedImageError("Unsupported image MIME type")
    if not content:
        raise InvalidUploadedImageError("Uploaded image is empty")
    if len(content) > max_bytes:
        raise InvalidUploadedImageError("Uploaded image exceeds the size limit")
    try:
        with Image.open(BytesIO(content)) as image:
            image_format = image.format
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > max_pixels:
                raise InvalidUploadedImageError(
                    "Uploaded image exceeds the pixel limit"
                )
            image.verify()
        with Image.open(BytesIO(content)) as image:
            image.convert("RGB").load()
    except InvalidUploadedImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidUploadedImageError(
            "Uploaded file is not a decodable image"
        ) from exc
    suffix = FORMAT_SUFFIXES.get(image_format or "")
    if suffix is None:
        raise InvalidUploadedImageError("Unsupported encoded image format")
    return suffix
