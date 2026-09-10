import { getState, mutate, emit } from "./db";
import { uid } from "../lib/utils";

const delay = (ms = 120) => new Promise((r) => setTimeout(r, ms));

const notifStore = () => getState().notifications;

export function notify(role, title, body, kind = "info", link) {
  const s = getState();
  if (!s.notifications[role]) s.notifications[role] = [];
  s.notifications[role].unshift({ id: uid("ntf"), title, body, kind, link, ts: new Date().toISOString(), read: false });
  s.notifications[role] = s.notifications[role].slice(0, 40);
}

export async function getNotifications(role) {
  await delay(50);
  return (notifStore()[role] || []).map((n) => ({ ...n }));
}

export async function markAllRead(role) {
  mutate((s) => {
    (s.notifications[role] || []).forEach((n) => (n.read = true));
  });
}

export async function markRead(role, id) {
  mutate((s) => {
    const n = (s.notifications[role] || []).find((x) => x.id === id);
    if (n) n.read = true;
  });
}

// Interval-based live notification simulation
const TICKS = {
  RETAILER: [
    ["Sale recorded", "2 units of Atorvastatin sold", "success"],
    ["Expiry reminder", "3 batches enter their 30-day window", "warning"],
  ],
  DISTRIBUTOR: [
    ["Vehicle update", "TN 11 AB reached stop 4 of 7", "info"],
    ["Confirmation pending", "1 return awaiting your receipt check", "warning"],
  ],
  MANUFACTURER: [
    ["Facility slot open", "EnviroSafe has a pickup slot tomorrow", "info"],
    ["Compliance nudge", "2 batches near their 30-day closure window", "warning"],
  ],
  REGULATOR: [
    ["Route update", "Active pickup routes: 2 vehicles moving", "info"],
    ["Alert digest", "No new critical alerts in the last hour", "info"],
  ],
  PICKUP_AGENT: [["Reminder", "Mark arrival when you reach each stop", "info"]],
};

let started = false;
export function startNotificationSim() {
  if (started) return;
  started = true;
  let i = 0;
  setInterval(() => {
    const roles = Object.keys(TICKS);
    const role = roles[i % roles.length];
    const pool = TICKS[role];
    const item = pool[Math.floor(Math.random() * pool.length)];
    notify(role, item[0], item[1], item[2]);
    emit();
    i++;
  }, 15000);
}
