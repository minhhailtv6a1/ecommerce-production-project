"""Request and response contracts for application authentication."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


def _validate_email(value: str) -> str:
    value = value.strip().casefold()
    if len(value) > 320 or value.count("@") != 1 or any(char.isspace() for char in value):
        raise ValueError("Invalid email address")
    local_part, domain = value.split("@")
    if not local_part or not domain or "." not in domain:
        raise ValueError("Invalid email address")
    return value


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, examples=["user@example.com"])
    password: SecretStr = Field(min_length=8, max_length=128, examples=["12345678"])

    _normalize_email = field_validator("email")(_validate_email)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, examples=["user@example.com"])
    password: SecretStr = Field(min_length=1, max_length=128, examples=["12345678"])

    _normalize_email = field_validator("email")(_validate_email)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(examples=["d384ece2-1b19-4c21-afd4-841405bb1690"])
    email: str = Field(min_length=3, max_length=320, examples=["user@example.com"])
    is_active: bool = Field(examples=[True])
    created_at: datetime = Field(examples=["2025-01-01T00:00:00+00:00"])


class TokenResponse(BaseModel):
    access_token: str = Field(examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."])
    token_type: Literal["bearer"] = Field(default="bearer", examples=["bearer"])
    expires_in: int = Field(examples=[1800])
    user: UserResponse
