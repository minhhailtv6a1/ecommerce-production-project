"""Hydrate ranked Pinecone image matches into unique public products."""

from __future__ import annotations

from collections.abc import Sequence

from app.repositories.pinecone import PineconeImageMatch
from app.schemas.image_search import ImageSearchItemResponse, ImageSearchResponse
from app.services.product_service import ProductService


def hydrate_visual_search_matches(
    matches: Sequence[PineconeImageMatch],
    *,
    product_service: ProductService,
    limit: int,
) -> ImageSearchResponse:
    """Deduplicate by product, hydrate, and retain Pinecone ranking order."""
    ranked: dict[str, float] = {}
    for match in matches:
        if not match.product_id or match.product_id in ranked:
            continue
        ranked[match.product_id] = match.score
    cards = product_service.cards_by_ids(list(ranked))
    items = [
        ImageSearchItemResponse(
            similarity_score=score,
            product=cards[product_id],
        )
        for product_id, score in ranked.items()
        if product_id in cards
    ]
    return ImageSearchResponse(items=items[:limit])
