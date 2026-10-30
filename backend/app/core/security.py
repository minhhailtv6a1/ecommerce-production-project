"""Argon2 password hashing and signed access-token primitives."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.core.config import Settings


class SecurityConfigurationError(RuntimeError):
    """Raised when JWT or password-hashing configuration is unusable."""


class InvalidAccessTokenError(ValueError):
    """Raised when an access token is invalid or expired."""


@dataclass(frozen=True)
class IssuedAccessToken:
    """Signed access token and its lifetime in seconds."""

    value: str
    expires_in: int


class Argon2PasswordManager:
    """Hash and verify passwords with pwdlib's recommended Argon2 settings."""

    dummy_hash = (
        "$argon2id$v=19$m=65536,t=3,p=4$wagCPXjifgvUFBzq4hqe3w$"
        "CYaIb8sB+wtD+Vu/P4uod1+Qof8h+1g7bbDlBID48Rc"
    )

    def __init__(self) -> None:
        try:
            from pwdlib import PasswordHash
        except ImportError as exc:
            raise SecurityConfigurationError(
                "Password hashing dependency is unavailable. "
                "Install requirements.txt."
            ) from exc
        self._password_hash = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._password_hash.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        try:
            return bool(self._password_hash.verify(password, password_hash))
        except Exception:
            return False


class JwtAccessTokenManager:
    """Issue and validate HS256 access JWTs for one application audience."""

    def __init__(self, config: Settings) -> None:
        if config.jwt_secret is None:
            raise SecurityConfigurationError("Missing authentication setting: JWT_SECRET")
        secret = config.jwt_secret.get_secret_value()
        if len(secret) < 32:
            raise SecurityConfigurationError(
                "JWT_SECRET must contain at least 32 characters"
            )
        self._secret = secret
        self._algorithm = config.jwt_algorithm
        self._expires_in = config.jwt_access_token_expire_minutes * 60
        self._issuer = config.jwt_issuer
        self._audience = config.jwt_audience

    def issue(self, user_id: UUID) -> IssuedAccessToken:
        try:
            import jwt
        except ImportError as exc:
            raise SecurityConfigurationError(
                "JWT dependency is unavailable. Install requirements.txt."
            ) from exc

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "type": "access",
            "iat": now,
            "exp": now + timedelta(seconds=self._expires_in),
            "iss": self._issuer,
            "aud": self._audience,
            "jti": str(uuid4()),
        }
        return IssuedAccessToken(
            value=jwt.encode(
                payload,
                self._secret,
                algorithm=self._algorithm,
            ),
            expires_in=self._expires_in,
        )

    def decode_user_id(self, token: str) -> UUID:
        try:
            import jwt
            from jwt.exceptions import InvalidTokenError
        except ImportError as exc:
            raise SecurityConfigurationError(
                "JWT dependency is unavailable. Install requirements.txt."
            ) from exc

        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["sub", "type", "iat", "exp", "iss", "aud"]},
            )
            if payload.get("type") != "access":
                raise InvalidAccessTokenError("Unexpected token type")
            return UUID(str(payload["sub"]))
        except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
            raise InvalidAccessTokenError("Invalid or expired access token") from exc
