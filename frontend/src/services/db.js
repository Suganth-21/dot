// Real-backed replacement for the old localStorage mock store. Same public
// shape (`getState()`, `subscribe()`, `emit()`) so `hooks/useDb.js`'s
// `useLive(selector)` — and every component built on it — keeps working
// untouched (ARCHITECTURE.md §9.5, BUILDPHASES.md's frontend swap plan).
//
// The in-memory `state` object is now a client-side cache: populated by
// REST bootstrap on login, kept in sync by a WebSocket connection
// (ARCHITECTURE.md §9) for live pushes, and re-synced by the `refreshX()`
// helpers every other service file calls after a mutation succeeds (there
// is no local fake state left to optimistically mutate — every write goes
// to the server, and these helpers re-fetch the truth).
import { apiPost, getTokens } from "../lib/api";
import { useAuth } from "../store/authStore";
import * as referenceService from "./referenceService";
import * as batchService from "./batchService";
import * as returnService from "./returnService";
import * as pickupService from "./pickupService";
import * as facilityRunService from "./facilityRunService";
import * as alertService from "./alertService";
import * as notificationService from "./notificationService";

function emptySkeleton() {
  return {
    pharmacies: [], distributors: [], agents: [], vehicles: [], manufacturers: [], facilities: [],
    batches: [], returns: [], routes: [], facilityRuns: [], alerts: [], sales: [],
    notifications: { RETAILER: [], DISTRIBUTOR: [], PICKUP_AGENT: [], MANUFACTURER: [], REGULATOR: [] },
    reports: [], patientReports: [],
  };
}

let state = emptySkeleton();
const listeners = new Set();

export function getState() {
  return state;
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let emitTimer = null;
export function emit(immediate = false) {
  if (immediate) {
    listeners.forEach((l) => l());
    return;
  }
  if (emitTimer) return;
  emitTimer = requestAnimationFrame(() => {
    emitTimer = null;
    listeners.forEach((l) => l());
  });
}

// `/api/sales` was never implemented backend-side (ARCHITECTURE.md §8.8
// documents it, but no route exists — see referenceService.js's
// `getSales`). Reconstructed here from each batch's own SALE-type events,
// which GET /api/batches already delivers — authoritative, no guesswork.
function deriveSales(batches) {
  const sales = [];
  for (const b of batches) {
    for (const e of b.events || []) {
      if (e.type === "SALE") {
        sales.push({ id: e.id, batchId: b.id, pharmacyId: b.pharmacyId, units: e.meta?.units ?? 0, ts: e.ts });
      }
    }
  }
  sales.sort((a, b) => new Date(b.ts) - new Date(a.ts));
  return sales;
}

// ---- Per-slice refetch — called by the mutating service functions after a
// write succeeds, and by the WebSocket handler on the matching push type.

export async function refreshReference() {
  const [pharmacies, distributors, manufacturers, facilities] = await Promise.all([
    referenceService.getPharmacies(),
    referenceService.getDistributors(),
    referenceService.getManufacturers(),
    referenceService.getFacilities(),
  ]);
  state.pharmacies = pharmacies;
  state.distributors = distributors;
  state.manufacturers = manufacturers;
  state.facilities = facilities;
  emit(true);
}

export async function refreshFleet() {
  const [agents, vehicles] = await Promise.all([referenceService.getAgents(), referenceService.getVehicles()]);
  state.agents = agents;
  state.vehicles = vehicles;
  emit(true);
}

export async function refreshBatches() {
  const batches = await batchService.listBatches();
  state.batches = batches;
  state.sales = deriveSales(batches);
  emit(true);
}

export async function refreshReturns() {
  state.returns = await returnService.listReturns({});
  emit(true);
}

export async function refreshRoutes() {
  state.routes = await pickupService.listRoutes({});
  emit(true);
  subscribeActiveRoutes();
}

export async function refreshFacilityRuns() {
  const user = useAuth.getState().user;
  // RBAC's facility_runs:read deliberately excludes RETAILER (a pharmacy
  // has no stake in the distributor->facility leg) — same guard shape as
  // refreshAlerts()'s PICKUP_AGENT exclusion below. Without it, a retailer
  // login's bootstrap() throws an unhandled 403 straight into the crash
  // overlay, since Promise.all doesn't isolate one failing fetch.
  if (!user || user.role === "RETAILER") return;
  state.facilityRuns = await facilityRunService.listFacilityRuns({});
  emit(true);
}

export async function refreshAlerts() {
  const user = useAuth.getState().user;
  // §6.5: PICKUP_AGENT has no "Alerts — read" permission at all.
  if (!user || user.role === "PICKUP_AGENT") return;
  state.alerts = await alertService.listAlerts({});
  emit(true);
}

export async function refreshNotifications() {
  const user = useAuth.getState().user;
  if (!user) return;
  const rows = await notificationService.getNotifications(user.role);
  state.notifications = { ...state.notifications, [user.role]: rows };
  emit(true);
}

// Optimistic local patch for the notification bell (mirrors the old mock's
// instant mutation) — notificationService.js calls this before firing the
// real PATCH so the UI updates without waiting on a round trip.
export function patchNotificationsRead(role, id) {
  const list = state.notifications[role];
  if (!list) return;
  list.forEach((n) => {
    if (!id || n.id === id) n.read = true;
  });
  emit(true);
}

async function bootstrap() {
  const user = useAuth.getState().user;
  if (!user) return;
  await Promise.all([
    refreshReference(),
    refreshFleet(),
    refreshBatches(),
    refreshReturns(),
    refreshRoutes(),
    refreshFacilityRuns(),
    refreshAlerts(),
    refreshNotifications(),
  ]);
}

// ---- WebSocket layer (ARCHITECTURE.md §9) ------------------------------

let ws = null;
let wsReconnectTimer = null;
let wsAttempt = 0;
let wsWatchdog = null;
let subscribedChannels = new Set();

function wsUrl() {
  const base = process.env.REACT_APP_WS_URL || "";
  const { accessToken } = getTokens();
  return `${base}?token=${encodeURIComponent(accessToken || "")}`;
}

function channelsForUser(user) {
  const chans = new Set();
  chans.add(`notifications:${user.role}:${user.entityId}`);
  if (user.role === "REGULATOR") {
    chans.add("alerts:regulator");
    chans.add("fleet:all");
  }
  if (user.role === "MANUFACTURER") {
    chans.add(`alerts:manufacturer:${user.entityId}`);
    chans.add("fleet:all");
  }
  if (user.role === "DISTRIBUTOR") {
    chans.add(`fleet:${user.entityId}`);
    chans.add(`returns:${user.entityId}`);
  }
  return chans;
}

function subscribeChannel(channel) {
  if (!ws || ws.readyState !== WebSocket.OPEN || subscribedChannels.has(channel)) return;
  subscribedChannels.add(channel);
  ws.send(JSON.stringify({ action: "subscribe", channel }));
}

function subscribeActiveRoutes() {
  state.routes.filter((r) => r.running || r.status === "active").forEach((r) => subscribeChannel(`route:${r.id}`));
}

function handleWsMessage(raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch (e) {
    return;
  }
  switch (msg.type) {
    case "route.position": {
      const r = state.routes.find((x) => x.id === msg.data.routeId);
      if (r) {
        r.pos = msg.data.pos;
        r.etaMin = msg.data.etaMin;
        const v = state.vehicles.find((x) => x.regNo === msg.data.vehicleReg);
        if (v) {
          v.lat = msg.data.pos.lat;
          v.lng = msg.data.pos.lng;
        }
        emit();
      } else {
        // A route this session has never fetched — created (and possibly
        // already dispatched) by someone else, or on another device,
        // after this tab's own bootstrap — pull it in for real instead of
        // silently dropping the position tick forever.
        refreshRoutes();
      }
      break;
    }
    case "route.stop":
      refreshRoutes();
      refreshReturns();
      break;
    case "facilityrun.position": {
      const r = state.facilityRuns.find((x) => x.id === msg.data.runId);
      if (r) {
        r.pos = msg.data.pos;
        r.etaMin = msg.data.etaMin;
        const v = state.vehicles.find((x) => x.regNo === msg.data.vehicleReg);
        if (v) {
          v.lat = msg.data.pos.lat;
          v.lng = msg.data.pos.lng;
        }
        emit();
      } else {
        refreshFacilityRuns();
      }
      break;
    }
    case "facilityrun.updated":
      refreshFacilityRuns();
      refreshBatches();
      break;
    case "alert.created":
      refreshAlerts();
      break;
    case "notification.created":
      refreshNotifications();
      // A new pickup route or facility run assigned to this session (most
      // often a PICKUP_AGENT, who holds no permanent fleet:* subscription
      // to catch it any other way) always fires a notification too — pull
      // both in so an already-open Today screen picks it up live instead
      // of needing a manual reload mid-demo.
      refreshRoutes();
      refreshFacilityRuns();
      break;
    case "batch.updated":
      refreshBatches();
      break;
    case "returns.updated":
      refreshReturns();
      break;
    default:
      break; // "subscribed" / "unsubscribed" / "error" acks — no cache action
  }
}

function teardownWs() {
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer);
    wsReconnectTimer = null;
  }
  if (wsWatchdog) {
    clearTimeout(wsWatchdog);
    wsWatchdog = null;
  }
  if (ws) {
    ws.onopen = null;
    ws.onmessage = null;
    ws.onclose = null;
    ws.onerror = null;
    try {
      ws.close();
    } catch (e) {
      // ignore
    }
    ws = null;
  }
  subscribedChannels = new Set();
}

function scheduleReconnect() {
  const user = useAuth.getState().user;
  if (!user) return; // logged out — nothing to reconnect for
  wsAttempt += 1;
  const base = Math.min(30000, 1000 * 2 ** (wsAttempt - 1)); // 1s/2s/4s/8s/.../30s cap
  const jitter = base * (0.5 + Math.random() * 0.5);
  wsReconnectTimer = setTimeout(() => {
    // Refetch rather than replay missed messages (ARCHITECTURE.md §9.6) —
    // state is small, refetching cannot desync.
    bootstrap().then(connectWs);
  }, jitter);
}

function connectWs() {
  const user = useAuth.getState().user;
  if (!user) return;
  teardownWs();

  const base = process.env.REACT_APP_WS_URL;
  if (!base) return; // not configured — degrade to REST-only silently

  try {
    ws = new WebSocket(wsUrl());
  } catch (e) {
    scheduleReconnect();
    return;
  }

  let gotAnyMessage = false;

  ws.onopen = () => {
    wsAttempt = 0;
    subscribedChannels = new Set();
    channelsForUser(user).forEach(subscribeChannel);
    subscribeActiveRoutes();
    // ARCHITECTURE.md §9.6 asks for a 30s app-level ping/pong; app/api/ws.py
    // implements no server-initiated heartbeat to answer one, so this is a
    // connect-time watchdog instead: a socket that never says anything back
    // (not even a subscribe ack) within 45s is treated as dead and rebuilt.
    // Documented as a deliberate deviation in the integration report.
    wsWatchdog = setTimeout(() => {
      if (!gotAnyMessage && ws) {
        try {
          ws.close();
        } catch (e) {
          // ignore
        }
      }
    }, 45000);
  };
  ws.onmessage = (evt) => {
    gotAnyMessage = true;
    handleWsMessage(evt.data);
  };
  ws.onclose = () => {
    if (wsWatchdog) clearTimeout(wsWatchdog);
    scheduleReconnect();
  };
  ws.onerror = () => {
    try {
      ws.close();
    } catch (e) {
      // ignore — onclose fires next and drives reconnect
    }
  };
}

// ---- Public lifecycle entry points --------------------------------------
// Names kept identical to the old mock (`startSimulation`, `resetDemo`) so
// App.js and AppShell.jsx — neither of them a `services/*.js` file in
// BUILDPHASES.md's file table — need zero edits (CLAUDE.md rule 3's spirit
// extended to the app shell, not just pages/*.jsx).

let started = false;

// Called once from App.js's mount effect. Kicks off bootstrap+connect
// immediately if a session is already persisted (page reload while logged
// in); otherwise the useAuth subscription below picks it up the moment
// login/demoLogin resolves.
export function startSimulation() {
  if (started) return;
  started = true;
  if (useAuth.getState().user) {
    bootstrap().then(connectWs);
  }
}

// Reacts to every login/logout/account-switch for the lifetime of the
// module (registered once, at import time — safe under React 18
// StrictMode's double effect-invocation since `startSimulation`'s own
// dedupe guard is separate from this).
let currentUserKey = null;
useAuth.subscribe((s) => {
  const user = s.user;
  const key = user ? `${user.role}:${user.entityId}` : null;
  if (key === currentUserKey) return;
  currentUserKey = key;
  teardownWs();
  state = emptySkeleton();
  emit(true);
  if (user) {
    bootstrap().then(connectWs);
  }
});

export async function resetDemo() {
  await apiPost("/demo/reset", {});
  await bootstrap();
}
