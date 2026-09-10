"""POST /api/demo/reset — powers the profile-menu "Reset demo data" button.
ARCHITECTURE.md §8.12. Environment-gated: `ENABLE_DEMO_RESET=false` (the
default) must not expose reset behavior, in production most of all.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import Forbidden
from app.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import LogoutResponse
from app.seed.reset import reset_demo_data

router = APIRouter()


@router.post("/demo/reset", response_model=LogoutResponse)
async def demo_reset(
    session: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)
) -> LogoutResponse:
    settings = get_settings()
    if not settings.enable_demo_reset:
        raise Forbidden("Demo reset is disabled in this environment.", code="DEMO_RESET_DISABLED")

    await reset_demo_data(session)
    return LogoutResponse(ok=True)
