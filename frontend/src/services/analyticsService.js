import { getState } from "./db";
import { DEMO_NOW } from "../lib/utils";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function lastMonths(n) {
  const out = [];
  const d = new Date(DEMO_NOW);
  for (let i = n - 1; i >= 0; i--) {
    const m = new Date(d.getFullYear(), d.getMonth() - i, 1);
    out.push(`${MONTHS[m.getMonth()]} '${String(m.getFullYear()).slice(2)}`);
  }
  return out;
}

function seededSeries(labels, base, spread, seed = 1) {
  let x = seed * 9973;
  return labels.map((l, i) => {
    x = (x * 1103515245 + 12345) & 0x7fffffff;
    const r = (x % 1000) / 1000;
    return { label: l, value: Math.round(base + spread * r + i * (spread * 0.05)) };
  });
}

export async function pharmacyStats(pharmacyId) {
  await delay();
  const s = getState();
  const batches = s.batches.filter((b) => b.pharmacyId === pharmacyId);
  const now = Date.now();
  const inWindow = (b, days) => {
    const d = Math.round((new Date(b.expiryDate) - now) / 86400000);
    return d >= 0 && d <= days && b.status !== "DESTROYED" && b.status !== "IN_RETURN";
  };
  const rets = s.returns.filter((r) => r.pharmacyId === pharmacyId);
  return {
    activeBatches: batches.filter((b) => ["ACTIVE", "EXPIRING_SOON"].includes(b.status)).length,
    expiring30: batches.filter((b) => inWindow(b, 30)).length,
    expiring60: batches.filter((b) => inWindow(b, 60)).length,
    pendingReturns: rets.filter((r) => !["FORWARDED", "CONFIRMED"].includes(r.status)).length,
    disputes: rets.filter((r) => r.status === "DISPUTED").length,
  };
}

export async function pharmacySparkline(pharmacyId) {
  await delay(60);
  const labels = Array.from({ length: 30 }, (_, i) => i);
  return seededSeries(labels, 12, 20, pharmacyId.length).map((d, i) => ({ day: i, value: d.value }));
}

export async function pharmacyAnalytics(pharmacyId) {
  await delay();
  const s = getState();
  const batches = s.batches.filter((b) => b.pharmacyId === pharmacyId);
  const months = lastMonths(12);
  const monthlySales = seededSeries(months, 400, 500, pharmacyId.length).map((d) => ({ month: d.label, units: d.value }));
  const drugTotals = {};
  s.sales.filter((x) => x.pharmacyId === pharmacyId).forEach((x) => {
    const b = s.batches.find((bb) => bb.id === x.batchId);
    if (b) drugTotals[b.drugName] = (drugTotals[b.drugName] || 0) + x.units;
  });
  const topDrugs = Object.entries(drugTotals).sort((a, b) => b[1] - a[1]).slice(0, 10).map(([name, units]) => ({ name, units }));
  const composition = [
    { name: "Active", value: batches.filter((b) => b.status === "ACTIVE").length, color: "#3fbf9a" },
    { name: "Expiring Soon", value: batches.filter((b) => b.status === "EXPIRING_SOON").length, color: "#e0a53d" },
    { name: "In Return", value: batches.filter((b) => b.status === "IN_RETURN").length, color: "#5b6cff" },
    { name: "Expired", value: batches.filter((b) => b.status === "EXPIRED").length, color: "#e0655b" },
  ];
  // heatmap day x hour
  const heatmap = [];
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  days.forEach((d, di) => {
    for (let h = 8; h <= 21; h++) {
      const busy = (h >= 10 && h <= 13) || (h >= 17 && h <= 20);
      const base = busy ? 8 : 2;
      heatmap.push({ day: d, hour: h, value: Math.round(base + ((di * 7 + h) % 6) + (di === 5 ? 4 : 0)) });
    }
  });
  const expiryByMonth = lastMonths(12).map((m, i) => ({
    month: m,
    oncology: (i * 3) % 7,
    antibiotics: (i * 5) % 9,
    cardiovascular: (i * 2) % 6,
    other: (i * 4) % 8,
  }));
  const rets = s.returns.filter((r) => r.pharmacyId === pharmacyId);
  return {
    monthlySales, topDrugs, composition, heatmap, expiryByMonth,
    kpis: {
      returnsYTD: rets.length + 14,
      valueReturned: rets.reduce((acc, r) => {
        const b = s.batches.find((bb) => bb.id === r.batchId);
        return acc + (b ? b.unitPrice * r.quantityClaimed : 0);
      }, 45000),
      disputeRate: rets.length ? Math.round((rets.filter((r) => r.status === "DISPUTED").length / rets.length) * 100) : 4,
    },
  };
}

export async function distributorStats(distributorId) {
  await delay();
  const s = getState();
  const rets = s.returns.filter((r) => r.distributorId === distributorId);
  const routes = s.routes.filter((r) => r.distributorId === distributorId);
  return {
    pendingPickups: rets.filter((r) => ["REQUESTED", "SCHEDULED"].includes(r.status)).length,
    pendingConfirmations: rets.filter((r) => r.status === "PICKED_UP").length,
    openDisputes: rets.filter((r) => r.status === "DISPUTED").length,
    readyToForward: rets.filter((r) => r.status === "CONFIRMED").length,
    activeVehicles: routes.filter((r) => r.running).length,
  };
}

export async function distributorAnalytics(distributorId) {
  await delay();
  const s = getState();
  const weeks = Array.from({ length: 12 }, (_, i) => `W${i + 1}`);
  const weekly = seededSeries(weeks, 8, 18, distributorId.length).map((d) => ({ week: d.label, returns: d.value }));
  const byPharmacy = s.pharmacies.slice(0, 15).map((p, i) => ({
    name: p.name.split(" ")[0] + " " + (p.name.split(" ")[1] || ""),
    returns: 3 + ((i * 7) % 20),
  })).sort((a, b) => b.returns - a.returns);
  const funnel = [
    { stage: "Requested", value: 120 },
    { stage: "Scheduled", value: 104 },
    { stage: "Picked Up", value: 92 },
    { stage: "Confirmed", value: 78 },
    { stage: "Forwarded", value: 71 },
  ];
  const disputeFreq = s.pharmacies.slice(0, 10).map((p, i) => ({ name: p.name.split(" ")[0], disputes: (i * 3) % 6 }));
  const heat = s.pharmacies.map((p) => ({ lat: p.lat, lng: p.lng, weight: 0.3 + ((p.id.length * 3) % 7) / 10 }));
  return {
    weekly, byPharmacy, funnel, disputeFreq, heat,
    kpis: { avgCompletion: "3.2 days", disputeRate: 9, onTime: 94 },
  };
}

export async function manufacturerStats(manufacturerId) {
  await delay();
  const s = getState();
  const batches = s.batches.filter((b) => b.manufacturerId === manufacturerId);
  const alerts = s.alerts.filter((a) => a.manufacturerId === manufacturerId);
  return {
    awaitingPickup: s.returns.filter((r) => r.status === "FORWARDED").length,
    certsPending: batches.filter((b) => b.scheduledFacility && b.status !== "DESTROYED").length,
    destroyedThisMonth: batches.filter((b) => b.status === "DESTROYED").length,
    activeRecalls: 1,
    alertsOnBatches: alerts.length,
  };
}

export async function manufacturerAnalytics(manufacturerId) {
  await delay();
  const s = getState();
  const months = lastMonths(24);
  const destroyed = seededSeries(months, 5, 25, manufacturerId.length).map((d) => ({ month: d.label, count: d.value }));
  const drugVol = {};
  s.batches.filter((b) => b.manufacturerId === manufacturerId).forEach((b) => {
    drugVol[b.drugName] = (drugVol[b.drugName] || 0) + b.initialQuantity - b.quantity;
  });
  const topDrugs = Object.entries(drugVol).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, v]) => ({ name, value: v }));
  const reentry = lastMonths(12).map((m, i) => ({ month: m, alerts: (i * 2) % 5 }));
  const bubbles = s.pharmacies.map((p, i) => ({ lat: p.lat, lng: p.lng, city: p.city, value: 5 + ((i * 11) % 40) }));
  // Sankey-ish flow data (nodes/links)
  const flow = {
    nodes: [
      ...s.pharmacies.slice(0, 4).map((p) => ({ name: p.name.split(" ")[0] })),
      ...s.distributors.map((d) => ({ name: d.name.split(" ")[0] })),
      ...s.facilities.map((f) => ({ name: f.name.split(" ")[0] })),
    ],
  };
  return {
    destroyed, topDrugs, reentry, bubbles, flow,
    kpis: { complianceRate: 91, valueDestroyed: 1840000, avgChain: "4.1 days" },
  };
}

export async function regulatorStats() {
  await delay();
  const s = getState();
  return {
    inPipeline: s.batches.filter((b) => b.status === "IN_RETURN").length,
    destroyedThisWeek: s.batches.filter((b) => b.status === "DESTROYED").length,
    activeAlerts: s.alerts.filter((a) => !["CLOSED"].includes(a.status)).length,
    oldDisputes: s.returns.filter((r) => r.status === "DISPUTED").length,
  };
}

export async function regulatorAnalytics() {
  await delay();
  const s = getState();
  const months = lastMonths(12);
  const national = months.map((m, i) => ({
    month: m,
    returns: 200 + i * 12 + ((i * 37) % 40),
    destroyed: 160 + i * 10 + ((i * 23) % 30),
    alerts: 8 + ((i * 5) % 12),
  }));
  const byCategory = months.slice(-6).map((m, i) => ({
    month: m,
    oncology: 20 + (i * 3) % 12,
    antibiotics: 30 + (i * 5) % 15,
    cardiovascular: 25 + (i * 4) % 10,
    other: 40 + (i * 6) % 20,
  }));
  const districts = [
    { district: "Chennai", compliance: 92 }, { district: "Coimbatore", compliance: 85 },
    { district: "Madurai", compliance: 78 }, { district: "Trichy", compliance: 88 },
    { district: "Salem", compliance: 74 }, { district: "Tirunelveli", compliance: 81 },
  ];
  const timeToClose = Array.from({ length: 12 }, (_, i) => ({ week: `W${i + 1}`, days: 5 + ((i * 3) % 5) }));
  // fraud network graph
  const nodes = [];
  const links = [];
  const entitiesInAlerts = {};
  s.alerts.forEach((a) => {
    entitiesInAlerts[a.entityId] = (entitiesInAlerts[a.entityId] || 0) + 1;
    if (a.manufacturerId) entitiesInAlerts[a.manufacturerId] = (entitiesInAlerts[a.manufacturerId] || 0) + 1;
  });
  const ids = Object.keys(entitiesInAlerts);
  ids.forEach((id) => {
    const ent = s.pharmacies.find((p) => p.id === id) || s.manufacturers.find((m) => m.id === id) || { name: id };
    nodes.push({ id, name: ent.name?.split(" ")[0] || id, weight: entitiesInAlerts[id] });
  });
  for (let i = 0; i < ids.length - 1; i++) {
    links.push({ source: ids[i], target: ids[i + 1], value: 1 + (i % 3) });
  }
  return {
    national, byCategory, districts, timeToClose,
    network: { nodes, links },
    kpis: {
      nationalCompliance: 87,
      investigations: s.alerts.filter((a) => a.status === "INVESTIGATING").length + 3,
      resolved: s.alerts.filter((a) => a.status === "CLOSED").length + 12,
      flaggedValue: 3250000,
    },
  };
}
