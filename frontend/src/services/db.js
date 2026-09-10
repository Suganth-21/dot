import { buildSeed } from "./seed";
import { lerp } from "../lib/utils";

const STORAGE_KEY = "dot_demo_state_v3";
const SEED_VERSION = 3;

let state = null;
const listeners = new Set();

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.version === SEED_VERSION) return parsed;
    }
  } catch (e) {
    // ignore
  }
  const seed = buildSeed();
  persist(seed);
  return seed;
}

let saveTimer = null;
function persist(s) {
  try {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    }, 200);
  } catch (e) {
    // ignore quota
  }
}

export function getState() {
  if (!state) state = load();
  return state;
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

let emitTimer = null;
export function emit(immediate = false) {
  persist(state);
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

export function mutate(fn) {
  fn(getState());
  emit();
}

export function resetDemo() {
  const seed = buildSeed();
  state = seed;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(seed));
  } catch (e) {}
  emit(true);
}

// Cross-tab sync: when another tab writes state, reload and notify listeners.
if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key === STORAGE_KEY && e.newValue) {
      try {
        const parsed = JSON.parse(e.newValue);
        if (parsed && parsed.version === SEED_VERSION) {
          state = parsed;
          listeners.forEach((l) => l());
        }
      } catch (err) {}
    }
  });
}

// ---- Simulation loop: move active-route vehicles, keep pharmacy tracking + fleet maps live
let simStarted = false;
export function startSimulation() {
  if (simStarted) return;
  simStarted = true;
  setInterval(() => {
    const s = getState();
    let changed = false;
    s.routes.forEach((r) => {
      if (!r.running || r.status === "completed") return;
      if (!r.path || r.path.length < 2) return;
      r.segT += 0.02;
      if (r.segT >= 1) {
        r.segT = 0;
        r.segIndex += 1;
        // mark stop reached
        const stopIdx = r.segIndex - 1;
        if (r.stops[stopIdx]) {
          r.stops[stopIdx].status = "DONE";
          if (r.stops[stopIdx + 1]) r.stops[stopIdx + 1].status = "CURRENT";
        }
        if (r.segIndex >= r.path.length - 1) {
          r.segIndex = r.path.length - 2;
          r.segT = 1;
          r.running = false;
          r.status = "completed";
        }
      }
      const a = r.path[r.segIndex];
      const b = r.path[Math.min(r.segIndex + 1, r.path.length - 1)];
      r.pos = { lat: lerp(a.lat, b.lat, r.segT), lng: lerp(a.lng, b.lng, r.segT) };
      r.etaMin = Math.max(1, Math.round((r.path.length - 1 - (r.segIndex + r.segT)) * 12));
      const veh = s.vehicles.find((v) => v.id === r.vehicleId);
      if (veh) {
        veh.lat = r.pos.lat;
        veh.lng = r.pos.lng;
      }
      changed = true;
    });
    if (changed) emit();
  }, 900);
}
