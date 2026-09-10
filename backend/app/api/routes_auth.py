"""POST /api/auth/{login,demo-login,refresh,logout}, GET /api/auth/me.
HTTP layer only — every decision lives in `app.services.auth_service`
(CLAUDE.md rule 7). See ARCHITECTURE.md §8.1.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    DemoLoginRequest,
    LoginRequest,
    LogoutRequest,
    LogoutResponse,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
    UserPublic,
)
from app.services import auth_service

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    user, access_token, refresh_token = await auth_service.login(
        session, email=payload.email, password=payload.password
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/auth/demo-login", response_model=TokenResponse)
async def demo_login(payload: DemoLoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    user, access_token, refresh_token = await auth_service.demo_login(session, role=payload.role)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/auth/refresh", response_model=RefreshResponse)
async def refresh(payload: RefreshRequest, session: AsyncSession = Depends(get_db)) -> RefreshResponse:
    access_token, refresh_token = await auth_service.refresh(session, refresh_token_str=payload.refresh_token)
    return RefreshResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/logout", response_model=LogoutResponse)
async def logout(payload: LogoutRequest, session: AsyncSession = Depends(get_db)) -> LogoutResponse:
    await auth_service.logout(session, refresh_token_str=payload.refresh_token)
    return LogoutResponse(ok=True)


@router.get("/auth/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse(user=UserPublic.model_validate(current_user))
