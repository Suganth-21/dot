"""Database access for `patient_reports`. No business decisions — turning a
report into a `PATIENT_REPORT` alert lives in `app.services.verify_service`.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient_report import PatientReport


async def create(session: AsyncSession, report: PatientReport) -> PatientReport:
    session.add(report)
    return report


async def delete_all(session: AsyncSession) -> None:
    """Phase-3-owned truncate for demo reset — see app.seed.reset."""
    await session.execute(PatientReport.__table__.delete())
