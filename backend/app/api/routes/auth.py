"""HTTP endpoints for registration, login, and current-user lookup."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.security import (
    Argon2PasswordManager,
    JwtAccessTokenManager,
    SecurityConfigurationError,
)
from app.repositories.database import (
    DatabaseConfigurationError,
    DatabaseConnectionError,
    open_database_connection,
)
from app.repositories.users import (
    PostgresUserRepository,
    UserRecord,
    UserRepositoryError,
)
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UnauthorizedError,
)


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def _password_manager() -> Argon2PasswordManager:
    return Argon2PasswordManager()


@lru_cache
def _token_manager() -> JwtAccessTokenManager:
    return JwtAccessTokenManager(settings)


def get_auth_service() -> Iterator[AuthService]:
    """Build a request-scoped service and close its database connection."""
    try:
        passwords = _password_manager()
        tokens = _token_manager()
        connection = open_database_connection()
        service = AuthService(
            users=PostgresUserRepository(connection),
            passwords=passwords,
            tokens=tokens,
        )
    except (
        DatabaseConfigurationError,
        DatabaseConnectionError,
        SecurityConfigurationError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    try:
        yield service
    finally:
        connection.close()


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
)
def register(
    request: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        result = service.register(
            email=request.email,
            password=request.password.get_secret_value(),
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc
    except UserRepositoryError as exc:
        raise _database_unavailable() from exc
    return _token_response(result.user, result.token.value, result.token.expires_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Log in with email and password",
)
def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        result = service.login(
            email=request.email,
            password=request.password.get_secret_value(),
        )
    except InvalidCredentialsError as exc:
        raise _unauthorized("Invalid email or password") from exc
    except UserRepositoryError as exc:
        raise _database_unavailable() from exc
    return _token_response(result.user, result.token.value, result.token.expires_in)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the authenticated user",
)
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise _unauthorized("Authentication is required")
    try:
        user = service.current_user(credentials.credentials)
    except UnauthorizedError as exc:
        raise _unauthorized("Invalid or expired access token") from exc
    except UserRepositoryError as exc:
        raise _database_unavailable() from exc
    return UserResponse.model_validate(user)


def _token_response(
    user: UserRecord,
    access_token: str,
    expires_in: int,
) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication database is unavailable",
    )
