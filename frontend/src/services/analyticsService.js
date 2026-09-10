import { apiGet } from "../lib/api";

export async function pharmacyStats(pharmacyId) {
  return apiGet(`/analytics/pharmacy/${encodeURIComponent(pharmacyId)}/stats`);
}
export async function pharmacySparkline(pharmacyId) {
  return apiGet(`/analytics/pharmacy/${encodeURIComponent(pharmacyId)}/sparkline`);
}
export async function pharmacyAnalytics(pharmacyId) {
  return apiGet(`/analytics/pharmacy/${encodeURIComponent(pharmacyId)}`);
}
export async function distributorStats(distributorId) {
  return apiGet(`/analytics/distributor/${encodeURIComponent(distributorId)}/stats`);
}
export async function distributorAnalytics(distributorId) {
  return apiGet(`/analytics/distributor/${encodeURIComponent(distributorId)}`);
}
export async function manufacturerStats(manufacturerId) {
  return apiGet(`/analytics/manufacturer/${encodeURIComponent(manufacturerId)}/stats`);
}
export async function manufacturerAnalytics(manufacturerId) {
  return apiGet(`/analytics/manufacturer/${encodeURIComponent(manufacturerId)}`);
}
export async function regulatorStats() {
  return apiGet("/analytics/regulator/stats");
}
export async function regulatorAnalytics() {
  return apiGet("/analytics/regulator");
}
