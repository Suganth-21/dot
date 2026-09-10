"""Wire shapes for /api/auth/*. ARCHITECTURE.md §6.3, §8.1. Field names and
shapes here are the contract the frontend already expects — see
frontend/src/store/authStore.js's `user` object and CLAUDE.md rule 3.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.rbac import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DemoLoginRequest(BaseModel):
    role: Role


class RefreshRequest(BaseModel):
    refresh_token: str = Field(validation_alias="refreshToken")

    model_config = ConfigDict(populate_by_name=True)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(validation_alias="refreshToken")

    model_config = ConfigDict(populate_by_name=True)


class UserPublic(BaseModel):
    """Never carries password_hash, signing_private_key, or any other
    secret — CLAUDE.md rule 7 / ARCHITECTURE.md §6.3."""

    id: str
    email: str
    name: str
    role: Role
    entity_id: str | None = Field(serialization_alias="entityId")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")
    user: UserPublic

    model_config = ConfigDict(populate_by_name=True)


class RefreshResponse(BaseModel):
    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")

    model_config = ConfigDict(populate_by_name=True)


class LogoutResponse(BaseModel):
    ok: bool = True


class MeResponse(BaseModel):
    user: UserPublic
