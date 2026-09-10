import { getState, mutate, emit } from "./db";
import { shortHash, photoHash, uid } from "../lib/utils";
import { pushAlert } from "./alertService";
import { notify } from "./notificationService";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

export function appendEvent(batch, type, actor, meta = {}, gps) {
  const prev = batch.events.length ? batch.events[batch.events.length - 1].hash : "0x0000000000000000";
  const ts = new Date().toISOString();
  const ph = photoHash(batch.id + type + ts);
  const evt = {
    id: uid("evt"),
    batchId: batch.id,
    type,
    actor,
    ts,
    gps: gps || { lat: 13.0827, lng: 80.2707 },
    photoHash: ph,
    meta,
    prevHash: prev,
    hash: shortHash(prev + batch.id + type + ts + actor.name + ph),
  };
  batch.events.push(evt);
  return evt;
}

export async function listBatches() {
  await delay();
  return getState().batches.map((b) => ({ ...b }));
}

export async function getBatch(id) {
  await delay();
  const b = getState().batches.find((x) => x.id === id || x.code === id);
  return b ? { ...b } : null;
}

export async function searchAll(q) {
  await delay(60);
  const s = getState();
  const term = q.trim().toLowerCase();
  if (!term) return [];
  const results = [];
  s.batches.forEach((b) => {
    if (b.id.toLowerCase().includes(term) || b.drugName.toLowerCase().includes(term)) {
      results.push({ type: "batch", id: b.id, title: b.drugName, subtitle: b.id, status: b.status });
    }
  });
  s.pharmacies.forEach((p) => {
    if (p.name.toLowerCase().includes(term)) results.push({ type: "pharmacy", id: p.id, title: p.name, subtitle: p.city });
  });
  return results.slice(0, 12);
}

// Re-entry detection lives here: registering a DESTROYED batch fires a critical alert.
export async function addBatch(payload, actor, pharmacyId) {
  await delay();
  const s = getState();
  const existing = s.batches.find((b) => b.id === payload.batchId || b.code === payload.batchId);

  if (existing && existing.status === "DESTROYED") {
    const ph = s.pharmacies.find((p) => p.id === pharmacyId);
    const alert = pushAlert({
      type: "REENTRY",
      severity: "critical",
      batchId: existing.id,
      drugName: existing.drugName,
      drugCategory: existing.category,
      entityId: pharmacyId,
      entityName: ph?.name || "Unknown pharmacy",
      district: ph?.city || "Unknown",
      manufacturerId: existing.manufacturerId,
      rule: "Batch marked DESTROYED re-registered at a pharmacy",
      message: `RE-ENTRY: Destroyed batch ${existing.id} (${existing.drugName}) was scanned for registration at ${ph?.name || "a pharmacy"}`,
    });
    appendEvent(existing, "REENTRY_BLOCKED", actor, { attemptedAt: ph?.name });
    notify("REGULATOR", "Critical re-entry alert", alert.message, "danger", `/regulator/alerts/${alert.id}`);
    notify("MANUFACTURER", "Re-entry on your batch", alert.message, "danger", `/manufacturer/batches/${existing.id}`);
    emit(true);
    return { reentry: true, alert, batch: { ...existing } };
  }

  // Normal registration
  const batch = existing || {
    id: payload.batchId,
    code: payload.batchId.replace("BATCH-", ""),
    drugName: payload.drugName,
    drugKey: payload.drugKey || "OTH",
    category: payload.category || "other",
    unitPrice: payload.unitPrice || 100,
    manufacturerId: payload.manufacturerId || "mfr_1",
    manufacturerName: payload.manufacturerName || "Unknown",
    pharmacyId,
    mfgDate: payload.mfgDate,
    expiryDate: payload.expiryDate,
    initialQuantity: payload.quantity,
    quantity: payload.quantity,
    status: "ACTIVE",
    holder: { type: "PHARMACY", id: pharmacyId, name: s.pharmacies.find((p) => p.id === pharmacyId)?.name },
    distributorId: "dist_1",
    events: [],
    destroyed: false,
  };
  appendEvent(batch, "REGISTERED", actor, { quantity: payload.quantity });
  if (!existing) s.batches.unshift(batch);
  notify("RETAILER", "Batch registered", `${payload.drugName} — ${payload.quantity} units added`, "success");
  emit(true);
  return { reentry: false, batch: { ...batch } };
}

export async function simulateSale(batchId, units = 1, actor) {
  let out = null;
  mutate((s) => {
    const b = s.batches.find((x) => x.id === batchId);
    if (!b || b.quantity < units) return;
    b.quantity -= units;
    appendEvent(b, "SALE", actor || { id: b.pharmacyId, name: b.holder?.name || "Pharmacy", role: "RETAILER" }, { units });
    s.sales.unshift({ id: uid("sale"), batchId, pharmacyId: b.pharmacyId, units, ts: new Date().toISOString() });
    out = { ...b };
  });
  return out;
}

export function computeStatus(batch, now = Date.now()) {
  if (batch.status === "DESTROYED" || batch.status === "IN_RETURN") return batch.status;
  const days = Math.round((new Date(batch.expiryDate) - now) / 86400000);
  if (days < 0) return "EXPIRED";
  if (days <= 60) return "EXPIRING_SOON";
  return "ACTIVE";
}
