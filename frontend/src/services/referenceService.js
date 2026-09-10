import { apiGet } from "../lib/api";

export async function getDistributors() {
  return apiGet("/reference/distributors");
}
export async function getManufacturers() {
  return apiGet("/reference/manufacturers");
}
export async function getFacilities() {
  return apiGet("/reference/facilities");
}
export async function getPharmacies() {
  return apiGet("/reference/pharmacies");
}
export async function getPharmacy(id) {
  return apiGet(`/reference/pharmacies/${id}`);
}
export async function getSales(pharmacyId) {
  // ARCHITECTURE.md §8.8 documents `GET /api/sales?pharmacyId=`, but the
  // backend never implemented it (no route registered — confirmed against
  // app/api/__init__.py) and no page calls this function today. Left as the
  // documented contract call rather than silently reshaped; see the final
  // integration report for how pages/pharmacy.jsx's Sales history is served
  // instead (derived client-side from batch events in services/db.js).
  return apiGet(`/sales?pharmacyId=${encodeURIComponent(pharmacyId)}`);
}
export async function getAgents(distributorId) {
  return apiGet(`/reference/agents${distributorId ? `?distributorId=${encodeURIComponent(distributorId)}` : ""}`);
}
export async function getVehicles(distributorId) {
  return apiGet(`/reference/vehicles${distributorId ? `?distributorId=${encodeURIComponent(distributorId)}` : ""}`);
}

// Additive — not in the original mock contract, but a real, unrestricted,
// read-only endpoint (`GET /api/reference/drugs`). Used to drive a proper
// drug picker on the retail-entry form instead of free-text, so a
// low-literacy user never has to type a category or a price by hand.
export async function getDrugs() {
  return apiGet("/reference/drugs");
}
