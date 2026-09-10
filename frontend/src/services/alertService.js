import { getState, mutate, emit } from "./db";
import { uid } from "../lib/utils";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

export function pushAlert(data) {
  const s = getState();
  const alert = {
    id: uid("alert"),
    ts: new Date().toISOString(),
    status: "OPEN",
    auditTrail: [{ action: "ALERT_FIRED", officer: "System", ts: new Date().toISOString() }],
    ...data,
  };
  s.alerts.unshift(alert);
  return alert;
}

export async function listAlerts(filter = {}) {
  await delay();
  let rows = getState().alerts.map((a) => ({ ...a }));
  if (filter.type) rows = rows.filter((a) => a.type === filter.type);
  if (filter.status) rows = rows.filter((a) => a.status === filter.status);
  if (filter.district) rows = rows.filter((a) => a.district === filter.district);
  if (filter.drugCategory) rows = rows.filter((a) => a.drugCategory === filter.drugCategory);
  if (filter.manufacturerId) rows = rows.filter((a) => a.manufacturerId === filter.manufacturerId);
  // oncology + antibiotics float to top, then severity, then recency
  const sevRank = { critical: 0, high: 1, medium: 2, low: 3 };
  const catRank = { oncology: 0, antibiotics: 1, cardiovascular: 2, other: 3 };
  rows.sort((a, b) => {
    if (catRank[a.drugCategory] !== catRank[b.drugCategory]) return catRank[a.drugCategory] - catRank[b.drugCategory];
    if (sevRank[a.severity] !== sevRank[b.severity]) return sevRank[a.severity] - sevRank[b.severity];
    return new Date(b.ts) - new Date(a.ts);
  });
  return rows;
}

export async function getAlert(id) {
  await delay(60);
  const s = getState();
  const a = s.alerts.find((x) => x.id === id);
  if (!a) return null;
  const batch = s.batches.find((b) => b.id === a.batchId);
  return { ...a, batch: batch ? { ...batch } : null };
}

export async function updateAlertStatus(id, status, officer) {
  await delay();
  mutate((s) => {
    const a = s.alerts.find((x) => x.id === id);
    if (!a) return;
    a.status = status;
    a.auditTrail.push({ action: status, officer: officer || "Officer", ts: new Date().toISOString() });
  });
  return { ok: true };
}

export async function listReports() {
  await delay();
  return getState().reports.map((r) => ({ ...r }));
}

export async function generateReport({ title, region, category }) {
  await delay(400);
  let created = null;
  mutate((s) => {
    created = {
      id: uid("rep"),
      title: title || `CDSCO Compliance Report — ${new Date().toLocaleDateString("en-IN", { month: "short", year: "numeric" })}`,
      region: region || "Tamil Nadu",
      category: category || "all",
      createdAt: new Date().toISOString(),
      size: (1 + Math.random() * 2).toFixed(1) + " MB",
    };
    s.reports.unshift(created);
  });
  return created;
}
