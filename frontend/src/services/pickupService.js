import { apiGet, apiPost } from "../lib/api";
import { refreshRoutes, refreshReturns, refreshFleet } from "./db";

export async function listRoutes(filter = {}) {
  const params = new URLSearchParams();
  if (filter.distributorId) params.set("distributorId", filter.distributorId);
  if (filter.agentId) params.set("agentId", filter.agentId);
  const qs = params.toString();
  return apiGet(`/routes${qs ? `?${qs}` : ""}`);
}

export async function getRoute(id) {
  return apiGet(`/routes/${encodeURIComponent(id)}`);
}

export async function listFleet(distributorId) {
  return apiGet(`/fleet${distributorId ? `?distributorId=${encodeURIComponent(distributorId)}` : ""}`);
}

export async function createRoute({ distributorId, returnIds, agentId, vehicleId, manualOrder }) {
  const created = await apiPost("/routes", {
    distributorId,
    returnIds,
    agentId,
    vehicleId,
    manualOrder,
  });
  await Promise.all([refreshRoutes(), refreshReturns()]);
  return created;
}

export async function dispatchRoute(routeId) {
  const res = await apiPost(`/routes/${encodeURIComponent(routeId)}/dispatch`, {});
  await Promise.all([refreshRoutes(), refreshFleet()]);
  return res;
}

export async function agentArrive(routeId, stopIndex) {
  await apiPost(`/routes/${encodeURIComponent(routeId)}/stops/${stopIndex}/arrive`, {});
  await Promise.all([refreshRoutes(), refreshReturns()]);
}

export async function agentPickup(routeId, stopIndex, counted) {
  await apiPost(`/routes/${encodeURIComponent(routeId)}/stops/${stopIndex}/pickup`, { counted });
  await Promise.all([refreshRoutes(), refreshReturns()]);
}
