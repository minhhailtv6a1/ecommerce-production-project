"""Tests for the shared frontend-facing error contract."""

from fastapi.testclient import TestClient

from app.api.dependencies import get_product_service
from app.main import app


def test_validation_errors_have_stable_contract_and_request_id() -> None:
    # Request validation tests must not depend on live Supabase configuration.
    app.dependency_overrides[get_product_service] = lambda: object()
    try:
        response = TestClient(app).get("/api/v1/products", params={"limit": 0})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed"
    assert "query.limit" in body["field_errors"]
    assert body["request_id"] == response.headers["x-request-id"]
