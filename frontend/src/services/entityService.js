import { getState } from "./db";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

function scoreEntity(s, entity, type) {
  const alertsOn = s.alerts.filter((a) => a.entityId === entity.id).length;
  let returnRate, disputeRate;
  if (type === "pharmacy") {
    const rets = s.returns.filter((r) => r.pharmacyId === entity.id);
    const disputes = rets.filter((r) => r.status === "DISPUTED" || r.resolutionNotes).length;
    returnRate = rets.length;
    disputeRate = rets.length ? Math.round((disputes / rets.length) * 100) : 0;
  } else {
    returnRate = 0;
    disputeRate = 0;
  }
  let score = 100 - alertsOn * 12 - disputeRate * 0.4;
  score = Math.max(20, Math.min(100, Math.round(score)));
  const risk = score >= 80 ? "LOW" : score >= 55 ? "MEDIUM" : "HIGH";
  return { score, risk, alertsOn, returnRate, disputeRate };
}

export async function listEntities() {
  await delay();
  const s = getState();
  const rows = [];
  s.pharmacies.forEach((p) => rows.push({ ...p, type: "PHARMACY", ...scoreEntity(s, p, "pharmacy") }));
  s.distributors.forEach((d) => rows.push({ ...d, type: "DISTRIBUTOR", ...scoreEntity(s, d, "distributor") }));
  s.manufacturers.forEach((m) => rows.push({ ...m, type: "MANUFACTURER", ...scoreEntity(s, m, "manufacturer") }));
  return rows;
}

export async function getEntity(id) {
  await delay();
  const s = getState();
  const p = s.pharmacies.find((x) => x.id === id);
  const d = s.distributors.find((x) => x.id === id);
  const m = s.manufacturers.find((x) => x.id === id);
  const entity = p || d || m;
  if (!entity) return null;
  const type = p ? "PHARMACY" : d ? "DISTRIBUTOR" : "MANUFACTURER";
  const stats = scoreEntity(s, entity, type.toLowerCase());
  const alerts = s.alerts.filter((a) => a.entityId === id);
  const batches = s.batches.filter((b) => b.pharmacyId === id || b.manufacturerId === id || b.distributorId === id);
  return { ...entity, type, ...stats, alerts, batchCount: batches.length };
}
