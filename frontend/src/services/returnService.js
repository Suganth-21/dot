import { getState, mutate, emit } from "./db";
import { uid, photoHash } from "../lib/utils";
import { appendEvent } from "./batchService";
import { pushAlert } from "./alertService";
import { notify } from "./notificationService";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

export async function listReturns(filter = {}) {
  await delay();
  let rows = getState().returns.map((r) => ({ ...r }));
  if (filter.pharmacyId) rows = rows.filter((r) => r.pharmacyId === filter.pharmacyId);
  if (filter.distributorId) rows = rows.filter((r) => r.distributorId === filter.distributorId);
  if (filter.status) rows = rows.filter((r) => r.status === filter.status);
  return rows.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
}

export async function getReturn(id) {
  await delay();
  const s = getState();
  const r = s.returns.find((x) => x.id === id);
  if (!r) return null;
  const batch = s.batches.find((b) => b.id === r.batchId);
  const pharmacy = s.pharmacies.find((p) => p.id === r.pharmacyId);
  const distributor = s.distributors.find((d) => d.id === r.distributorId);
  return { ...r, batch: batch ? { ...batch } : null, pharmacy, distributor };
}

export async function createReturn(batchId, data, actor) {
  await delay();
  let created = null;
  mutate((s) => {
    const batch = s.batches.find((b) => b.id === batchId);
    if (!batch) return;
    batch.status = "IN_RETURN";
    batch.holder = { type: "PHARMACY", id: batch.pharmacyId, name: s.pharmacies.find((p) => p.id === batch.pharmacyId)?.name };
    appendEvent(batch, "RETURN_INITIATED", actor, { quantity: data.quantity, reason: data.reason, photoHash: data.photoHash });
    created = {
      id: uid("ret"),
      batchId,
      pharmacyId: batch.pharmacyId,
      distributorId: data.distributorId,
      drugName: batch.drugName,
      category: batch.category,
      quantityClaimed: data.quantity,
      quantityReceived: null,
      reason: data.reason,
      status: "REQUESTED",
      photoHash: data.photoHash || photoHash("ret" + batchId),
      distributorPhotoHash: null,
      createdAt: new Date().toISOString(),
      disputeNotes: "",
      resolutionNotes: "",
      routeId: null,
    };
    s.returns.unshift(created);
    const distName = s.distributors.find((d) => d.id === data.distributorId)?.name;
    notify("DISTRIBUTOR", "New return in inbox", `${batch.drugName} from ${created ? s.pharmacies.find((p) => p.id === batch.pharmacyId)?.name : ""}`, "info", "/distributor/returns/inbox");
    notify("RETAILER", "Return created", `Pickup requested from ${distName}`, "success", `/pharmacy/returns/${created.id}/track`);
  });
  return created;
}

// Distributor dispute gate
export async function distributorReceive(returnId, { quantityReceived, photoHash: ph, notes }) {
  await delay();
  let result = null;
  mutate((s) => {
    const r = s.returns.find((x) => x.id === returnId);
    if (!r) return;
    const batch = s.batches.find((b) => b.id === r.batchId);
    r.quantityReceived = quantityReceived;
    r.distributorPhotoHash = ph || photoHash("distret" + returnId);
    r.distributorNotes = notes || "";
    if (quantityReceived === r.quantityClaimed) {
      r.status = "CONFIRMED";
      if (batch) {
        batch.holder = { type: "DISTRIBUTOR", id: r.distributorId, name: s.distributors.find((d) => d.id === r.distributorId)?.name };
        appendEvent(batch, "DISTRIBUTOR_CONFIRMED", { id: r.distributorId, name: batch.holder.name, role: "DISTRIBUTOR" }, { received: quantityReceived });
      }
      result = { dispute: false };
    } else {
      r.status = "DISPUTED";
      const ph2 = s.pharmacies.find((p) => p.id === r.pharmacyId);
      const alert = pushAlert({
        type: "QUANTITY_MISMATCH",
        severity: "high",
        batchId: r.batchId,
        drugName: r.drugName,
        drugCategory: r.category,
        entityId: r.pharmacyId,
        entityName: ph2?.name,
        district: ph2?.city,
        manufacturerId: batch?.manufacturerId,
        rule: "Distributor received qty ≠ pharmacy claimed qty",
        message: `QUANTITY MISMATCH: ${r.drugName} (${r.batchId}) — claimed ${r.quantityClaimed}, received ${quantityReceived}`,
      });
      notify("REGULATOR", "Quantity mismatch alert", alert.message, "warning", `/regulator/alerts/${alert.id}`);
      notify("RETAILER", "Dispute on your return", `Quantity mismatch on ${r.drugName}`, "warning", `/pharmacy/alerts`);
      result = { dispute: true, alert };
    }
  });
  return result;
}

export async function resolveDispute(returnId, resolutionNotes) {
  await delay();
  mutate((s) => {
    const r = s.returns.find((x) => x.id === returnId);
    if (!r) return;
    r.resolutionNotes = resolutionNotes;
    r.status = "CONFIRMED";
    const batch = s.batches.find((b) => b.id === r.batchId);
    if (batch) {
      batch.holder = { type: "DISTRIBUTOR", id: r.distributorId, name: s.distributors.find((d) => d.id === r.distributorId)?.name };
      appendEvent(batch, "DISPUTE_RESOLVED", { id: r.distributorId, name: batch.holder.name, role: "DISTRIBUTOR" }, { received: r.quantityReceived, notes: resolutionNotes });
    }
    const alert = s.alerts.find((a) => a.batchId === r.batchId && a.type === "QUANTITY_MISMATCH" && a.status !== "CLOSED");
    if (alert) {
      alert.status = "CLOSED";
      alert.auditTrail.push({ action: "RESOLVED_AT_DISTRIBUTOR", officer: "Distributor", ts: new Date().toISOString(), notes: resolutionNotes });
    }
  });
  return { ok: true };
}

export async function forwardReturns(returnIds, actor) {
  await delay();
  mutate((s) => {
    returnIds.forEach((id) => {
      const r = s.returns.find((x) => x.id === id);
      if (!r || r.status !== "CONFIRMED") return;
      r.status = "FORWARDED";
      const batch = s.batches.find((b) => b.id === r.batchId);
      if (batch) {
        appendEvent(batch, "FORWARDED", actor, { to: batch.manufacturerName });
        notify("MANUFACTURER", "Return forwarded", `${batch.drugName} (${batch.id}) awaiting facility pickup`, "info", "/manufacturer/inbox");
      }
    });
  });
  return { ok: true };
}


// Kanban drag: move a return between pipeline stages with sensible side-effects.
export async function setReturnStatus(returnId, status, actor) {
  await delay(60);
  let result = null;
  mutate((s) => {
    const r = s.returns.find((x) => x.id === returnId);
    if (!r || r.status === status) return;
    const batch = s.batches.find((b) => b.id === r.batchId);
    const distName = s.distributors.find((d) => d.id === r.distributorId)?.name;
    if (status === "REQUESTED") {
      r.status = "REQUESTED";
      r.quantityReceived = null;
      r.routeId = null;
    } else if (status === "SCHEDULED") {
      r.status = "SCHEDULED";
    } else if (status === "PICKED_UP") {
      r.status = "PICKED_UP";
      r.pickedQuantity = r.pickedQuantity ?? r.quantityClaimed;
      if (batch && !batch.events.some((e) => e.type === "PICKED_UP")) {
        appendEvent(batch, "PICKED_UP", actor || { id: r.distributorId, name: distName, role: "DISTRIBUTOR" }, { counted: r.quantityClaimed });
      }
    } else if (status === "CONFIRMED") {
      r.status = "CONFIRMED";
      r.quantityReceived = r.quantityReceived ?? r.quantityClaimed;
      if (batch) {
        batch.holder = { type: "DISTRIBUTOR", id: r.distributorId, name: distName };
        if (!batch.events.some((e) => e.type === "DISTRIBUTOR_CONFIRMED")) {
          appendEvent(batch, "DISTRIBUTOR_CONFIRMED", actor || { id: r.distributorId, name: distName, role: "DISTRIBUTOR" }, { received: r.quantityReceived });
        }
      }
    }
    result = { ...r };
  });
  return result;
}
