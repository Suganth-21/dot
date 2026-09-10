"""GET/POST /api/batches, GET /api/search. HTTP layer only — see
`app.services.batch_service` for every rule and role scoping (CLAUDE.md
rule 7). ARCHITECTURE.md §8.2.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.deps import get_current_user, get_db, require_role
from app.models.user import User
from app.schemas.batch import (
    BatchOut,
    ChainVerificationOut,
    RegisterBatchRequest,
    RegisterBatchResponse,
    SaleRequest,
    SearchResultOut,
)
from app.services import batch_service

router = APIRouter()


@router.get("/batches", response_model=list[BatchOut])
async def list_batches(
    pharmacyId: str | None = Query(default=None),
    manufacturerId: str | None = Query(default=None),
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BatchOut]:
    return await batch_service.list_batches(
        session, current_user, status=status, query=q, limit=limit, offset=offset,
        pharmacy_id=pharmacyId, manufacturer_id=manufacturerId,
    )


@router.get("/batches/{identifier}", response_model=BatchOut)
async def get_batch(
    identifier: str, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> BatchOut:
    return await batch_service.get_batch(session, current_user, identifier)


@router.get("/batches/{identifier}/verify-chain", response_model=ChainVerificationOut)
async def verify_chain(
    identifier: str,
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_role(Role.REGULATOR)),
) -> ChainVerificationOut:
    return await batch_service.verify_chain(session, identifier)


@router.post("/batches", response_model=RegisterBatchResponse)
async def register_batch(
    payload: RegisterBatchRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.RETAILER)),
) -> RegisterBatchResponse:
    return await batch_service.register_batch(session, current_user, payload)


@router.post("/batches/{identifier}/sale", response_model=BatchOut)
async def record_sale(
    identifier: str,
    payload: SaleRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.RETAILER)),
) -> BatchOut:
    return await batch_service.record_sale(session, current_user, identifier, payload.units)


@router.get("/search", response_model=list[SearchResultOut])
async def search(
    q: str = Query(default=""),
    session: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> list[SearchResultOut]:
    return await batch_service.search(session, q)
