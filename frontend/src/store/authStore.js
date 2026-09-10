import { create } from "zustand";
import { persist } from "zustand/middleware";

// Demo accounts — one-click quick login, no password needed.
export const DEMO_ACCOUNTS = [
  { role: "RETAILER", label: "Pharmacy Portal", name: "Apollo Pharmacy — T. Nagar", entityId: "ph_1", email: "retailer@dot.in", home: "/pharmacy/dashboard", color: "mint", themeColor: "#10B981" },
  { role: "DISTRIBUTOR", label: "Distributor Portal", name: "Sunrise Pharma Distributors", entityId: "dist_1", email: "distributor@dot.in", home: "/distributor/dashboard", color: "accent", themeColor: "#FACC15" },
  { role: "PICKUP_AGENT", label: "Pickup Agent App", name: "Ravi Kumar", entityId: "agent_1", email: "agent@dot.in", home: "/agent/today", color: "sky2", themeColor: "#EA580C" },
  { role: "MANUFACTURER", label: "Manufacturer Portal", name: "Cipla Ltd.", entityId: "mfr_1", email: "manufacturer@dot.in", home: "/manufacturer/dashboard", color: "lilac", themeColor: "#7C3AED" },
  { role: "REGULATOR", label: "Drug Controller", name: "CDSCO — Tamil Nadu", entityId: "reg_1", email: "regulator@dot.in", home: "/regulator/dashboard", color: "amber2", themeColor: "#E11D48" },
];

export const ROLE_HOME = Object.fromEntries(DEMO_ACCOUNTS.map((a) => [a.role, a.home]));
export const ROLE_COLORS = Object.fromEntries(DEMO_ACCOUNTS.map((a) => [a.role, a.themeColor]));

export const useAuth = create(
  persist(
    (set) => ({
      user: null,
      login: (account) => set({ user: account }),
      logout: () => set({ user: null }),
    }),
    { name: "dot_auth" }
  )
);
