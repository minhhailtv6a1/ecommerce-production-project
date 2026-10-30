"""Load stable links between Pinecone documents and catalog records."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class CatalogLinkError(ValueError):
    """Raised when the product-image manifest cannot link catalog records."""


@dataclass(frozen=True)
class CatalogVectorLink:
    """Relational identifiers associated with one Pinecone document."""

    product_id: str
    image_id: str


def load_catalog_vector_links(path: Path) -> dict[str, CatalogVectorLink]:
    """Load vector ID to product/image ID mappings from the catalog CSV."""
    path = path.expanduser().resolve()
    if not path.is_file():
        raise CatalogLinkError(f"Catalog image manifest does not exist: {path}")

    required = {"id", "product_id", "pinecone_vector_id"}
    links: dict[str, CatalogVectorLink] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise CatalogLinkError(
                "Catalog image manifest is missing columns: "
                + ", ".join(sorted(missing))
            )

        for row_number, row in enumerate(reader, start=2):
            vector_id = (row.get("pinecone_vector_id") or "").strip()
            product_id = (row.get("product_id") or "").strip()
            image_id = (row.get("id") or "").strip()
            if not vector_id or not product_id or not image_id:
                raise CatalogLinkError(
                    f"Catalog image manifest has an empty link at row {row_number}"
                )
            link = CatalogVectorLink(product_id=product_id, image_id=image_id)
            existing = links.get(vector_id)
            if existing is not None and existing != link:
                raise CatalogLinkError(
                    f"Conflicting catalog links for vector ID {vector_id!r}"
                )
            links[vector_id] = link

    if not links:
        raise CatalogLinkError("Catalog image manifest contains no records")
    return links
