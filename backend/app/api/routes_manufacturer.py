"""GET /api/manufacturer/inbox, POST /api/manufacturer/schedule,
GET /api/batches/{id}/cert-eligibility, POST /api/manufacturer/certificates.
HTTP layer only — see `app.services.manufacturer_service` for every rule
(CLAUDE.md rule 7). ARCHITECTURE.md §7.2, §8.5.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role
from app.deps import get_db, require_permission, require_role
from app.models.user import User
from app.schemas.manufacturer import (
    CertEligibilityOut,
    ScheduleFacilityRequest,
    ScheduleFacilityResponse,
    UploadCertificateRequest,
    UploadCertificateResponse,
)
from app.schemas.return_ import ReturnDetailOut
from app.services import manufacturer_service

router = APIRouter()


@router.get("/manufacturer/inbox", response_model=list[ReturnDetailOut])
async def list_inbox(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.MANUFACTURER)),
) -> list[ReturnDetailOut]:
    return await manufacturer_service.list_inbox(session, current_user)


@router.post("/manufacturer/schedule", response_model=ScheduleFacilityResponse)
async def schedule_facility(
    payload: ScheduleFacilityRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("facility:schedule")),
) -> ScheduleFacilityResponse:
    await manufacturer_service.schedule_facility(
        session, current_user, payload.batch_ids, payload.facility_id, payload.date,
    )
    return ScheduleFacilityResponse(ok=True)


@router.get("/batches/{identifier}/cert-eligibility", response_model=CertEligibilityOut)
async def cert_eligibility(
    identifier: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.MANUFACTURER)),
) -> CertEligibilityOut:
    return await manufacturer_service.cert_eligibility(session, current_user, identifier)


@router.post("/manufacturer/certificates", response_model=UploadCertificateResponse)
async def upload_certificate(
    payload: UploadCertificateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("certificate:upload")),
) -> UploadCertificateResponse:
    return await manufacturer_service.upload_certificate(
        session, current_user, payload.batch_id, payload.cert_id, payload.file_name,
    )
