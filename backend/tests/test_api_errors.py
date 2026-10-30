"""Tests for the shared frontend-facing error contract."""

from fastapi.testclient import TestClient

from app.main import app


def test_validation_errors_have_stable_contract_and_request_id() -> None:
    response = TestClient(app).get("/api/v1/products", params={"limit": 0})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Request validation failed"
    assert "query.limit" in body["field_errors"]
    assert body["request_id"] == response.headers["x-request-id"]
