"""Patient Shield: public batch verification and suspicious-medicine
reports. CLAUDE.md rule 4 — nothing in this module, or anything it calls,
may ever require authentication. See ARCHITECTURE.md §3, §7.3, §8.7.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.enums import AlertSeverity, AlertType, BatchStatus, EventType
from app.models.patient_report import PatientReport
from app.repositories import batch_repo, event_repo, patient_report_repo
from app.schemas.public import (
    LocationIn,
    ReportSuspiciousRequest,
    ReportSuspiciousResponse,
    VerifyBatchOut,
    VerifyBatchSummaryOut,
    VerifyHistoryEntryOut,
)
from app.services import alert_service, batch_status


async def _lookup(session: AsyncSession, term: str):
    """Id, then code, then `BATCH-{input}` — ARCHITECTURE.md §3 / §8.7,
    matching `verifyService.js`'s mock lookup exactly."""
    batch = await batch_repo.get_by_id_or_code(session, term)
    if batch is not None:
        return batch
    if not term.startswith("BATCH-"):
        return await batch_repo.get_by_id_or_code(session, f"BATCH-{term}")
    return None


async def verify_batch(session: AsyncSession, term: str) -> VerifyBatchOut:
    batch = await _lookup(session, term)
    if batch is None:
        return VerifyBatchOut(verdict="NOT_FOUND", batch_id=term)

    now = get_settings().demo_now_dt
    status = batch_status.derive_status(batch.expiry_date, batch.status, now)

    if status == BatchStatus.DESTROYED:
        # ARCHITECTURE.md §7.3: a patient scanning a destroyed batch gets
        # the red verdict, but this is NOT a re-entry alert — a patient
        # checking a box is not evidence a pharmacy is selling it. Only a
        # follow-up suspicious report raises a PATIENT_REPORT alert.
        events = await event_repo.list_for_batch(session, batch.id)
        destroyed_event = next((e for e in reversed(events) if e.type == EventType.DESTROYED), None)
        destroyed_date = batch.destroyed_date or (destroyed_event.ts if destroyed_event else None)
        history = [VerifyHistoryEntryOut(type=e.type.value, ts=e.ts) for e in events[-5:]]
        return VerifyBatchOut(
            verdict="DESTROYED",
            batch=VerifyBatchSummaryOut(
                id=batch.id,
                drug_name=batch.drug_name,
                manufacturer_name=batch.manufacturer_name,
                expiry_date=batch.expiry_date,
                destroyed_date=destroyed_date,
                cert_id=batch.cert_id,
            ),
            history=history,
        )

    return VerifyBatchOut(
        verdict="GENUINE",
        batch=VerifyBatchSummaryOut(
            id=batch.id,
            drug_name=batch.drug_name,
            manufacturer_name=batch.manufacturer_name,
            expiry_date=batch.expiry_date,
            status=status,
        ),
    )


async def report_suspicious(
    session: AsyncSession, payload: ReportSuspiciousRequest, ip_hash: str | None
) -> ReportSuspiciousResponse:
    batch = None
    if payload.batch_id:
        batch = await batch_repo.get_by_id_or_code(session, payload.batch_id)

    # A live patient action happening "now", same reasoning as
    # alert_service.raise_alert's timestamp — not pinned to DEMO_NOW, which
    # is only for seeded historical data (ARCHITECTURE.md §4.10).
    now = datetime.now(UTC)
    location = payload.location or LocationIn()

    report = PatientReport(
        id=f"prep_{uuid.uuid4().hex[:16]}",
        batch_id=batch.id if batch else payload.batch_id,
        lat=location.lat,
        lng=location.lng,
        district=location.district,
        notes=payload.notes,
        photo_hash=payload.photo_hash,
        pharmacy_name=payload.pharmacy_name,
        ts=now,
        ip_hash=ip_hash,
    )
    await patient_report_repo.create(session, report)

    destroyed = False
    if batch is not None:
        status = batch_status.derive_status(batch.expiry_date, batch.status, get_settings().demo_now_dt)
        destroyed = status == BatchStatus.DESTROYED

    suffix = f" — {payload.batch_id}" if payload.batch_id else ""
    notes_suffix = f" ({payload.notes})" if payload.notes else ""
    await alert_service.raise_alert(
        session,
        type_=AlertType.PATIENT_REPORT,
        severity=AlertSeverity.critical if destroyed else AlertSeverity.high,
        batch=batch,
        entity_id="public",
        entity_name=payload.pharmacy_name or "Reported by patient",
        district=location.district or "Unknown",
        manufacturer_id=batch.manufacturer_id if batch else None,
        rule="Public report via Patient Shield",
        message=f"PATIENT REPORT: Suspicious medicine reported{suffix}{notes_suffix}",
    )
    await session.commit()

    return ReportSuspiciousResponse(
        id=report.id,
        batch_id=report.batch_id,
        location=location,
        notes=report.notes,
        photo_hash=report.photo_hash,
        pharmacy_name=report.pharmacy_name,
        ts=report.ts,
    )
