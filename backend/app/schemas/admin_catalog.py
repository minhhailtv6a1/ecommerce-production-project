"""Admin-only product catalog request and response contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProductStatus = Literal["draft", "published", "archived"]
ImageIndexStatus = Literal["pending", "indexing", "indexed", "failed", "removed"]


class AdminProductCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=240)
    slug: str = Field(
        min_length=1,
        max_length=240,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, max_length=10_000)
    category_id: str = Field(pattern=r"^[0-9]{2}$")
    brand: str | None = Field(default=None, max_length=160)
    currency: str = Field(default="VND", pattern=r"^[A-Z]{3}$")


class AdminProductUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=240)
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=240,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    description: str | None = Field(default=None, max_length=10_000)
    category_id: str | None = Field(default=None, pattern=r"^[0-9]{2}$")
    brand: str | None = Field(default=None, max_length=160)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def require_change(self) -> "AdminProductUpdateRequest":
        if not self.model_fields_set.difference({"expected_version"}):
            raise ValueError("At least one product field must be provided")
        return self


class AdminVariantCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=120)
    color: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=120)
    price: int = Field(ge=0)
    compare_at_price: int | None = Field(default=None, ge=0)
    inventory_quantity: int = Field(default=0, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def compare_price_is_valid(self) -> "AdminVariantCreateRequest":
        if self.compare_at_price is not None and self.compare_at_price < self.price:
            raise ValueError("compare_at_price must be greater than or equal to price")
        return self


class AdminVariantUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, max_length=120)
    size: str | None = Field(default=None, max_length=120)
    price: int | None = Field(default=None, ge=0)
    compare_at_price: int | None = Field(default=None, ge=0)
    inventory_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AdminVariantUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one variant field must be provided")
        return self


class AdminImageUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alt_text: str | None = Field(default=None, min_length=1, max_length=500)
    sort_order: int | None = Field(default=None, ge=0, le=32_767)
    is_primary: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AdminImageUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one image field must be provided")
        return self


class AdminVariantResponse(BaseModel):
    id: UUID
    sku: str
    color: str | None
    size: str | None
    price: int
    compare_at_price: int | None
    inventory_quantity: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AdminImageResponse(BaseModel):
    id: UUID
    storage_path: str
    url: str | None = None
    alt_text: str
    sort_order: int
    is_primary: bool
    index_status: ImageIndexStatus
    indexed_at: datetime | None
    index_error: str | None
    created_at: datetime
    updated_at: datetime


class AdminProductResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    description: str | None
    category_id: str
    brand: str | None
    status: ProductStatus
    currency: str
    version: int
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime
    variants: list[AdminVariantResponse] = Field(default_factory=list)
    images: list[AdminImageResponse] = Field(default_factory=list)


class AdminProductSummaryResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    category_id: str
    brand: str | None
    status: ProductStatus
    currency: str
    version: int
    price_from: int | None
    inventory_total: int
    index_status: ImageIndexStatus | None
    primary_image_url: str | None = None
    primary_image_alt: str | None = None
    updated_at: datetime


class AdminProductListResponse(BaseModel):
    items: list[AdminProductSummaryResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    pages: int = Field(ge=0)
