"""HTTP contract tests for protected admin product management."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_admin_catalog_service
from app.api.routes.auth import require_admin
from app.main import app
from app.repositories.admin_products import AdminProductVersionConflictError
from app.repositories.users import UserRecord


NOW = datetime.now(UTC)
PRODUCT_ID = uuid4()


def _product(*, status: str = "draft") -> dict[str, Any]:
    return {
        "id": PRODUCT_ID,
        "slug": "ao-thun-admin",
        "name": "Áo thun admin",
        "description": "Mô tả",
        "category_id": "02",
        "brand": "Demo",
        "status": status,
        "currency": "VND",
        "version": 1,
        "created_by": None,
        "updated_by": None,
        "created_at": NOW,
        "updated_at": NOW,
        "variants": [],
        "images": [],
    }


class FakeAdminCatalogService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_update = False

    def list_products(self, **filters: Any) -> dict[str, Any]:
        self.calls.append(("list", filters))
        return {
            "items": [{
                "id": PRODUCT_ID,
                "slug": "ao-thun-admin",
                "name": "Áo thun admin",
                "category_id": "02",
                "brand": "Demo",
                "status": "draft",
                "currency": "VND",
                "version": 1,
                "price_from": None,
                "inventory_total": 0,
                "index_status": None,
                "updated_at": NOW,
            }],
            "total": 1,
            "page": filters["page"],
            "page_size": filters["page_size"],
            "pages": 1,
        }

    def create_product(self, **values: Any) -> dict[str, Any]:
        self.calls.append(("create", values))
        result = _product()
        result.update(values["values"])
        return result

    def update_product(self, **values: Any) -> dict[str, Any]:
        if self.fail_update:
            raise AdminProductVersionConflictError("Product version is 2, expected 1")
        self.calls.append(("update", values))
        return _product()

    def publish(self, **values: Any) -> dict[str, Any]:
        self.calls.append(("publish", values))
        return _product(status="published")


@pytest.fixture
def service() -> FakeAdminCatalogService:
    return FakeAdminCatalogService()


@pytest.fixture
def client(service: FakeAdminCatalogService):
    admin = UserRecord(
        id=uuid4(),
        email="admin@example.com",
        password_hash="unused",
        is_active=True,
        role="admin",
        created_at=NOW,
    )
    app.dependency_overrides[require_admin] = lambda: admin
    app.dependency_overrides[get_admin_catalog_service] = lambda: service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_admin_product_list_forwards_filters_and_pagination(
    client: TestClient, service: FakeAdminCatalogService
) -> None:
    response = client.get(
        "/api/v1/admin/products",
        params={"status": "draft", "category_id": "02", "page": 2, "limit": 10},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(PRODUCT_ID)
    assert service.calls[0] == ("list", {
        "keyword": None,
        "category_id": "02",
        "status": "draft",
        "index_status": None,
        "page": 2,
        "page_size": 10,
    })


def test_admin_can_create_draft_and_publish_product(
    client: TestClient, service: FakeAdminCatalogService
) -> None:
    created = client.post(
        "/api/v1/admin/products",
        json={
            "name": "Áo thun admin",
            "slug": "ao-thun-admin",
            "category_id": "02",
            "brand": "Demo",
        },
    )
    published = client.post(f"/api/v1/admin/products/{PRODUCT_ID}/publish")

    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert [name for name, _ in service.calls] == ["create", "publish"]
    assert service.calls[0][1]["values"]["currency"] == "VND"


def test_version_conflict_uses_stable_error_contract(
    client: TestClient, service: FakeAdminCatalogService
) -> None:
    service.fail_update = True

    response = client.patch(
        f"/api/v1/admin/products/{PRODUCT_ID}",
        json={"expected_version": 1, "name": "Tên mới"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "PRODUCT_VERSION_CONFLICT"
    assert response.json()["request_id"]


def test_admin_product_routes_reject_anonymous_requests() -> None:
    app.dependency_overrides.clear()

    response = TestClient(app).get("/api/v1/admin/products")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"
