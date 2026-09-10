"""Alert business logic: raising, listing (with the category -> severity ->
recency ordering ARCHITECTURE.md §4.7 declares a domain rule, not a query
convenience), reading, and regulator status transitions. See ARCHITECTURE.md
§4.7, §6.5, §8.6.

`raise_alert` is the only writer to the `alerts` table other than this
module's own read paths — `fraud_service` and (in a later phase)
`return_service`/`manufacturer_service` call it rather than constructing an
`Alert` row directly, the same one-writer discipline `event_service` uses
for `events` (CLAUDE.md rule 2).

Deliberately has no dependency on `batch_service` — see `BatchOut.from_model`
in `app.schemas.batch` for why: `batch_service` -> `fraud_service` ->
`alert_service` -> `batch_service` would be a circular import, so the
`GET /api/alerts/{id}` batch join below is built directly from repositories
instead.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import Forbidden, NotFound
from app.core.rbac import Role
from app.models.alert import Alert
from app.models.batch import Batch
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.models.report import Report
from app.models.user import User
from app.repositories import alert_repo, batch_repo, event_repo, reference_repo, report_repo
from app.schemas.alert import AlertOut, AlertStatusUpdateResponse
from app.schemas.batch import BatchOut
from app.schemas.report import GenerateReportRequest, ReportOut
from app.services import batch_status

_CATEGORY_RANK = {"oncology": 0, "antibiotics": 1, "cardiovascular": 2, "other": 3}
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


async def raise_alert(
    session: AsyncSession,
    *,
    type_: AlertType,
    severity: AlertSeverity,
    batch: Batch | None,
    entity_id: str | None,
    entity_name: str | None,
    district: str | None,
    manufacturer_id: str | None,
    rule: str,
    message: str,
) -> Alert:
    """Does not commit — the caller owns the transaction (same discipline as
    `event_service.append`), and in the re-entry path the caller commits
    even though the operation that triggered the alert is refused (the
    alert must survive; the refused write must not)."""
    now = datetime.now(timezone.utc)
    alert = Alert(
        id=f"alert_{uuid.uuid4().hex[:16]}",
        type=type_,
        severity=severity,
        status=AlertStatus.OPEN,
        batch_id=batch.id if batch else None,
        drug_name=batch.drug_name if batch else None,
        drug_category=batch.category if batch else None,
        entity_id=entity_id,
        entity_name=entity_name,
        district=district,
        manufacturer_id=manufacturer_id,
        rule=rule,
        message=message,
        audit_trail=[{"action": "ALERT_FIRED", "officer": "System", "ts": now.isoformat()}],
        ts=now,
    )
    await alert_repo.create(session, alert)
    return alert


async def find_latest_open(session: AsyncSession, batch_id: str, type_: AlertType) -> Alert | None:
    """Used by `return_service.resolve_dispute` to find the
    `QUANTITY_MISMATCH` alert a dispute resolution closes (ARCHITECTURE.md
    §7.1: "the open QUANTITY_MISMATCH alert is closed with an audit-trail
    entry"), matching the mock's own lookup
    (`alerts.find(a => a.batchId === batchId && a.type === type && a.status !== "CLOSED")`)."""
    candidates = await alert_repo.list_alerts(session, type_=type_.value, batch_id=batch_id)
    open_candidates = [a for a in candidates if a.status != AlertStatus.CLOSED]
    return open_candidates[0] if open_candidates else None  # list_alerts already orders newest-first


def _check_alert_scope(current_user: User, alert: Alert) -> None:
    """ARCHITECTURE.md §6.5 "Alerts — read" row. PICKUP_AGENT has no `—`
    entry there at all, so it never reaches here — the route's
    `require_permission("alerts:read")` guard rejects it with 403 first."""
    role = current_user.role
    if role == Role.REGULATOR:
        return
    if role in (Role.RETAILER, Role.DISTRIBUTOR) and alert.entity_id == current_user.entity_id:
        return
    if role == Role.MANUFACTURER and alert.manufacturer_id == current_user.entity_id:
        return
    raise Forbidden("You do not have access to this alert.", code="NOT_YOUR_ALERT")


def _scope_filters(current_user: User) -> dict[str, str]:
    role = current_user.role
    if role in (Role.RETAILER, Role.DISTRIBUTOR):
        return {"entity_id": current_user.entity_id}
    if role == Role.MANUFACTURER:
        return {"manufacturer_id": current_user.entity_id}
    return {}  # REGULATOR sees everything


def _sort_key(alert: Alert):
    category = alert.drug_category.value if alert.drug_category else None
    return (
        _CATEGORY_RANK.get(category, len(_CATEGORY_RANK)),
        _SEVERITY_RANK.get(alert.severity.value, len(_SEVERITY_RANK)),
        -alert.ts.timestamp(),
    )


async def list_alerts(
    session: AsyncSession,
    current_user: User,
    *,
    type_: str | None = None,
    status: str | None = None,
    district: str | None = None,
    drug_category: str | None = None,
    manufacturer_id: str | None = None,
) -> list[AlertOut]:
    filters = _scope_filters(current_user)
    if current_user.role == Role.REGULATOR and manufacturer_id:
        filters["manufacturer_id"] = manufacturer_id

    rows = await alert_repo.list_alerts(
        session, type_=type_, status=status, district=district, drug_category=drug_category, **filters
    )
    rows.sort(key=_sort_key)
    return [AlertOut.from_model(a) for a in rows]


async def _batch_out(session: AsyncSession, batch_id: str) -> BatchOut | None:
    """Local, repository-level equivalent of `batch_service._to_batch_out` —
    see this module's docstring for why it isn't just imported."""
    batch = await batch_repo.get_by_id(session, batch_id)
    if batch is None:
        return None
    events = await event_repo.list_for_batch(session, batch.id)
    facility_name = None
    if batch.scheduled_facility_id:
        facility = await reference_repo.get_facility(session, batch.scheduled_facility_id)
        facility_name = facility.name if facility else None
    status = batch_status.derive_status(batch.expiry_date, batch.status, get_settings().demo_now_dt)
    return BatchOut.from_model(batch, status=status, events=events, facility_name=facility_name)


async def get_alert(session: AsyncSession, current_user: User, alert_id: str) -> AlertOut:
    alert = await alert_repo.get(session, alert_id)
    if alert is None:
        raise NotFound("Alert not found.", code="ALERT_NOT_FOUND")
    _check_alert_scope(current_user, alert)

    batch_out = await _batch_out(session, alert.batch_id) if alert.batch_id else None
    return AlertOut.from_model(alert, batch=batch_out)


def transition(
    alert: Alert, status: AlertStatus, officer: str | None, *, action: str | None = None, notes: str | None = None
) -> None:
    """Sets `alert.status` and appends one audit-trail entry. Does not
    commit — same discipline as `raise_alert` — and does not look the alert
    up itself, so a caller that's already holding the row (e.g.
    `return_service.resolve_dispute`, closing the `QUANTITY_MISMATCH` alert
    in the same transaction as the return's own state change) can reuse
    this instead of re-implementing the audit-trail-append shape (CLAUDE.md
    rule 7: "no copy-pasted rule checks"). `action` defaults to `status`'s
    own value (`PATCH /api/alerts/{id}/status`'s case) but can be overridden
    with a more specific label — `resolve_dispute` uses
    `RESOLVED_AT_DISTRIBUTOR`, matching the mock exactly."""
    alert.status = status
    alert.audit_trail = [
        *alert.audit_trail,
        {
            "action": action or status.value,
            "officer": officer or "Officer",
            "ts": datetime.now(timezone.utc).isoformat(),
            "notes": notes,
        },
    ]


async def update_status(
    session: AsyncSession, alert_id: str, status: AlertStatus, officer: str | None
) -> AlertStatusUpdateResponse:
    """REGULATOR-only — enforced by the route's role guard, not here (this
    module has no ownership concept for alert status changes; a regulator's
    jurisdiction is national, ARCHITECTURE.md §6.5). Does not commit — the
    route commits, the same way every other write in this codebase leaves
    the transaction boundary to its caller."""
    alert = await alert_repo.get(session, alert_id)
    if alert is None:
        raise NotFound("Alert not found.", code="ALERT_NOT_FOUND")

    transition(alert, status, officer)
    return AlertStatusUpdateResponse(ok=True)


async def list_reports(session: AsyncSession) -> list[ReportOut]:
    rows = await report_repo.list_reports(session)
    return [ReportOut.from_model(r) for r in rows]


async def generate_report(session: AsyncSession, payload: GenerateReportRequest) -> ReportOut:
    """Metadata-only — real PDF generation is Phase 9 (BUILDPHASES.md cut
    list #2). Matches the mock's `generateReport` defaults exactly."""
    now = datetime.now(timezone.utc)
    month_label = now.strftime("%b %Y")
    report = Report(
        id=f"rep_{uuid.uuid4().hex[:16]}",
        title=payload.title or f"CDSCO Compliance Report — {month_label}",
        region=payload.region or "Tamil Nadu",
        category=payload.category or "all",
        created_at=now,
        size=f"{1 + (uuid.uuid4().int % 2000) / 1000:.1f} MB",
        file_path=None,
    )
    await report_repo.create(session, report)
    await session.commit()
    return ReportOut.from_model(report)
