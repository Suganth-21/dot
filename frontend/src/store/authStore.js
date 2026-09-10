import { create } from "zustand";
import { persist } from "zustand/middleware";
import { apiPost, getTokens, setTokens, clearTokens, setUnauthorizedHandler } from "../lib/api";

// Demo accounts — one-click quick login buttons on Login.jsx. `role`, `email`
// drive the real POST /api/auth/demo-login {role} call; `label`/`home`/
// `color`/`themeColor` are pure presentation, merged onto the real user object
// returned by the backend (ARCHITECTURE.md §6.3 — "Three of those are pure
// presentation... The frontend merges in label/home/color from the existing
// DEMO_ACCOUNTS-derived map keyed by role").
export const DEMO_ACCOUNTS = [
  { role: "RETAILER", label: "Pharmacy Portal", name: "Apollo Pharmacy — T. Nagar", entityId: "ph_1", email: "retailer@dot.in", home: "/pharmacy/dashboard", color: "mint", themeColor: "#10B981" },
  { role: "DISTRIBUTOR", label: "Distributor Portal", name: "Sunrise Pharma Distributors", entityId: "dist_1", email: "distributor@dot.in", home: "/distributor/dashboard", color: "accent", themeColor: "#FACC15" },
  { role: "PICKUP_AGENT", label: "Pickup Agent App", name: "Ravi Kumar", entityId: "agent_1", email: "agent@dot.in", home: "/agent/today", color: "sky2", themeColor: "#EA580C" },
  { role: "MANUFACTURER", label: "Manufacturer Portal", name: "Cipla Ltd.", entityId: "mfr_1", email: "manufacturer@dot.in", home: "/manufacturer/dashboard", color: "lilac", themeColor: "#7C3AED" },
  { role: "REGULATOR", label: "Drug Controller", name: "CDSCO — Tamil Nadu", entityId: "reg_1", email: "regulator@dot.in", home: "/regulator/dashboard", color: "amber2", themeColor: "#E11D48" },
];

export const ROLE_HOME = Object.fromEntries(DEMO_ACCOUNTS.map((a) => [a.role, a.home]));
export const ROLE_COLORS = Object.fromEntries(DEMO_ACCOUNTS.map((a) => [a.role, a.themeColor]));
const ROLE_PRESENTATION = Object.fromEntries(
  DEMO_ACCOUNTS.map((a) => [a.role, { label: a.label, home: a.home, color: a.color, themeColor: a.themeColor }])
);

// Real fields come off the wire (id, email, name, role, entityId); label/
// home/color/themeColor are stitched on locally — never sent by the API.
function mergeUser(apiUser) {
  const presentation = ROLE_PRESENTATION[apiUser.role] || {};
  return { ...presentation, ...apiUser };
}

export const useAuth = create(
  persist(
    (set) => ({
      user: null,

      // Real email/password sign-in — POST /api/auth/login.
      login: async (email, password) => {
        const data = await apiPost("/auth/login", { email, password }, { auth: false });
        setTokens(data.accessToken, data.refreshToken);
        const user = mergeUser(data.user);
        set({ user });
        return user;
      },

      // One-click demo buttons — same real auth code path, seeded shortcut
      // through the front door (ARCHITECTURE.md §6.4), never a second door.
      demoLogin: async (role) => {
        const data = await apiPost("/auth/demo-login", { role }, { auth: false });
        setTokens(data.accessToken, data.refreshToken);
        const user = mergeUser(data.user);
        set({ user });
        return user;
      },

      // Revokes server-side before wiping local state — a captured
      // pre-logout refresh token must fail on reuse (ARCHITECTURE.md §6.1).
      logout: () => {
        const { refreshToken } = getTokens();
        if (refreshToken) {
          apiPost("/auth/logout", { refreshToken }, { auth: false }).catch(() => {});
        }
        clearTokens();
        set({ user: null });
      },
    }),
    { name: "dot_auth" }
  )
);

// api.js can't import this store (would cycle) — it calls back through this
// handler instead once a refresh attempt has genuinely failed.
setUnauthorizedHandler(() => {
  useAuth.getState().logout();
  if (typeof window !== "undefined" && window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
});
