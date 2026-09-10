"""GET /api/alerts, GET /api/alerts/{id}, PATCH /api/alerts/{id}/status —
ARCHITECTURE.md §4.7, §6.5, §8.6. Real HTTP requests against a real
database, seeded via the real reset path.
"""
import pytest

from app.models.enums import AlertSeverity, AlertType
from app.services import alert_service

DESTROYED_BATCH = "BATCH-DOX-2026-B04"  # ph_3, mfr_1 — see app/seed/seed_batches.py

_REGISTER_B04 = {
    "batchId": DESTROYED_BATCH, "drugName": "Doxorubicin 50mg", "drugKey": "DOX",
    "category": "oncology", "unitPrice": 4200, "manufacturerId": "mfr_1",
    "manufacturerName": "Cipla Ltd.", "mfgDate": "2026-01-01T00:00:00Z",
    "expiryDate": "2027-01-01T00:00:00Z", "quantity": 10,
}


async def _token(client, role: str) -> str:
    resp = await client.post("/api/auth/demo-login", json={"role": role})
    assert resp.status_code == 200, resp.text
    return resp.json()["accessToken"]


async def _trigger_reentry_alert(client) -> None:
    """Registering the pre-destroyed hero batch as the RETAILER demo
    account (ph_1) is the simplest real, end-to-end way to get a live
    REENTRY alert (entity_id=ph_1, manufacturer_id=mfr_1) into the
    database for these tests to read back."""
    token = await _token(client, "RETAILER")
    resp = await client.post("/api/batches", json=_REGISTER_B04, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_alerts_requires_authentication(client, seeded):
    resp = await client.get("/api/alerts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_pickup_agent_forbidden_from_alerts(client, seeded):
    token = await _token(client, "PICKUP_AGENT")
    resp = await client.get("/api/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_regulator_sees_the_reentry_alert(client, seeded):
    await _trigger_reentry_alert(client)
    token = await _token(client, "REGULATOR")
    resp = await client.get("/api/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert any(a["type"] == "REENTRY" and a["batchId"] == DESTROYED_BATCH for a in body)


@pytest.mark.asyncio
async def test_retailer_sees_own_entity_alert_but_not_another_entitys(client, seeded, db_session):
    await _trigger_reentry_alert(client)  # entity_id = ph_1
    await alert_service.raise_alert(
        db_session, type_=AlertType.REENTRY, severity=AlertSeverity.critical, batch=None,
        entity_id="ph_9", entity_name="Someone Else's Pharmacy", district="Unknown",
        manufacturer_id=None, rule="test fixture", message="not ph_1's alert",
    )
    await db_session.commit()

    token = await _token(client, "RETAILER")  # ph_1
    resp = await client.get("/api/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert any(a["entityId"] == "ph_1" for a in body)
    assert all(a["entityId"] != "ph_9" for a in body)


@pytest.mark.asyncio
async def test_manufacturer_sees_alerts_on_own_batches(client, seeded):
    await _trigger_reentry_alert(client)  # manufacturer_id = mfr_1
    token = await _token(client, "MANUFACTURER")  # mfr_1
    resp = await client.get("/api/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert any(a["manufacturerId"] == "mfr_1" for a in body)


class _Regulator:
    """Minimal stand-in for `app.models.user.User` — `list_alerts` only
    reads `.role` and `.entity_id` off its `current_user` argument."""

    from app.core.rbac import Role as _Role

    role = _Role.REGULATOR
    entity_id = None


@pytest.mark.asyncio
async def test_ordering_is_category_then_severity_then_recency(seeded, db_session):
    # Deliberately inserted out of priority order.
    other_low = await alert_service.raise_alert(
        db_session, type_=AlertType.QUANTITY_CAP, severity=AlertSeverity.low, batch=None,
        entity_id="ph_1", entity_name="x", district="x", manufacturer_id=None,
        rule="r", message="other/low",
    )
    other_low.drug_category = None
    oncology_high = await alert_service.raise_alert(
        db_session, type_=AlertType.QUANTITY_CAP, severity=AlertSeverity.high, batch=None,
        entity_id="ph_1", entity_name="x", district="x", manufacturer_id=None,
        rule="r", message="oncology/high",
    )
    from app.models.enums import DrugCategory
    oncology_high.drug_category = DrugCategory.oncology
    oncology_critical = await alert_service.raise_alert(
        db_session, type_=AlertType.QUANTITY_CAP, severity=AlertSeverity.critical, batch=None,
        entity_id="ph_1", entity_name="x", district="x", manufacturer_id=None,
        rule="r", message="oncology/critical",
    )
    oncology_critical.drug_category = DrugCategory.oncology
    await db_session.commit()

    rows = await alert_service.list_alerts(db_session, _Regulator())
    ids_in_order = [a.id for a in rows if a.id in {other_low.id, oncology_high.id, oncology_critical.id}]
    assert ids_in_order == [oncology_critical.id, oncology_high.id, other_low.id]


@pytest.mark.asyncio
async def test_get_alert_includes_batch_with_events(client, seeded):
    await _trigger_reentry_alert(client)
    token = await _token(client, "REGULATOR")
    list_resp = await client.get("/api/alerts?type=REENTRY", headers={"Authorization": f"Bearer {token}"})
    alert_id = list_resp.json()[0]["id"]

    resp = await client.get(f"/api/alerts/{alert_id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["batch"]["id"] == DESTROYED_BATCH
    assert len(body["batch"]["events"]) > 0
    assert body["batch"]["events"][-1]["type"] == "REENTRY_BLOCKED"


@pytest.mark.asyncio
async def test_get_alert_not_found(client, seeded):
    token = await _token(client, "REGULATOR")
    resp = await client.get("/api/alerts/alert_does_not_exist", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_alert_forbidden_outside_scope(client, seeded, db_session):
    alert = await alert_service.raise_alert(
        db_session, type_=AlertType.REENTRY, severity=AlertSeverity.critical, batch=None,
        entity_id="ph_1", entity_name="Apollo Pharmacy", district="Chennai",
        manufacturer_id=None, rule="test fixture", message="retailer-only alert",
    )
    await db_session.commit()

    token = await _token(client, "MANUFACTURER")  # not entity_id=ph_1 and no manufacturer_id match
    resp = await client.get(f"/api/alerts/{alert.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_alert_status_requires_regulator(client, seeded, db_session):
    alert = await alert_service.raise_alert(
        db_session, type_=AlertType.REENTRY, severity=AlertSeverity.critical, batch=None,
        entity_id="ph_1", entity_name="x", district="x", manufacturer_id=None,
        rule="r", message="m",
    )
    await db_session.commit()

    token = await _token(client, "DISTRIBUTOR")
    resp = await client.patch(
        f"/api/alerts/{alert.id}/status", json={"status": "INVESTIGATING"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_alert_status_appends_audit_trail(client, seeded, db_session):
    alert = await alert_service.raise_alert(
        db_session, type_=AlertType.REENTRY, severity=AlertSeverity.critical, batch=None,
        entity_id="ph_1", entity_name="x", district="x", manufacturer_id=None,
        rule="r", message="m",
    )
    await db_session.commit()

    token = await _token(client, "REGULATOR")
    resp = await client.patch(
        f"/api/alerts/{alert.id}/status", json={"status": "INVESTIGATING", "officer": "Officer R. Menon"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    get_resp = await client.get(f"/api/alerts/{alert.id}", headers={"Authorization": f"Bearer {token}"})
    body = get_resp.json()
    assert body["status"] == "INVESTIGATING"
    assert len(body["auditTrail"]) == 2
    assert body["auditTrail"][-1]["action"] == "INVESTIGATING"
    assert body["auditTrail"][-1]["officer"] == "Officer R. Menon"


@pytest.mark.asyncio
async def test_update_alert_status_not_found(client, seeded):
    token = await _token(client, "REGULATOR")
    resp = await client.patch(
        "/api/alerts/alert_does_not_exist/status", json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
