"""Manufacturer business logic: inbox, facility scheduling, certificate
binding. All rule enforcement and role scoping live here (CLAUDE.md rule
7). See ARCHITECTURE.md §7.2, §8.5.

Certificate binding reuses `return_service.assert_not_disputed` rather than
reimplementing the dispute check — "§7.1, reused" per ARCHITECTURE.md §7.2's
own pseudocode, exactly the reuse `return_service.assert_not_disputed`'s
docstring was written to support.
"""
from __future__ import annotations

import uuid
from datetime import date as date_
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, Forbidden, NotFound
from app.core.rbac import Role
from app.core.realtime import hub
from app.models.batch import Batch
from app.models.enums import BatchStatus, EventType, HolderType, NotificationKind
from app.models.user import User
from app.repositories import batch_repo, event_repo, reference_repo, return_repo
from app.schemas.batch import BatchOut, EventOut
from app.schemas.manufacturer import CertEligibilityOut, UploadCertificateResponse
from app.schemas.reference import DistributorOut, PharmacyOut
from app.schemas.return_ import ReturnDetailOut, ReturnOut
from app.services import batch_service, event_service, notification_service
from app.services.return_service import assert_not_disputed


async def list_inbox(session: AsyncSession, current_user: User) -> list[ReturnDetailOut]:
    rows = await return_repo.list_returns(
        session, status="FORWARDED", manufacturer_id=current_user.entity_id,
    )
    out: list[ReturnDetailOut] = []
    for ret in rows:
        batch = await batch_repo.get_by_id(session, ret.batch_id)
        if batch is None or batch.status == BatchStatus.DESTROYED:
            continue
        batch_out = await batch_service.to_batch_out(session, batch)
        pharmacy = await reference_repo.get_pharmacy(session, ret.pharmacy_id)
        distributor = await reference_repo.get_distributor(session, ret.distributor_id)
        base = ReturnOut.from_model(ret)
        out.append(ReturnDetailOut(
            **base.model_dump(), batch=batch_out,
            pharmacy=PharmacyOut.model_validate(pharmacy) if pharmacy else None,
            distributor=DistributorOut.model_validate(distributor) if distributor else None,
        ))
    return out


async def schedule_facility(
    session: AsyncSession, actor: User, batch_ids: list[str], facility_id: str, sched_date: date_
) -> None:
    facility = await reference_repo.get_facility(session, facility_id)
    if facility is None:
        raise NotFound("Facility not found.", code="FACILITY_NOT_FOUND")

    for batch_id in batch_ids:
        batch = await batch_repo.get_for_update(session, batch_id)
        if batch is None:
            raise NotFound(f"Batch {batch_id} not found.", code="BATCH_NOT_FOUND")
        if batch.manufacturer_id != actor.entity_id:
            raise Forbidden(f"Batch {batch_id} does not belong to your manufacturer account.", code="NOT_YOUR_BATCH")

        batch.scheduled_facility_id = facility.id
        batch.scheduled_facility_date = sched_date
        batch.updated_at = datetime.now(timezone.utc)

        await event_service.append(
            session, batch=batch, event_type=EventType.FACILITY_SCHEDULED,
            actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
            meta={"facility": facility.name, "date": sched_date.isoformat()},
            gps=(facility.lat, facility.lng),
        )

    await session.commit()


async def _assert_cert_eligible(session: AsyncSession, actor: User, batch: Batch | None) -> None:
    """ARCHITECTURE.md §7.2's `assert_cert_eligible`, ported exactly — raises
    a `DomainError` for every failure; never returns a soft `{eligible:
    false}` shape. That softer shape belongs only to `cert_eligibility`
    below, the read-only pre-check endpoint."""
    if batch is None:
        raise NotFound("Batch not found.", code="BATCH_NOT_FOUND")
    if batch.manufacturer_id != actor.entity_id:
        raise Forbidden("This batch does not belong to your manufacturer account.", code="NOT_YOUR_BATCH")
    if batch.status == BatchStatus.DESTROYED:
        raise Conflict(f"Batch {batch.id} has already been destroyed.", code="ALREADY_DESTROYED")

    types = {t.value for t in await event_repo.types_for_batch(session, batch.id)}
    if not ({"DISTRIBUTOR_CONFIRMED", "DISPUTE_RESOLVED"} & types):
        raise Conflict(
            "This batch has not been confirmed at the distributor stage. Certificate upload blocked.",
            code="NOT_DISTRIBUTOR_CONFIRMED",
        )
    if "FORWARDED" not in types:
        raise Conflict(
            "This batch has not been forwarded to the manufacturer yet. Certificate upload blocked.",
            code="NOT_FORWARDED",
        )

    ret = await return_repo.latest_for_batch(session, batch.id)
    assert_not_disputed(ret)  # §7.1, reused — raises 409 CHAIN_HALTED_DISPUTE


async def cert_eligibility(session: AsyncSession, current_user: User, identifier: str) -> CertEligibilityOut:
    """Read-only pre-check — ARCHITECTURE.md §8.5: "the real enforcement is
    inside the upload endpoint regardless." Ports `certEligibility` from the
    mock: never raises, always answers `{eligible, reason?}`."""
    batch = await batch_repo.get_by_id_or_code(session, identifier)
    try:
        await _assert_cert_eligible(session, current_user, batch)
    except NotFound:
        return CertEligibilityOut(eligible=False, reason="Batch not found")
    except Forbidden:
        return CertEligibilityOut(eligible=False, reason="This batch does not belong to your manufacturer account.")
    except Conflict as exc:
        return CertEligibilityOut(eligible=False, reason=exc.message)
    return CertEligibilityOut(eligible=True)


async def upload_certificate(
    session: AsyncSession, actor: User, batch_id: str, cert_id: str | None, file_name: str | None
) -> UploadCertificateResponse:
    batch = await batch_repo.get_for_update(session, batch_id)
    await _assert_cert_eligible(session, actor, batch)  # raises on any ineligibility, including disputed

    facility = None
    if batch.scheduled_facility_id:
        facility = await reference_repo.get_facility(session, batch.scheduled_facility_id)

    now = datetime.now(timezone.utc)
    resolved_cert_id = cert_id or f"CERT-{batch.code}-2026"
    batch.status = BatchStatus.DESTROYED
    batch.destroyed = True
    batch.destroyed_date = now
    batch.cert_id = resolved_cert_id
    batch.holder_type = HolderType.FACILITY
    batch.holder_id = facility.id if facility else None
    batch.holder_name = facility.name if facility else "Licensed facility"
    batch.updated_at = now

    event = await event_service.append(
        session, batch=batch, event_type=EventType.DESTROYED,
        actor_id=actor.entity_id, actor_name=actor.name, actor_role=actor.role.value,
        meta={"facility": facility.name if facility else None, "certId": resolved_cert_id, "fileName": file_name},
        gps=(facility.lat, facility.lng) if facility else None,
    )

    await notification_service.notify(
        session, Role.REGULATOR, "Batch destroyed",
        f"{batch.drug_name} ({batch.id}) destruction certificate uploaded",
        NotificationKind.success, f"/regulator/batches/{batch.id}",
    )
    await notification_service.notify(
        session, Role.RETAILER, "Return closed", f"{batch.drug_name} was destroyed and verified",
        NotificationKind.success, None,
    )

    await session.commit()
    await hub.publish(
        f"batch:{batch.id}", "batch.updated",
        {"batchId": batch.id, "status": batch.status.value,
         "event": EventOut.from_model(event).model_dump(mode="json", by_alias=True)},
    )

    batch_out = BatchOut.from_model(
        batch, status=batch.status, events=[event], facility_name=facility.name if facility else None,
    )
    return UploadCertificateResponse(ok=True, batch=batch_out, covered_batches=[batch.id])
