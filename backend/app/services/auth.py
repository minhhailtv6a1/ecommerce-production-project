"""Registration, login, and authenticated-user business logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.core.security import IssuedAccessToken
from app.repositories.users import (
    UserAlreadyExistsError,
    UserRecord,
)


class EmailAlreadyRegisteredError(RuntimeError):
    """Raised when registration targets an existing normalized email."""


class InvalidCredentialsError(RuntimeError):
    """Raised when login credentials cannot be authenticated."""


class UnauthorizedError(RuntimeError):
    """Raised when an access token does not identify an active user."""


class UserRepository(Protocol):
    def get_by_email(self, email: str) -> UserRecord | None: ...

    def get_by_id(self, user_id: UUID) -> UserRecord | None: ...

    def create(self, *, email: str, password_hash: str) -> UserRecord: ...


class PasswordManager(Protocol):
    dummy_hash: str

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class AccessTokenManager(Protocol):
    def issue(self, user_id: UUID) -> IssuedAccessToken: ...

    def decode_user_id(self, token: str) -> UUID: ...


@dataclass(frozen=True)
class AuthenticationResult:
    user: UserRecord
    token: IssuedAccessToken


class AuthService:
    """Coordinate user persistence, password hashing, and access tokens."""

    def __init__(
        self,
        *,
        users: UserRepository,
        passwords: PasswordManager,
        tokens: AccessTokenManager,
    ) -> None:
        self._users = users
        self._passwords = passwords
        self._tokens = tokens

    def register(self, *, email: str, password: str) -> AuthenticationResult:
        normalized_email = normalize_email(email)
        if self._users.get_by_email(normalized_email) is not None:
            raise EmailAlreadyRegisteredError

        password_hash = self._passwords.hash(password)
        try:
            user = self._users.create(
                email=normalized_email,
                password_hash=password_hash,
            )
        except UserAlreadyExistsError as exc:
            raise EmailAlreadyRegisteredError from exc
        return AuthenticationResult(user=user, token=self._tokens.issue(user.id))

    def login(self, *, email: str, password: str) -> AuthenticationResult:
        normalized_email = normalize_email(email)
        user = self._users.get_by_email(normalized_email)
        password_hash = user.password_hash if user else self._passwords.dummy_hash
        password_matches = self._passwords.verify(password, password_hash)
        if user is None or not password_matches or not user.is_active:
            raise InvalidCredentialsError
        return AuthenticationResult(user=user, token=self._tokens.issue(user.id))

    def current_user(self, token: str) -> UserRecord:
        try:
            user_id = self._tokens.decode_user_id(token)
        except ValueError as exc:
            raise UnauthorizedError from exc
        user = self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError
        return user


def normalize_email(email: str) -> str:
    return email.strip().casefold()
