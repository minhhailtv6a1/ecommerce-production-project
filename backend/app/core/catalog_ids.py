"""Stable catalog identities derived from dataset-relative image paths."""

from __future__ import annotations

import uuid


CATALOG_NAMESPACE = uuid.UUID("42ec71e6-dcc1-4f95-a552-c7b2a978e286")


def catalog_ids_for_image(relative_path: str) -> tuple[str, str, str]:
    """Return deterministic product, variant, and image UUIDs for one image."""
    product_id = uuid.uuid5(CATALOG_NAMESPACE, f"product:{relative_path}")
    variant_id = uuid.uuid5(CATALOG_NAMESPACE, f"variant:{product_id}:default")
    image_id = uuid.uuid5(CATALOG_NAMESPACE, f"image:{relative_path}")
    return str(product_id), str(variant_id), str(image_id)

