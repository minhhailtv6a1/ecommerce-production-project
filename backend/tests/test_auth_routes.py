"""HTTP contract tests for custom authentication endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auth import get_auth_service, require_admin
from app.core.security import IssuedAccessToken
from app.main import app
from app.repositories.users import UserRecord
from app.services.auth import (
    AuthenticationResult,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UnauthorizedError,
)


class FakeAuthService:
    def __init__(self) -> None:
        self.user = UserRecord(
            id=uuid4(),
            email="user@example.com",
            password_hash="not-exposed",
            is_active=True,
            role="customer",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.token = IssuedAccessToken("signed-access-token", 1800)

    def register(self, *, email: str, password: str) -> AuthenticationResult:
        if email == "existing@example.com":
            raise EmailAlreadyRegisteredError
        return AuthenticationResult(self.user, self.token)

    def login(self, *, email: str, password: str) -> AuthenticationResult:
        if password != "secret123":
            raise InvalidCredentialsError
        return AuthenticationResult(self.user, self.token)

    def current_user(self, token: str) -> UserRecord:
        if token != self.token.value:
            raise UnauthorizedError
        return self.user


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_register_returns_user_and_bearer_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "USER@example.com", "password": "secret123"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"] == "signed-access-token"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["role"] == "customer"
    assert "password_hash" not in body["user"]


def test_register_rejects_client_supplied_admin_role(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "secret123",
            "role": "admin",
        },
    )

    assert response.status_code == 422


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "existing@example.com", "password": "secret123"},
    )

    assert response.status_code == 409


def test_login_rejects_invalid_credentials_with_generic_message(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "UNAUTHORIZED"
    assert body["message"] == "Invalid email or password"
    assert body["field_errors"] == {}
    assert body["request_id"] == response.headers["x-request-id"]
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_requires_and_validates_bearer_token(client: TestClient) -> None:
    missing = client.get("/api/v1/auth/me")
    valid = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer signed-access-token"},
    )

    assert missing.status_code == 401
    assert valid.status_code == 200
    assert valid.json()["email"] == "user@example.com"
    assert valid.json()["role"] == "customer"


def test_require_admin_distinguishes_unauthenticated_customer_and_admin() -> None:
    probe = FastAPI()
    service = FakeAuthService()

    @probe.get("/admin-probe")
    def admin_probe(user: UserRecord = Depends(require_admin)) -> dict[str, str]:
        return {"role": user.role}

    probe.dependency_overrides[get_auth_service] = lambda: service
    client = TestClient(probe)

    missing = client.get("/admin-probe")
    customer = client.get(
        "/admin-probe",
        headers={"Authorization": "Bearer signed-access-token"},
    )
    service.user = UserRecord(
        id=service.user.id,
        email=service.user.email,
        password_hash=service.user.password_hash,
        is_active=True,
        role="admin",
        created_at=service.user.created_at,
    )
    admin = client.get(
        "/admin-probe",
        headers={"Authorization": "Bearer signed-access-token"},
    )

    assert missing.status_code == 401
    assert customer.status_code == 403
    assert admin.status_code == 200
    assert admin.json() == {"role": "admin"}
