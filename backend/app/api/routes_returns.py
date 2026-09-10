"""GET/POST /api/returns and its sub-resources. HTTP layer only — see
`app.services.return_service` for every rule, the dispute gate, and role
scoping (CLAUDE.md rule 7). ARCHITECTURE.md §8.3.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.deps import get_db, require_permission, require_role
from app.models.user import User
from app.schemas.return_ import (
    CreateReturnRequest,
    DistributorReceiveRequest,
    DistributorReceiveResponse,
    ForwardReturnsRequest,
    ForwardReturnsResponse,
    ResolveDisputeRequest,
    ResolveDisputeResponse,
    ReturnDetailOut,
    ReturnOut,
    SetReturnStatusRequest,
)
from app.services import return_service

router = APIRouter()


@router.get("/returns", response_model=list[ReturnOut])
async def list_returns(
    pharmacyId: str | None = Query(default=None),
    distributorId: str | None = Query(default=None),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("returns:read")),
) -> list[ReturnOut]:
    return await return_service.list_returns(
        session, current_user, pharmacy_id=pharmacyId, distributor_id=distributorId, status=status,
    )


@router.get("/returns/{return_id}", response_model=ReturnDetailOut)
async def get_return(
    return_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("returns:read")),
) -> ReturnDetailOut:
    return await return_service.get_return(session, current_user, return_id)


@router.post("/returns", response_model=ReturnOut)
async def create_return(
    payload: CreateReturnRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("returns:create")),
) -> ReturnOut:
    return await return_service.create_return(session, current_user, payload)


@router.patch("/returns/{return_id}/receive", response_model=DistributorReceiveResponse)
async def distributor_receive(
    return_id: str,
    payload: DistributorReceiveRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("returns:receive_or_dispute")),
) -> DistributorReceiveResponse:
    return await return_service.distributor_receive(session, current_user, return_id, payload)


@router.patch("/returns/{return_id}/resolve", response_model=ResolveDisputeResponse)
async def resolve_dispute(
    return_id: str,
    payload: ResolveDisputeRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("returns:resolve_dispute")),
) -> ResolveDisputeResponse:
    return await return_service.resolve_dispute(session, current_user, return_id, payload.resolution_notes)


@router.post("/returns/forward", response_model=ForwardReturnsResponse)
async def forward_returns(
    payload: ForwardReturnsRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("returns:forward")),
) -> ForwardReturnsResponse:
    return await return_service.forward_returns(session, current_user, payload.return_ids)


@router.patch("/returns/{return_id}/status", response_model=ReturnOut)
async def set_return_status(
    return_id: str,
    payload: SetReturnStatusRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.DISTRIBUTOR)),
) -> ReturnOut:
    return await return_service.set_return_status(session, current_user, return_id, payload.status)
