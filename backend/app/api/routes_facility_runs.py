"""GET/POST /api/facility-runs and stop actions — the distributor ->
destruction-facility leg. HTTP layer only, see
`app.services.facility_run_service` for every rule and role scoping
(CLAUDE.md rule 7)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.deps import get_db, require_permission, require_role
from app.models.user import User
from app.schemas.facility_run import CreateFacilityRunRequest, DispatchResponse, FacilityRunOut
from app.services import facility_run_service

router = APIRouter()


@router.get("/facility-runs", response_model=list[FacilityRunOut])
async def list_facility_runs(
    distributorId: str | None = Query(default=None),
    agentId: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("facility_runs:read")),
) -> list[FacilityRunOut]:
    return await facility_run_service.list_runs(session, current_user, distributor_id=distributorId, agent_id=agentId)


@router.get("/facility-runs/{run_id}", response_model=FacilityRunOut)
async def get_facility_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("facility_runs:read")),
) -> FacilityRunOut:
    return await facility_run_service.get_run(session, current_user, run_id)


@router.post("/facility-runs", response_model=FacilityRunOut)
async def create_facility_run(
    payload: CreateFacilityRunRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("facility_runs:create_or_dispatch")),
) -> FacilityRunOut:
    return await facility_run_service.create_run(session, current_user, payload)


@router.post("/facility-runs/{run_id}/dispatch", response_model=DispatchResponse)
async def dispatch_facility_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    # Same precedent as routes/dispatch: both DISTRIBUTOR and PICKUP_AGENT
    # may call this, which a single permission key can't express alongside
    # facility_runs:create (DISTRIBUTOR-only, correct for *create*).
    current_user: User = Depends(require_role(Role.DISTRIBUTOR, Role.PICKUP_AGENT)),
) -> DispatchResponse:
    return await facility_run_service.dispatch_run(session, current_user, run_id)


@router.post("/facility-runs/{run_id}/deliver", response_model=FacilityRunOut)
async def deliver_facility_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("facility_runs:deliver")),
) -> FacilityRunOut:
    return await facility_run_service.deliver_run(session, current_user, run_id)
