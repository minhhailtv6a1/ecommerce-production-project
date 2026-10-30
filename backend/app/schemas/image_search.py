"""Public visual product-search response contracts."""

from pydantic import BaseModel, Field

from app.schemas.catalog import ProductCardResponse


class ImageSearchItemResponse(BaseModel):
    similarity_score: float = Field(ge=-1, le=1, examples=[0.8723])
    product: ProductCardResponse


class ImageSearchResponse(BaseModel):
    items: list[ImageSearchItemResponse]
    retrieval_time_ms: float = Field(
        default=0,
        ge=0,
        description=(
            "Server-side RAG retrieval time in milliseconds, including image "
            "embedding, Pinecone search, and product hydration."
        ),
        examples=[364.01],
    )
