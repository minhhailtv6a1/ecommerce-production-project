"""HTTP contract tests for protected cart and order endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_commerce_service
from app.api.routes.auth import require_current_user
from app.main import app
from app.repositories.users import UserRecord
from app.services.commerce import CommerceService
from tests.test_commerce_service import FakeCommerceStore


@pytest.fixture
def commerce_client() -> tuple[TestClient, FakeCommerceStore]:
    store = FakeCommerceStore()
    user = UserRecord(
        id=store.user_id,
        email="user@example.com",
        password_hash="hidden",
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    app.dependency_overrides[require_current_user] = lambda: user
    app.dependency_overrides[get_commerce_service] = lambda: CommerceService(store)
    try:
        yield TestClient(app), store
    finally:
        app.dependency_overrides.clear()


def test_cart_add_update_and_delete_contract(commerce_client) -> None:  # type: ignore[no-untyped-def]
    client, store = commerce_client

    added = client.post(
        "/api/v1/cart/items",
        json={"variant_id": str(store.variant_id), "quantity": 2},
    )
    updated = client.patch(
        f"/api/v1/cart/items/{store.variant_id}", json={"quantity": 3}
    )
    deleted = client.delete(f"/api/v1/cart/items/{store.variant_id}")

    assert added.status_code == 201
    assert added.json()["subtotal"] == 200_000
    assert updated.status_code == 200
    assert updated.json()["item_count"] == 3
    assert deleted.status_code == 204


def test_checkout_and_order_contract(commerce_client) -> None:  # type: ignore[no-untyped-def]
    client, store = commerce_client
    store.quantity = 2

    response = client.post(
        "/api/v1/orders",
        json={
            "receiver_name": "Nguyen Van A",
            "phone": "0900000000",
            "shipping_address": "1 Nguyen Hue, TP HCM",
        },
    )
    listing = client.get("/api/v1/orders")
    missing = client.get(f"/api/v1/orders/{uuid4()}")

    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["items"][0]["sku"] == "SKU-01"
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1
    assert missing.status_code == 404
    assert missing.json()["message"] == "Order not found"


def test_cart_requires_authentication() -> None:
    app.dependency_overrides[get_commerce_service] = lambda: CommerceService(FakeCommerceStore())
    try:
        response = TestClient(app).get("/api/v1/cart")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401

