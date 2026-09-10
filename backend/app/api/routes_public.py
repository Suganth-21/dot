"""GET /api/public/verify/{batchId}, POST /api/public/report.

CLAUDE.md rule 4 — this router NEVER carries an auth dependency, on any
route, ever. `tests/test_public_verify.py::test_no_route_has_auth_dependency`
fails the build if one is ever added, per ARCHITECTURE.md §6.6.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.crypto import sha256_hex
from app.core.rate_limit import limiter
from app.deps import get_db
from app.schemas.public import ReportSuspiciousRequest, ReportSuspiciousResponse, VerifyBatchOut
from app.services import verify_service

router = APIRouter()


def _client_ip_hash(request: Request) -> str | None:
    client = request.client
    if client is None or not client.host:
        return None
    # Hashed, never raw — ARCHITECTURE.md §4.9 / §6.6 open question #9:
    # abuse-pattern analysis without storing an identifying IP address.
    return sha256_hex(client.host.encode("utf-8"))


@router.get("/public/verify/{batch_id}", response_model=VerifyBatchOut, response_model_exclude_none=True)
@limiter.limit(lambda: get_settings().public_verify_rate_limit)
async def verify_batch(
    request: Request, batch_id: str, session: AsyncSession = Depends(get_db)
) -> VerifyBatchOut:
    return await verify_service.verify_batch(session, batch_id)


@router.post("/public/report", response_model=ReportSuspiciousResponse)
@limiter.limit(lambda: get_settings().public_report_rate_limit)
async def report_suspicious(
    request: Request, payload: ReportSuspiciousRequest, session: AsyncSession = Depends(get_db)
) -> ReportSuspiciousResponse:
    return await verify_service.report_suspicious(session, payload, _client_ip_hash(request))
