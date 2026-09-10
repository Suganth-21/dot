import { apiGet, apiPatch, apiPost } from "../lib/api";
import { refreshAlerts } from "./db";

// pushAlert is gone — alerts are raised server-side only (fraud/re-entry/
// quantity-cap/dispute logic), never client-constructed (CLAUDE.md rule 2).

export async function listAlerts(filter = {}) {
  const params = new URLSearchParams();
  if (filter.type) params.set("type", filter.type);
  if (filter.status) params.set("status", filter.status);
  if (filter.district) params.set("district", filter.district);
  if (filter.drugCategory) params.set("drugCategory", filter.drugCategory);
  if (filter.manufacturerId) params.set("manufacturerId", filter.manufacturerId);
  const qs = params.toString();
  return apiGet(`/alerts${qs ? `?${qs}` : ""}`);
}

export async function getAlert(id) {
  return apiGet(`/alerts/${encodeURIComponent(id)}`);
}

export async function updateAlertStatus(id, status, officer) {
  const res = await apiPatch(`/alerts/${encodeURIComponent(id)}/status`, { status, officer });
  await refreshAlerts();
  return res;
}

export async function listReports() {
  return apiGet("/reports");
}

export async function generateReport({ title, region, category }) {
  return apiPost("/reports", { title, region, category });
}
