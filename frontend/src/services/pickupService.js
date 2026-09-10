import { getState, mutate } from "./db";
import { uid } from "../lib/utils";
import { appendEvent } from "./batchService";
import { notify } from "./notificationService";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

export async function listRoutes(filter = {}) {
  await delay();
  let rows = getState().routes.map((r) => ({ ...r }));
  if (filter.distributorId) rows = rows.filter((r) => r.distributorId === filter.distributorId);
  if (filter.agentId) rows = rows.filter((r) => r.agentId === filter.agentId);
  return rows;
}

export async function getRoute(id) {
  await delay(60);
  const r = getState().routes.find((x) => x.id === id);
  return r ? { ...r } : null;
}

export async function listFleet(distributorId) {
  await delay();
  const s = getState();
  let vehicles = s.vehicles.map((v) => ({ ...v }));
  let agents = s.agents.map((a) => ({ ...a }));
  if (distributorId) {
    vehicles = vehicles.filter((v) => v.distributorId === distributorId);
    agents = agents.filter((a) => a.distributorId === distributorId);
  }
  return { vehicles, agents };
}

export async function createRoute({ distributorId, returnIds, agentId, vehicleId, manualOrder }) {
  await delay();
  let created = null;
  mutate((s) => {
    const dist = s.distributors.find((d) => d.id === distributorId);
    const rets = returnIds.map((id) => s.returns.find((r) => r.id === id)).filter(Boolean);
    const stops = rets.map((r, i) => {
      const p = s.pharmacies.find((x) => x.id === r.pharmacyId);
      return {
        pharmacyId: p.id, pharmacyName: p.name, address: p.address, lat: p.lat, lng: p.lng,
        order: i + 1, status: "PENDING", expectedBatches: 1, returnId: r.id,
      };
    });
    // Respect manual order from the builder, else nearest-neighbour from warehouse.
    let ordered;
    if (manualOrder) {
      ordered = stops.map((st, i) => ({ ...st, order: i + 1 }));
    } else {
      ordered = [];
      let cur = { lat: dist.lat, lng: dist.lng };
      const pool = [...stops];
      while (pool.length) {
        pool.sort((a, b) => dist2(cur, a) - dist2(cur, b));
        const next = pool.shift();
        next.order = ordered.length + 1;
        ordered.push(next);
        cur = next;
      }
    }
    const agent = s.agents.find((a) => a.id === agentId);
    const veh = s.vehicles.find((v) => v.id === vehicleId);
    created = {
      id: uid("route"),
      distributorId,
      agentId,
      agentName: agent?.name,
      vehicleId,
      vehicleReg: veh?.regNo,
      stops: ordered,
      status: "planned",
      createdAt: new Date().toISOString(),
      path: [{ lat: dist.lat, lng: dist.lng }, ...ordered.map((st) => ({ lat: st.lat, lng: st.lng }))],
      segIndex: 0, segT: 0,
      pos: { lat: dist.lat, lng: dist.lng },
      etaMin: ordered.length * 12,
      running: false,
    };
    s.routes.unshift(created);
    rets.forEach((r) => {
      r.status = "SCHEDULED";
      r.routeId = created.id;
    });
    notify("PICKUP_AGENT", "New route assigned", `${ordered.length} stops assigned`, "info", "/agent/today");
  });
  return created;
}

export async function dispatchRoute(routeId) {
  await delay();
  mutate((s) => {
    const r = s.routes.find((x) => x.id === routeId);
    if (!r) return;
    r.running = true;
    r.status = "active";
    if (r.stops[0]) r.stops[0].status = "CURRENT";
    const agent = s.agents.find((a) => a.id === r.agentId);
    const veh = s.vehicles.find((v) => v.id === r.vehicleId);
    if (agent) agent.status = "active";
    if (veh) veh.status = "active";
    notify("RETAILER", "Pickup en route", `${r.vehicleReg} is on the way`, "info", "/pharmacy/returns");
  });
  return { ok: true };
}

export async function agentArrive(routeId, stopIndex) {
  await delay(60);
  mutate((s) => {
    const r = s.routes.find((x) => x.id === routeId);
    if (!r || !r.stops[stopIndex]) return;
    r.stops[stopIndex].status = "ARRIVED";
    const ret = s.returns.find((x) => x.id === r.stops[stopIndex].returnId);
    if (ret) {
      ret.status = "ARRIVED";
      const batch = s.batches.find((b) => b.id === ret.batchId);
      if (batch) appendEvent(batch, "AGENT_ARRIVED", { id: r.agentId, name: r.agentName, role: "PICKUP_AGENT" }, {});
    }
  });
}

export async function agentPickup(routeId, stopIndex, counted) {
  await delay();
  mutate((s) => {
    const r = s.routes.find((x) => x.id === routeId);
    if (!r || !r.stops[stopIndex]) return;
    r.stops[stopIndex].status = "DONE";
    r.stops[stopIndex].counted = counted;
    if (r.stops[stopIndex + 1]) r.stops[stopIndex + 1].status = "CURRENT";
    const ret = s.returns.find((x) => x.id === r.stops[stopIndex].returnId);
    if (ret) {
      ret.status = "PICKED_UP";
      ret.pickedQuantity = counted;
      const batch = s.batches.find((b) => b.id === ret.batchId);
      if (batch) appendEvent(batch, "PICKED_UP", { id: r.agentId, name: r.agentName, role: "PICKUP_AGENT" }, { counted });
      notify("DISTRIBUTOR", "Pickup completed", `${ret.drugName} picked up (${counted} units) — confirm receipt`, "info", `/distributor/returns/${ret.id}`);
    }
  });
}

function dist2(a, b) {
  return (a.lat - b.lat) ** 2 + (a.lng - b.lng) ** 2;
}
