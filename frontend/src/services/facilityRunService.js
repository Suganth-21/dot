import { apiGet, apiPost } from "../lib/api";
import { refreshFacilityRuns, refreshBatches, refreshFleet } from "./db";

export async function listFacilityRuns(filter = {}) {
  const params = new URLSearchParams();
  if (filter.distributorId) params.set("distributorId", filter.distributorId);
  if (filter.agentId) params.set("agentId", filter.agentId);
  const qs = params.toString();
  return apiGet(`/facility-runs${qs ? `?${qs}` : ""}`);
}

export async function getFacilityRun(id) {
  return apiGet(`/facility-runs/${encodeURIComponent(id)}`);
}

export async function createFacilityRun({ distributorId, batchIds, facilityId, agentId, vehicleId }) {
  const created = await apiPost("/facility-runs", { distributorId, batchIds, facilityId, agentId, vehicleId });
  await Promise.all([refreshFacilityRuns(), refreshBatches()]);
  return created;
}

export async function dispatchFacilityRun(runId) {
  const res = await apiPost(`/facility-runs/${encodeURIComponent(runId)}/dispatch`, {});
  await Promise.all([refreshFacilityRuns(), refreshFleet()]);
  return res;
}

export async function deliverFacilityRun(runId) {
  const res = await apiPost(`/facility-runs/${encodeURIComponent(runId)}/deliver`, {});
  await Promise.all([refreshFacilityRuns(), refreshBatches()]);
  return res;
}
