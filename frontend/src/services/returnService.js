import { apiGet, apiPost, apiPatch } from "../lib/api";
import { refreshReturns, refreshBatches, refreshAlerts } from "./db";

export async function listReturns(filter = {}) {
  const params = new URLSearchParams();
  if (filter.pharmacyId) params.set("pharmacyId", filter.pharmacyId);
  if (filter.distributorId) params.set("distributorId", filter.distributorId);
  if (filter.status) params.set("status", filter.status);
  const qs = params.toString();
  return apiGet(`/returns${qs ? `?${qs}` : ""}`);
}

export async function getReturn(id) {
  return apiGet(`/returns/${encodeURIComponent(id)}`);
}

export async function createReturn(batchId, data, actor) {
  const created = await apiPost("/returns", {
    batchId,
    quantity: data.quantity,
    distributorId: data.distributorId,
    reason: data.reason,
    photoHash: data.photoHash,
  });
  await Promise.all([refreshReturns(), refreshBatches()]);
  return created;
}

// Distributor dispute gate — a mismatch is still a 200 `{dispute: true,
// alert}` (ARCHITECTURE.md §7.1 / BUILDPHASES.md error conventions), never a
// thrown error; the refusal happens later, on forward/resolve of a
// DISPUTED return.
export async function distributorReceive(returnId, { quantityReceived, photoHash: ph, notes }) {
  const res = await apiPatch(`/returns/${encodeURIComponent(returnId)}/receive`, {
    quantityReceived,
    photoHash: ph,
    notes,
  });
  await Promise.all([refreshReturns(), refreshBatches(), refreshAlerts()]);
  return res;
}

export async function resolveDispute(returnId, resolutionNotes) {
  const res = await apiPatch(`/returns/${encodeURIComponent(returnId)}/resolve`, { resolutionNotes });
  await Promise.all([refreshReturns(), refreshBatches(), refreshAlerts()]);
  return res;
}

export async function forwardReturns(returnIds, actor) {
  const res = await apiPost("/returns/forward", { returnIds });
  await Promise.all([refreshReturns(), refreshBatches()]);
  return res;
}

// Kanban drag: move a return between pipeline stages.
export async function setReturnStatus(returnId, status, actor) {
  const res = await apiPatch(`/returns/${encodeURIComponent(returnId)}/status`, { status });
  await Promise.all([refreshReturns(), refreshBatches()]);
  return res;
}
