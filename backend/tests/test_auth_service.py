"""Tests for registration, login, and access-token business logic."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.core.security import IssuedAccessToken
from app.repositories.users import UserRecord
from app.services.auth import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UnauthorizedError,
)


class FakeUsers:
    def __init__(self) -> None:
        self.by_email: dict[str, UserRecord] = {}

    def get_by_email(self, email: str) -> UserRecord | None:
        return self.by_email.get(email)

    def get_by_id(self, user_id: UUID) -> UserRecord | None:
        return next(
            (user for user in self.by_email.values() if user.id == user_id),
            None,
        )

    def create(self, *, email: str, password_hash: str) -> UserRecord:
        user = UserRecord(
            id=uuid4(),
            email=email,
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        self.by_email[email] = user
        return user


class FakePasswords:
    dummy_hash = "dummy-hash"

    def hash(self, password: str) -> str:
        return "hashed:" + password

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == "hashed:" + password


class FakeTokens:
    def __init__(self) -> None:
        self.token_users: dict[str, UUID] = {}

    def issue(self, user_id: UUID) -> IssuedAccessToken:
        token = "token-for-" + str(user_id)
        self.token_users[token] = user_id
        return IssuedAccessToken(value=token, expires_in=1800)

    def decode_user_id(self, token: str) -> UUID:
        try:
            return self.token_users[token]
        except KeyError as exc:
            raise ValueError("invalid token") from exc


def build_service() -> tuple[AuthService, FakeUsers, FakeTokens]:
    users = FakeUsers()
    tokens = FakeTokens()
    return (
        AuthService(users=users, passwords=FakePasswords(), tokens=tokens),
        users,
        tokens,
    )


def test_register_normalizes_email_hashes_password_and_issues_token() -> None:
    service, users, _ = build_service()

    result = service.register(email="  User@Example.COM ", password="secret123")

    assert result.user.email == "user@example.com"
    assert result.user.password_hash == "hashed:secret123"
    assert users.by_email["user@example.com"] == result.user
    assert result.token.value.startswith("token-for-")
    assert result.token.expires_in == 1800


def test_duplicate_registration_is_rejected() -> None:
    service, _, _ = build_service()
    service.register(email="user@example.com", password="secret123")

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register(email="USER@example.com", password="another123")


def test_login_uses_generic_error_for_unknown_email_or_wrong_password() -> None:
    service, _, _ = build_service()
    service.register(email="user@example.com", password="secret123")

    with pytest.raises(InvalidCredentialsError):
        service.login(email="missing@example.com", password="secret123")
    with pytest.raises(InvalidCredentialsError):
        service.login(email="user@example.com", password="wrong-password")


def test_current_user_requires_valid_token_and_active_user() -> None:
    service, _, _ = build_service()
    registered = service.register(email="user@example.com", password="secret123")

    current = service.current_user(registered.token.value)

    assert current.id == registered.user.id
    with pytest.raises(UnauthorizedError):
        service.current_user("invalid-token")
