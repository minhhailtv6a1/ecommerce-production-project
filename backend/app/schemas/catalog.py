"""Frontend-facing category and product contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryResponse(BaseModel):
    id: str = Field(pattern=r"^[0-9]{2}$", examples=["00"])
    slug: str = Field(examples=["dam-vay-nu"])
    name: str = Field(examples=["Đầm / Váy Nữ"])
    description: str | None = Field(
        default=None, examples=["Danh mục chuẩn 00: Đầm / Váy Nữ."]
    )
    product_count: int = Field(ge=0, examples=[42])


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]


class ProductImageResponse(BaseModel):
    id: UUID = Field(examples=["ee1dc6a9-18fa-5b73-b719-122fa1e8d30b"])
    url: str = Field(
        examples=[
            "catalog/00/00b32bd5ba9cdd7c2f11e3975b3e54fa.jpg"
        ]
    )
    alt: str = Field(examples=["Đầm / Váy Nữ - Mẫu 001"])
    sort_order: int = Field(ge=0, examples=[0])
    is_primary: bool = Field(examples=[True])


class ProductVariantResponse(BaseModel):
    id: UUID = Field(examples=["98b9126a-8d71-565d-bb44-dfa523a0eee3"])
    sku: str = Field(examples=["CAT00-0001-DEFAULT"])
    color: str | None = Field(default=None, examples=["Đen"])
    size: str | None = Field(default=None, examples=["S"])
    price: int = Field(ge=0, examples=[459000])
    compare_at_price: int | None = Field(default=None, ge=0, examples=[559000])
    inventory_quantity: int = Field(ge=0, examples=[12])
    is_active: bool = Field(examples=[True])


class ProductCardResponse(BaseModel):
    id: UUID = Field(examples=["d876766d-3552-5916-80ef-54658aace46b"])
    slug: str = Field(examples=["dam-vay-nu-001-99d81a5d1b"])
    name: str = Field(examples=["Đầm / Váy Nữ - Mẫu 001"])
    category_id: str = Field(pattern=r"^[0-9]{2}$", examples=["00"])
    brand: str | None = Field(default=None, examples=["Demo Brand A"])
    price: int = Field(ge=0, examples=[459000])
    compare_at_price: int | None = Field(default=None, ge=0, examples=[559000])
    currency: str = Field(examples=["VND"])
    primary_image: ProductImageResponse
    available_sizes: list[str] = Field(examples=[["S", "M", "L"]])
    available_colors: list[str] = Field(examples=[["Đen", "Trắng"]])
    in_stock: bool = Field(examples=[True])


class ProductDetailResponse(ProductCardResponse):
    description: str | None = Field(
        default=None,
        examples=[
            "Sản phẩm mô phỏng thuộc danh mục Đầm / Váy Nữ, "
            "được sinh từ bộ ảnh phục vụ phát triển và kiểm thử."
        ],
    )
    status: Literal["published"] = Field(examples=["published"])
    created_at: datetime = Field(examples=["2025-01-01T00:00:00+00:00"])
    images: list[ProductImageResponse]
    variants: list[ProductVariantResponse]


class ProductListResponse(BaseModel):
    items: list[ProductCardResponse]
    total: int = Field(ge=0, examples=[150])
    page: int = Field(ge=1, examples=[1])
    page_size: int = Field(ge=1, examples=[20])
    pages: int = Field(ge=0, examples=[8])
