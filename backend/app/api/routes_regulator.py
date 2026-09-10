"""GET /api/regulator/profile — the one Phase-1 endpoint that is genuinely
role-restricted, per ARCHITECTURE.md §4.2 open question #5: the officer
profile that `pages/regulator.jsx` currently hardcodes moves into seeded
data here. Also the concrete example that proves the RBAC guard rejects the
wrong role server-side (BUILDPHASES.md Phase 1 verification).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.deps import get_db, require_role
from app.models.user import User
from app.schemas.reference import RegulatorOut
from app.services import reference_service

router = APIRouter()


@router.get("/regulator/profile", response_model=RegulatorOut)
async def get_regulator_profile(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.REGULATOR)),
) -> RegulatorOut:
    # entity_id, not a path param: a regulator reads their own jurisdiction's
    # profile, never another one's — there is no "which regulator" to guess.
    row = await reference_service.get_regulator_profile(session, current_user.entity_id)
    return RegulatorOut.model_validate(row)
