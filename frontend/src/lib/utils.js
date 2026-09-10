import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

// Deterministic tiny hash -> hex string (for hash-chain visualisation, NOT crypto).
export function shortHash(input) {
  const str = String(input);
  let h1 = 0x811c9dc5;
  let h2 = 0x1000193;
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
    h2 = Math.imul(h2 + c, 0x85ebca6b) >>> 0;
  }
  const hex = (h1.toString(16).padStart(8, "0") + h2.toString(16).padStart(8, "0")).padEnd(16, "0");
  return "0x" + hex.slice(0, 16);
}

export function photoHash(seed) {
  return shortHash("photo:" + seed).replace("0x", "0x") + shortHash("p2:" + seed).slice(2, 10);
}

export function uid(prefix = "id") {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}${Date.now().toString(36).slice(-4)}`;
}

export function daysBetween(a, b) {
  return Math.round((new Date(b) - new Date(a)) / 86400000);
}

export function formatDate(d, opts) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-IN", opts || { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDateTime(d) {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export function timeAgo(d) {
  const s = Math.floor((Date.now() - new Date(d)) / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const dd = Math.floor(h / 24);
  return `${dd}d ago`;
}

export function inr(n) {
  if (n == null) return "—";
  return "₹" + Number(n).toLocaleString("en-IN");
}

// Current "now" for the demo — treated as September 2026.
export const DEMO_NOW = new Date("2026-09-15T09:30:00+05:30");

export function lerp(a, b, t) {
  return a + (b - a) * t;
}
