"""Tests for public image upload validation."""

from io import BytesIO

import pytest
from PIL import Image

from app.services.image_upload import (
    InvalidUploadedImageError,
    validate_uploaded_image,
)


def _png_bytes(size: tuple[int, int] = (4, 3)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size, color=(20, 30, 40)).save(stream, format="PNG")
    return stream.getvalue()


def test_validate_uploaded_image_checks_actual_content() -> None:
    assert validate_uploaded_image(
        _png_bytes(),
        content_type="image/png",
        max_bytes=1024,
        max_pixels=100,
    ) == ".png"


def test_validate_uploaded_image_rejects_invalid_or_oversized_data() -> None:
    with pytest.raises(InvalidUploadedImageError, match="decodable"):
        validate_uploaded_image(
            b"not-an-image",
            content_type="image/png",
            max_bytes=1024,
            max_pixels=100,
        )
    with pytest.raises(InvalidUploadedImageError, match="pixel limit"):
        validate_uploaded_image(
            _png_bytes((11, 10)),
            content_type="image/png",
            max_bytes=1024,
            max_pixels=100,
        )
