import { getState } from "./db";

const delay = (ms = 80) => new Promise((r) => setTimeout(r, ms));

export async function getDistributors() {
  await delay();
  return getState().distributors.map((d) => ({ ...d }));
}
export async function getManufacturers() {
  await delay();
  return getState().manufacturers.map((m) => ({ ...m }));
}
export async function getFacilities() {
  await delay();
  return getState().facilities.map((f) => ({ ...f }));
}
export async function getPharmacies() {
  await delay();
  return getState().pharmacies.map((p) => ({ ...p }));
}
export async function getPharmacy(id) {
  await delay();
  return getState().pharmacies.find((p) => p.id === id);
}
export async function getSales(pharmacyId) {
  await delay();
  return getState().sales.filter((s) => s.pharmacyId === pharmacyId).map((s) => ({ ...s }));
}
export async function getAgents(distributorId) {
  await delay();
  return getState().agents.filter((a) => !distributorId || a.distributorId === distributorId).map((a) => ({ ...a }));
}
export async function getVehicles(distributorId) {
  await delay();
  return getState().vehicles.filter((v) => !distributorId || v.distributorId === distributorId).map((v) => ({ ...v }));
}
