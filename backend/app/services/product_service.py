"""Catalog hydration and browser-safe product image URLs."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Protocol

from app.repositories.products import ProductFilters
from app.schemas.catalog import (
    CategoryListResponse,
    ProductCardResponse,
    ProductDetailResponse,
    ProductImageResponse,
    ProductListResponse,
    ProductVariantResponse,
)


class CatalogRepository(Protocol):
    def list_categories(self) -> list[dict[str, Any]]: ...
    def list_products(self, filters: ProductFilters) -> tuple[list[dict[str, Any]], int]: ...
    def get_product(self, identifier: str) -> dict[str, Any] | None: ...
    def get_products_by_ids(self, product_ids: Sequence[str]) -> list[dict[str, Any]]: ...
    def get_variants(self, product_ids: Sequence[str]) -> list[dict[str, Any]]: ...
    def get_images(self, product_ids: Sequence[str]) -> list[dict[str, Any]]: ...


class ImageUrlResolver(Protocol):
    def resolve_many(self, storage_paths: Sequence[str]) -> dict[str, str]: ...


class ProductNotFoundError(LookupError):
    """Raised when no public product matches an ID or slug."""


class ProductService:
    def __init__(
        self,
        repository: CatalogRepository,
        image_url_resolver: ImageUrlResolver,
    ) -> None:
        self.repository = repository
        self.image_url_resolver = image_url_resolver

    def categories(self) -> CategoryListResponse:
        return CategoryListResponse(items=self.repository.list_categories())

    def list_products(self, filters: ProductFilters) -> ProductListResponse:
        rows, total = self.repository.list_products(filters)
        cards = self._hydrate_cards(rows)
        return ProductListResponse(
            items=cards,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            pages=math.ceil(total / filters.page_size) if total else 0,
        )

    def product_detail(self, identifier: str) -> ProductDetailResponse:
        row = self.repository.get_product(identifier)
        if row is None:
            raise ProductNotFoundError(identifier)
        product_id = str(row["id"])
        variants = self.repository.get_variants([product_id])
        images = self.repository.get_images([product_id])
        image_models = self._image_models(images)
        card = self._build_card(row, variants, image_models)
        return ProductDetailResponse(
            **card.model_dump(),
            description=row.get("description"),
            status="published",
            created_at=row["created_at"],
            images=image_models,
            variants=[ProductVariantResponse(**variant) for variant in variants],
        )

    def cards_by_ids(self, product_ids: Sequence[str]) -> dict[str, ProductCardResponse]:
        rows = self.repository.get_products_by_ids(product_ids)
        cards = self._hydrate_cards(rows)
        return {str(card.id): card for card in cards}

    def _hydrate_cards(
        self,
        rows: Sequence[dict[str, Any]],
    ) -> list[ProductCardResponse]:
        if not rows:
            return []
        product_ids = [str(row["id"]) for row in rows]
        variants = self.repository.get_variants(product_ids)
        images = self.repository.get_images(product_ids)
        variants_by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for variant in variants:
            variants_by_product[str(variant["product_id"])].append(variant)
        image_models = self._image_models(images)
        images_by_product: dict[str, list[ProductImageResponse]] = defaultdict(list)
        for image, model in zip(images, image_models, strict=True):
            images_by_product[str(image["product_id"])].append(model)
        return [
            self._build_card(
                row,
                variants_by_product[str(row["id"])],
                images_by_product[str(row["id"])],
            )
            for row in rows
        ]

    def _image_models(
        self,
        images: Sequence[dict[str, Any]],
    ) -> list[ProductImageResponse]:
        paths = [
            image["storage_path"]
            for image in images
            if not image.get("public_url")
        ]
        resolved = self.image_url_resolver.resolve_many(paths)
        return [
            ProductImageResponse(
                id=image["id"],
                url=image.get("public_url") or resolved[image["storage_path"]],
                alt=image["alt_text"],
                sort_order=image["sort_order"],
                is_primary=image["is_primary"],
            )
            for image in images
        ]

    @staticmethod
    def _build_card(
        row: dict[str, Any],
        variants: Sequence[dict[str, Any]],
        images: Sequence[ProductImageResponse],
    ) -> ProductCardResponse:
        if not variants:
            raise RuntimeError(f"Published product {row['id']} has no active variant")
        if not images:
            raise RuntimeError(f"Published product {row['id']} has no image")
        primary = next((image for image in images if image.is_primary), images[0])
        sizes = list(dict.fromkeys(v["size"] for v in variants if v.get("size")))
        colors = list(dict.fromkeys(v["color"] for v in variants if v.get("color")))
        return ProductCardResponse(
            id=row["id"],
            slug=row["slug"],
            name=row["name"],
            category_id=row["category_id"],
            brand=row.get("brand"),
            price=row["price"],
            compare_at_price=row.get("compare_at_price"),
            currency=row["currency"],
            primary_image=primary,
            available_sizes=sizes,
            available_colors=colors,
            in_stock=any(v["inventory_quantity"] > 0 for v in variants),
        )
