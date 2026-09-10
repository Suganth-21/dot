import { shortHash, photoHash, uid, DEMO_NOW } from "../lib/utils";

const day = 86400000;
const now = DEMO_NOW.getTime();

// ---- Reference data ----------------------------------------------------------

export const DRUGS = {
  DOX: { name: "Doxorubicin 50mg", code: "DOX", category: "oncology", price: 4200 },
  CIS: { name: "Cisplatin 50mg", code: "CIS", category: "oncology", price: 3800 },
  CEF: { name: "Cefixime 200mg", code: "CEF", category: "antibiotics", price: 320 },
  MER: { name: "Meropenem 1g Inj", code: "MER", category: "antibiotics", price: 1450 },
  ATO: { name: "Atorvastatin 20mg", code: "ATO", category: "cardiovascular", price: 180 },
  AML: { name: "Amlodipine 5mg", code: "AML", category: "cardiovascular", price: 95 },
  PAR: { name: "Paracetamol 650mg", code: "PAR", category: "other", price: 40 },
  MET: { name: "Metformin 500mg", code: "MET", category: "other", price: 65 },
  OME: { name: "Omeprazole 20mg", code: "OME", category: "other", price: 88 },
};

const PHARMACY_NAMES = [
  ["Apollo Pharmacy — T. Nagar", "Chennai", 13.0418, 80.2341],
  ["MedPlus — Anna Nagar", "Chennai", 13.0878, 80.2101],
  ["Sri Krishna Medicals", "Chennai", 13.0604, 80.2496],
  ["Vijaya Pharma — Velachery", "Chennai", 12.9791, 80.2209],
  ["Guardian Chemists", "Chennai", 13.0067, 80.2570],
  ["Annai Medical Store", "Coimbatore", 11.0168, 76.9558],
  ["Saravana Pharma", "Madurai", 9.9252, 78.1198],
  ["Kaveri Medicals", "Tiruchirappalli", 10.7905, 78.7047],
  ["Bharathi Drug House", "Salem", 11.6643, 78.1460],
  ["Lakshmi Pharmacy — Adyar", "Chennai", 13.0012, 80.2565],
];

const DISTRIBUTOR_NAMES = [
  ["Sunrise Pharma Distributors", "Chennai", 13.0850, 80.2101],
  ["Meridian Medical Logistics", "Chennai", 12.9900, 80.2200],
  ["TN Healthcare Supply Co.", "Coimbatore", 11.0100, 76.9600],
];

const MANUFACTURER_NAMES = [
  ["Cipla Ltd.", "Chennai", 13.1100, 80.1000],
  ["Sun Pharmaceutical Industries", "Chennai", 12.9500, 80.1500],
  ["Dr. Reddy's Laboratories", "Chennai", 13.0500, 80.1800],
  ["Zydus Lifesciences", "Coimbatore", 11.0500, 76.9000],
];

const FACILITY_NAMES = [
  ["Medicare Biomedical Waste Facility", "Gummidipoondi", 13.4080, 80.1100],
  ["EnviroSafe Incineration Unit", "Sriperumbudur", 12.9700, 79.9400],
  ["GreenClean Waste Management", "Maraimalai Nagar", 12.7900, 80.0200],
];

const AGENT_NAMES = ["Ravi Kumar", "Suresh Babu", "Karthik M.", "Anand R.", "Vignesh S.", "Prakash T.", "Manoj K.", "Deepak V."];

// ---- Builders ----------------------------------------------------------------

function makeEvent(batchId, type, actor, tsOffsetDays, meta = {}, gps) {
  const ts = now - tsOffsetDays * day;
  return {
    id: uid("evt"),
    batchId,
    type,
    actor,
    ts: new Date(ts).toISOString(),
    gps: gps || { lat: 13.0827 + (Math.random() - 0.5) * 0.3, lng: 80.2707 + (Math.random() - 0.5) * 0.3 },
    photoHash: photoHash(batchId + type + tsOffsetDays),
    meta,
    prevHash: null,
    hash: null,
  };
}

function chainEvents(events) {
  let prev = "0x0000000000000000";
  return events.map((e) => {
    e.prevHash = prev;
    e.hash = shortHash(prev + e.batchId + e.type + e.ts + e.actor.name + e.photoHash);
    prev = e.hash;
    return e;
  });
}

export function buildSeed() {
  const pharmacies = PHARMACY_NAMES.map((p, i) => ({
    id: `ph_${i + 1}`,
    name: p[0],
    city: p[1],
    lat: p[2],
    lng: p[3],
    address: `${10 + i} ${p[1]} Main Rd, ${p[1]}, Tamil Nadu`,
    licenseNo: `TN-RTL-${20250 + i}`,
    phone: `+91 98${(40000000 + i * 111111).toString().slice(0, 8)}`,
    distributorIds: ["dist_1", "dist_2"],
  }));

  const distributors = DISTRIBUTOR_NAMES.map((d, i) => ({
    id: `dist_${i + 1}`,
    name: d[0],
    city: d[1],
    lat: d[2],
    lng: d[3],
    address: `${d[1]} Wholesale Market, ${d[1]}, Tamil Nadu`,
    licenseNo: `TN-DST-${1200 + i}`,
  }));

  let agentCounter = 0;
  const agents = [];
  const vehicles = [];
  distributors.forEach((d, di) => {
    const nAgents = di === 0 ? 4 : 3;
    for (let a = 0; a < nAgents; a++) {
      agents.push({
        id: `agent_${agents.length + 1}`,
        distributorId: d.id,
        name: AGENT_NAMES[agentCounter++ % AGENT_NAMES.length],
        phone: `+91 90${(43000000 + agents.length * 131313).toString().slice(0, 8)}`,
        status: "idle",
      });
    }
    const nVeh = di === 0 ? 3 : 2;
    for (let v = 0; v < nVeh; v++) {
      vehicles.push({
        id: `veh_${vehicles.length + 1}`,
        distributorId: d.id,
        regNo: `TN ${11 + di} ${String.fromCharCode(65 + v)}${String.fromCharCode(66 + v)} ${1000 + vehicles.length * 37}`,
        status: "idle",
        lat: d.lat,
        lng: d.lng,
      });
    }
  });

  const manufacturers = MANUFACTURER_NAMES.map((m, i) => ({
    id: `mfr_${i + 1}`,
    name: m[0],
    city: m[1],
    lat: m[2],
    lng: m[3],
    address: `${m[1]} Industrial Estate, ${m[1]}, Tamil Nadu`,
    licenseNo: `MFG-${5500 + i}`,
  }));

  const facilities = FACILITY_NAMES.map((f, i) => ({
    id: `fac_${i + 1}`,
    name: f[0],
    city: f[1],
    lat: f[2],
    lng: f[3],
    licenseNo: `BMW-${900 + i}`,
  }));

  // ---- Batches ----
  const batches = [];
  const returns = [];
  const sales = [];
  const alerts = [];

  const drugKeys = Object.keys(DRUGS);

  function pushBatch(cfg) {
    const drug = DRUGS[cfg.drugKey];
    const mfr = manufacturers[cfg.mfrIdx % manufacturers.length];
    const events = [];
    // registered event
    events.push(makeEvent(cfg.id, "REGISTERED", { id: cfg.pharmacyId, name: pharmacies.find((p) => p.id === cfg.pharmacyId)?.name || "Pharmacy", role: "RETAILER" }, cfg.regDaysAgo, { quantity: cfg.initialQty }));
    // sales events
    let sold = cfg.initialQty - cfg.qty;
    let saleChunks = Math.max(0, Math.min(12, Math.round(sold / Math.max(1, Math.ceil(sold / 8)))));
    let remainingSold = sold;
    const ph = pharmacies.find((p) => p.id === cfg.pharmacyId);
    for (let s = 0; s < 10 && remainingSold > 0; s++) {
      const units = Math.max(1, Math.round(remainingSold / (10 - s)));
      const applied = Math.min(units, remainingSold);
      remainingSold -= applied;
      const off = cfg.regDaysAgo - Math.round(((s + 1) / 11) * cfg.regDaysAgo);
      events.push(makeEvent(cfg.id, "SALE", { id: ph.id, name: ph.name, role: "RETAILER" }, off, { units: applied }, { lat: ph.lat, lng: ph.lng }));
      sales.push({ id: uid("sale"), batchId: cfg.id, pharmacyId: ph.id, units: applied, ts: new Date(now - off * day).toISOString() });
    }
    // lifecycle events for in-return / destroyed batches
    if (["IN_RETURN", "DESTROYED"].includes(cfg.status)) {
      const dist = distributors[cfg.distIdx % distributors.length];
      events.push(makeEvent(cfg.id, "RETURN_INITIATED", { id: ph.id, name: ph.name, role: "RETAILER" }, cfg.flowDaysAgo, { quantity: cfg.qty, reason: "EXPIRED" }, { lat: ph.lat, lng: ph.lng }));
      events.push(makeEvent(cfg.id, "PICKUP_ASSIGNED", { id: dist.id, name: dist.name, role: "DISTRIBUTOR" }, cfg.flowDaysAgo - 1, {}, { lat: dist.lat, lng: dist.lng }));
      events.push(makeEvent(cfg.id, "PICKED_UP", { id: agents[cfg.distIdx].id, name: agents[cfg.distIdx].name, role: "PICKUP_AGENT" }, cfg.flowDaysAgo - 2, { counted: cfg.qty }, { lat: ph.lat, lng: ph.lng }));
      events.push(makeEvent(cfg.id, "DISTRIBUTOR_CONFIRMED", { id: dist.id, name: dist.name, role: "DISTRIBUTOR" }, cfg.flowDaysAgo - 3, { received: cfg.qty }, { lat: dist.lat, lng: dist.lng }));
      events.push(makeEvent(cfg.id, "FORWARDED", { id: dist.id, name: dist.name, role: "DISTRIBUTOR" }, cfg.flowDaysAgo - 4, { to: mfr.name }, { lat: dist.lat, lng: dist.lng }));
    }
    if (cfg.status === "DESTROYED") {
      const fac = facilities[cfg.mfrIdx % facilities.length];
      events.push(makeEvent(cfg.id, "FACILITY_SCHEDULED", { id: mfr.id, name: mfr.name, role: "MANUFACTURER" }, cfg.flowDaysAgo - 6, { facility: fac.name }, { lat: mfr.lat, lng: mfr.lng }));
      events.push(makeEvent(cfg.id, "DESTROYED", { id: mfr.id, name: mfr.name, role: "MANUFACTURER" }, cfg.flowDaysAgo - 8, { facility: fac.name, certId: `CERT-${cfg.code}-${2026}` }, { lat: fac.lat, lng: fac.lng }));
    }

    const holder =
      cfg.status === "DESTROYED"
        ? { type: "FACILITY", id: facilities[cfg.mfrIdx % facilities.length].id, name: facilities[cfg.mfrIdx % facilities.length].name }
        : cfg.status === "IN_RETURN"
        ? { type: "DISTRIBUTOR", id: distributors[cfg.distIdx % distributors.length].id, name: distributors[cfg.distIdx % distributors.length].name }
        : { type: "PHARMACY", id: ph.id, name: ph.name };

    batches.push({
      id: cfg.id,
      code: cfg.code,
      drugName: drug.name,
      drugKey: cfg.drugKey,
      category: drug.category,
      unitPrice: drug.price,
      manufacturerId: mfr.id,
      manufacturerName: mfr.name,
      pharmacyId: cfg.pharmacyId,
      mfgDate: new Date(now - cfg.mfgDaysAgo * day).toISOString(),
      expiryDate: new Date(now + cfg.expiryInDays * day).toISOString(),
      initialQuantity: cfg.initialQty,
      quantity: cfg.qty,
      status: cfg.status,
      holder,
      distributorId: distributors[cfg.distIdx % distributors.length].id,
      events: chainEvents(events),
      destroyed: cfg.status === "DESTROYED",
      destroyedDate: cfg.status === "DESTROYED" ? new Date(now - (cfg.flowDaysAgo - 8) * day).toISOString() : null,
      certId: cfg.status === "DESTROYED" ? `CERT-${cfg.code}-2026` : null,
    });
  }

  // The hero demo batch — EXPIRING_SOON at Pharmacy A (ph_1), Doxorubicin, 50 units, mapped to Distributor X (dist_1)
  pushBatch({
    id: "BATCH-DOX-2026-A17", code: "DOX-2026-A17", drugKey: "DOX", pharmacyId: "ph_1",
    mfrIdx: 0, distIdx: 0, initialQty: 50, qty: 50, status: "EXPIRING_SOON",
    mfgDaysAgo: 500, expiryInDays: 22, regDaysAgo: 60, flowDaysAgo: 0,
  });

  // A pre-destroyed doxorubicin batch used for re-entry demo lookups (already destroyed)
  pushBatch({
    id: "BATCH-DOX-2026-B04", code: "DOX-2026-B04", drugKey: "DOX", pharmacyId: "ph_3",
    mfrIdx: 0, distIdx: 0, initialQty: 40, qty: 40, status: "DESTROYED",
    mfgDaysAgo: 620, expiryInDays: -30, regDaysAgo: 120, flowDaysAgo: 40,
  });

  // Generate a spread of batches
  const statusPlan = [
    { status: "ACTIVE", n: 14, expiry: [120, 400] },
    { status: "EXPIRING_SOON", n: 8, expiry: [10, 55] },
    { status: "EXPIRED", n: 5, expiry: [-40, -2] },
    { status: "IN_RETURN", n: 6, expiry: [-25, 10] },
    { status: "DESTROYED", n: 9, expiry: [-90, -20] },
  ];

  let counter = 5;
  statusPlan.forEach((plan) => {
    for (let i = 0; i < plan.n; i++) {
      const drugKey = drugKeys[counter % drugKeys.length];
      const code = `${DRUGS[drugKey].code}-2026-${String.fromCharCode(65 + (counter % 6))}${10 + (counter % 80)}`;
      const initialQty = 40 + ((counter * 7) % 80);
      const soldFactor = plan.status === "ACTIVE" ? 0.4 : plan.status === "EXPIRING_SOON" ? 0.55 : 0.3;
      const qty = plan.status === "DESTROYED" || plan.status === "IN_RETURN"
        ? Math.max(10, Math.round(initialQty * (1 - soldFactor)))
        : Math.max(5, Math.round(initialQty * (1 - soldFactor * Math.random())));
      pushBatch({
        id: `BATCH-${code}`,
        code,
        drugKey,
        pharmacyId: `ph_${1 + (counter % pharmacies.length)}`,
        mfrIdx: counter % manufacturers.length,
        distIdx: counter % distributors.length,
        initialQty,
        qty,
        status: plan.status,
        mfgDaysAgo: 400 + (counter % 200),
        expiryInDays: Math.round(plan.expiry[0] + Math.random() * (plan.expiry[1] - plan.expiry[0])),
        regDaysAgo: 90 + (counter % 120),
        flowDaysAgo: 10 + (counter % 30),
      });
      counter++;
    }
  });

  // ---- Returns (active pipeline) ----
  const inReturnBatches = batches.filter((b) => b.status === "IN_RETURN");
  inReturnBatches.forEach((b, i) => {
    const statusCycle = ["REQUESTED", "ASSIGNED", "EN_ROUTE", "CONFIRMED", "DISPUTED"][i % 5];
    returns.push({
      id: `ret_${i + 1}`,
      batchId: b.id,
      pharmacyId: b.pharmacyId,
      distributorId: b.distributorId,
      drugName: b.drugName,
      category: b.category,
      quantityClaimed: b.quantity,
      quantityReceived: statusCycle === "CONFIRMED" ? b.quantity : statusCycle === "DISPUTED" ? b.quantity - 5 : null,
      reason: ["EXPIRED", "DAMAGED", "RECALL"][i % 3],
      status: statusCycle,
      photoHash: photoHash("ret" + b.id),
      distributorPhotoHash: ["CONFIRMED", "DISPUTED"].includes(statusCycle) ? photoHash("distret" + b.id) : null,
      createdAt: new Date(now - (3 + i) * day).toISOString(),
      disputeNotes: "",
      resolutionNotes: "",
      routeId: null,
    });
  });

  // ---- Active pickup routes with moving vehicles ----
  const routes = [];
  function makeRoute(id, distributorId, agentIdx, vehIdx, phIds, status) {
    const dist = distributors.find((d) => d.id === distributorId);
    const stops = phIds.map((pid, idx) => {
      const p = pharmacies.find((x) => x.id === pid);
      return {
        pharmacyId: pid,
        pharmacyName: p.name,
        address: p.address,
        lat: p.lat,
        lng: p.lng,
        order: idx + 1,
        status: status === "active" ? (idx === 0 ? "DONE" : idx === 1 ? "CURRENT" : "PENDING") : "PENDING",
        expectedBatches: 1 + (idx % 2),
        returnId: returns[idx % returns.length]?.id || null,
      };
    });
    const distAgents = agents.filter((a) => a.distributorId === distributorId);
    const distVeh = vehicles.filter((v) => v.distributorId === distributorId);
    const agent = distAgents[agentIdx % distAgents.length];
    const veh = distVeh[vehIdx % distVeh.length];
    // path: warehouse -> stops
    const path = [{ lat: dist.lat, lng: dist.lng }, ...stops.map((s) => ({ lat: s.lat, lng: s.lng }))];
    routes.push({
      id,
      distributorId,
      agentId: agent.id,
      agentName: agent.name,
      vehicleId: veh.id,
      vehicleReg: veh.regNo,
      stops,
      status, // 'active' | 'planned' | 'completed'
      createdAt: new Date(now - 1 * day).toISOString(),
      path,
      segIndex: status === "active" ? 1 : 0,
      segT: status === "active" ? 0.35 : 0,
      pos: status === "active" ? { lat: (dist.lat + stops[0].lat) / 2, lng: (dist.lng + stops[0].lng) / 2 } : { lat: dist.lat, lng: dist.lng },
      etaMin: 42,
      running: status === "active",
    });
    if (status === "active") {
      agent.status = "active";
      veh.status = "active";
    }
  }
  makeRoute("route_1", "dist_1", 0, 0, ["ph_2", "ph_4", "ph_5", "ph_10", "ph_3", "ph_1", "ph_9"], "active");
  makeRoute("route_2", "dist_2", 0, 0, ["ph_6", "ph_8", "ph_7"], "active");

  // ---- Alerts (fired re-entry / mismatch) ----
  const destroyedBatches = batches.filter((b) => b.status === "DESTROYED");
  const alertSeed = [
    { batch: destroyedBatches[0], type: "REENTRY", sev: "critical", rule: "Batch marked DESTROYED re-registered at a pharmacy", ph: "ph_7" },
    { batch: destroyedBatches[1], type: "REENTRY", sev: "critical", rule: "Batch marked DESTROYED re-registered at a pharmacy", ph: "ph_9" },
    { batch: destroyedBatches[2], type: "QUANTITY_MISMATCH", sev: "high", rule: "Distributor received qty < pharmacy claimed qty", ph: "ph_4" },
    { batch: destroyedBatches[3], type: "CERT_MISMATCH", sev: "medium", rule: "Destruction certificate batch list mismatch", ph: "ph_5" },
    { batch: destroyedBatches[4], type: "REENTRY", sev: "critical", rule: "Batch marked DESTROYED re-registered at a pharmacy", ph: "ph_6" },
  ];
  alertSeed.forEach((a, i) => {
    if (!a.batch) return;
    const ph = pharmacies.find((p) => p.id === a.ph);
    alerts.push({
      id: `alert_${i + 1}`,
      type: a.type,
      severity: a.sev,
      batchId: a.batch.id,
      drugName: a.batch.drugName,
      drugCategory: a.batch.category,
      entityId: a.ph,
      entityName: ph.name,
      district: ph.city,
      manufacturerId: a.batch.manufacturerId,
      ts: new Date(now - (i * 6 + 2) * 3600000).toISOString(),
      status: i === 0 ? "OPEN" : i === 1 ? "INVESTIGATING" : "OPEN",
      rule: a.rule,
      message: `${a.type === "REENTRY" ? "Destroyed batch reappeared" : a.type === "QUANTITY_MISMATCH" ? "Quantity mismatch" : "Certificate mismatch"} — ${a.batch.drugName} (${a.batch.id}) at ${ph.name}`,
      auditTrail: [
        { action: "ALERT_FIRED", officer: "System", ts: new Date(now - (i * 6 + 2) * 3600000).toISOString() },
      ],
    });
  });

  // ---- Notifications per role ----
  const notifications = {
    RETAILER: [],
    DISTRIBUTOR: [],
    PICKUP_AGENT: [],
    MANUFACTURER: [],
    REGULATOR: [],
  };
  function notify(role, title, body, kind = "info", link) {
    notifications[role].unshift({ id: uid("ntf"), title, body, kind, link, ts: new Date(now - Math.random() * 3600000).toISOString(), read: false });
  }
  notify("RETAILER", "Batch expiring soon", "BATCH-DOX-2026-A17 (Doxorubicin) expires in 22 days", "warning", "/pharmacy/inventory/BATCH-DOX-2026-A17");
  notify("RETAILER", "Pickup scheduled", "Sunrise Pharma will pick up 2 returns today", "info", "/pharmacy/returns");
  notify("DISTRIBUTOR", "New return in inbox", "Lakshmi Pharmacy initiated a return", "info", "/distributor/returns/inbox");
  notify("DISTRIBUTOR", "Dispute opened", "Quantity mismatch on a confirmed return", "warning", "/distributor/disputes");
  notify("MANUFACTURER", "Re-entry alert", "A destroyed batch reappeared on a shelf", "danger", "/manufacturer/dashboard");
  notify("REGULATOR", "Critical re-entry alert", alerts[0]?.message || "Re-entry detected", "danger", "/regulator/alerts");
  notify("PICKUP_AGENT", "Route assigned", "Route 4 — 7 stops assigned to you", "info", "/agent/today");

  const reports = [
    { id: "rep_1", title: "CDSCO Monthly Compliance — Aug 2026", region: "Tamil Nadu", category: "all", createdAt: new Date(now - 5 * day).toISOString(), size: "2.1 MB" },
    { id: "rep_2", title: "Oncology Returns Audit — Q2 2026", region: "Chennai", category: "oncology", createdAt: new Date(now - 18 * day).toISOString(), size: "1.4 MB" },
  ];

  const patientReports = [];

  return {
    version: 3,
    pharmacies,
    distributors,
    agents,
    vehicles,
    manufacturers,
    facilities,
    batches,
    returns,
    routes,
    alerts,
    sales,
    notifications,
    reports,
    patientReports,
  };
}
