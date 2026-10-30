"""Tests for product hydration and catalog contracts."""

from datetime import UTC, datetime
from uuid import UUID

from app.repositories.products import ProductFilters
from app.services.product_service import ProductService


PRODUCT_ID = "d876766d-3552-5916-80ef-54658aace46b"
VARIANT_ID = "98b9126a-8d71-565d-bb44-dfa523a0eee3"
IMAGE_ID = "ee1dc6a9-18fa-5b73-b719-122fa1e8d30b"


class FakeCatalogRepository:
    product = {
        "id": UUID(PRODUCT_ID),
        "slug": "dam-vay-nu-001",
        "name": "Đầm / Váy Nữ - Mẫu 001",
        "description": "Mô tả",
        "category_id": "00",
        "brand": "Demo Brand A",
        "status": "published",
        "currency": "VND",
        "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        "price": 459000,
        "compare_at_price": None,
        "inventory_quantity": 12,
    }
    variant = {
        "id": UUID(VARIANT_ID),
        "product_id": UUID(PRODUCT_ID),
        "sku": "CAT00-0001-DEFAULT",
        "color": "Đen",
        "size": "S",
        "price": 459000,
        "compare_at_price": None,
        "inventory_quantity": 12,
        "is_active": True,
    }
    image = {
        "id": UUID(IMAGE_ID),
        "product_id": UUID(PRODUCT_ID),
        "storage_path": "catalog/00/a.jpg",
        "public_url": None,
        "alt_text": "Đầm nữ",
        "sort_order": 0,
        "is_primary": True,
    }

    def list_categories(self):  # type: ignore[no-untyped-def]
        return [
            {
                "id": "00",
                "slug": "dam-vay-nu",
                "name": "Đầm / Váy Nữ",
                "description": None,
                "product_count": 200,
            }
        ]

    def list_products(self, filters: ProductFilters):  # type: ignore[no-untyped-def]
        return [self.product], 1

    def get_product(self, identifier: str):  # type: ignore[no-untyped-def]
        return self.product if identifier in {PRODUCT_ID, self.product["slug"]} else None

    def get_products_by_ids(self, product_ids):  # type: ignore[no-untyped-def]
        return [self.product] if PRODUCT_ID in product_ids else []

    def get_variants(self, product_ids):  # type: ignore[no-untyped-def]
        return [self.variant] if PRODUCT_ID in product_ids else []

    def get_images(self, product_ids):  # type: ignore[no-untyped-def]
        return [self.image] if PRODUCT_ID in product_ids else []


class FakeUrlResolver:
    def resolve_many(self, paths):  # type: ignore[no-untyped-def]
        return {path: f"https://cdn.example/{path}?token=x" for path in paths}


def test_product_service_returns_frontend_ready_cards_and_detail() -> None:
    service = ProductService(FakeCatalogRepository(), FakeUrlResolver())

    listing = service.list_products(ProductFilters())
    detail = service.product_detail("dam-vay-nu-001")

    assert listing.total == 1
    assert listing.items[0].available_sizes == ["S"]
    assert listing.items[0].available_colors == ["Đen"]
    assert listing.items[0].in_stock is True
    assert "token=x" in listing.items[0].primary_image.url
    assert detail.variants[0].sku == "CAT00-0001-DEFAULT"
    assert detail.images[0].is_primary is True
