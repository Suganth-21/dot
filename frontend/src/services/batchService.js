import { apiGet, apiPost, ApiError } from "../lib/api";
import { refreshBatches } from "./db";

export async function listBatches() {
  return apiGet("/batches");
}

export async function getBatch(id) {
  try {
    return await apiGet(`/batches/${encodeURIComponent(id)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export async function searchAll(q) {
  return apiGet(`/search?q=${encodeURIComponent(q)}`);
}

// Re-entry detection lives server-side (app.services.fraud_service):
// registering an already-DESTROYED batch id is a real, thrown 409
// BATCH_DESTROYED_REENTRY, not a soft 200 — ARCHITECTURE.md §8.2 and
// BUILDPHASES.md's seed/error-convention notes now document this directly
// (the docs previously described a `{reentry: true}` 200 shape; that was
// the mismatch, resolved by updating the docs to match the real,
// already-correct backend behavior, not by reshaping a working backend to
// fit a stale description — the real §10 error table already listed
// re-entry as a 409 case). The caller (pages/pharmacy.jsx's InventoryAdd)
// catches `BATCH_DESTROYED_REENTRY` itself via `onError`.
export async function addBatch(payload, actor, pharmacyId) {
  const res = await apiPost("/batches", payload);
  await refreshBatches();
  return { reentry: false, batch: res.batch, alert: res.alert, quantityCapBreach: res.quantityCapBreach };
}

export async function simulateSale(batchId, units = 1, actor) {
  const batch = await apiPost(`/batches/${encodeURIComponent(batchId)}/sale`, { units });
  await refreshBatches();
  return batch;
}

// Purely local display helper (BUILDPHASES.md "computeStatus stays as a
// display helper only") — the server derives status authoritatively on
// every read; nothing here drives an actual state transition.
export function computeStatus(batch, now = Date.now()) {
  if (batch.status === "DESTROYED" || batch.status === "IN_RETURN") return batch.status;
  const days = Math.round((new Date(batch.expiryDate) - now) / 86400000);
  if (days < 0) return "EXPIRED";
  if (days <= 60) return "EXPIRING_SOON";
  return "ACTIVE";
}
