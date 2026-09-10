import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import {
  LayoutDashboard, Boxes, RotateCcw, ShoppingCart, BarChart3, Bell,
  Inbox, Truck, Route as RouteIcon, AlertTriangle, Send, Users, Map, FileText,
  Building2, FileCheck2, History,
} from "lucide-react";

import { useAuth } from "./store/authStore";
import { startSimulation } from "./services/db";
import { startNotificationSim } from "./services/notificationService";

import AppShell from "./components/layout/AppShell";
import AgentShell from "./components/layout/AgentShell";
import Login from "./pages/Login";
import * as P from "./pages/pharmacy";
import * as D from "./pages/distributor";
import * as A from "./pages/agent";
import * as M from "./pages/manufacturer";
import * as R from "./pages/regulator";
import * as V from "./pages/verify";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 0, staleTime: 500, placeholderData: (p) => p } },
});

function Protected({ role, children }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (role && user.role !== role) return <Navigate to={user.home} replace />;
  return children;
}

const pharmacyNav = [
  { to: "/pharmacy/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/pharmacy/inventory", label: "Inventory", icon: Boxes },
  { to: "/pharmacy/returns", label: "Returns", icon: RotateCcw },
  { to: "/pharmacy/sales", label: "Sales", icon: ShoppingCart },
  { to: "/pharmacy/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/pharmacy/alerts", label: "Alerts", icon: Bell },
];
const distributorNav = [
  { to: "/distributor/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/distributor/returns/inbox", label: "Inbox", icon: Inbox },
  { to: "/distributor/pickups", label: "Pickups", icon: Truck },
  { to: "/distributor/fleet", label: "Fleet", icon: RouteIcon },
  { to: "/distributor/disputes", label: "Disputes", icon: AlertTriangle },
  { to: "/distributor/forward", label: "Forward", icon: Send },
  { to: "/distributor/analytics", label: "Analytics", icon: BarChart3 },
];
const manufacturerNav = [
  { to: "/manufacturer/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/manufacturer/inbox", label: "Inbox", icon: Inbox },
  { to: "/manufacturer/facilities", label: "Facilities", icon: Building2 },
  { to: "/manufacturer/certificates", label: "Certificates", icon: FileCheck2 },
  { to: "/manufacturer/fleet-map", label: "Fleet Map", icon: Map },
  { to: "/manufacturer/batches", label: "Batches", icon: Boxes },
  { to: "/manufacturer/analytics", label: "Analytics", icon: BarChart3 },
];
const regulatorNav = [
  { to: "/regulator/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/regulator/alerts", label: "Alerts", icon: AlertTriangle },
  { to: "/regulator/batches", label: "Batches", icon: Boxes },
  { to: "/regulator/returns", label: "Returns", icon: RotateCcw },
  { to: "/regulator/entities", label: "Entities", icon: Users },
  { to: "/regulator/fleet-map", label: "Fleet Map", icon: Map },
  { to: "/regulator/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/regulator/reports", label: "Reports", icon: FileText },
];
const agentNav = [
  { to: "/agent/today", label: "Today", icon: RouteIcon },
  { to: "/agent/history", label: "History", icon: History },
  { to: "/agent/profile", label: "Profile", icon: Users },
];

export default function App() {
  useEffect(() => {
    startSimulation();
    startNotificationSim();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Toaster position="top-right" richColors closeButton toastOptions={{ style: { borderRadius: "16px" } }} />
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<Login />} />

          {/* Public Patient Shield */}
          <Route path="/verify" element={<V.Landing />} />
          <Route path="/verify/scan" element={<V.Scan />} />
          <Route path="/verify/result/:batchId" element={<V.Result />} />
          <Route path="/verify/report" element={<V.Report />} />

          {/* Pharmacy */}
          <Route path="/pharmacy" element={<Protected role="RETAILER"><AppShell navItems={pharmacyNav} role="RETAILER" roleHome="/pharmacy/dashboard" roleLabel="Pharmacy Portal" /></Protected>}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<P.Dashboard />} />
            <Route path="inventory" element={<P.Inventory />} />
            <Route path="inventory/add" element={<P.InventoryAdd />} />
            <Route path="inventory/:batchId" element={<P.BatchDetail />} />
            <Route path="returns" element={<P.Returns />} />
            <Route path="returns/new/:batchId" element={<P.ReturnNew />} />
            <Route path="returns/:returnId/track" element={<P.ReturnTrack />} />
            <Route path="sales" element={<P.Sales />} />
            <Route path="analytics" element={<P.Analytics />} />
            <Route path="alerts" element={<P.Alerts />} />
            <Route path="profile" element={<P.Profile />} />
          </Route>

          {/* Distributor */}
          <Route path="/distributor" element={<Protected role="DISTRIBUTOR"><AppShell navItems={distributorNav} role="DISTRIBUTOR" roleHome="/distributor/dashboard" roleLabel="Distributor Portal" /></Protected>}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<D.Dashboard />} />
            <Route path="returns/inbox" element={<D.Inbox />} />
            <Route path="returns/:returnId" element={<D.ReturnDetail />} />
            <Route path="pickups" element={<D.Pickups />} />
            <Route path="pickups/new" element={<D.PickupNew />} />
            <Route path="pickups/:routeId" element={<D.RouteView />} />
            <Route path="fleet" element={<D.Fleet />} />
            <Route path="disputes" element={<D.Disputes />} />
            <Route path="forward" element={<D.Forward />} />
            <Route path="analytics" element={<D.Analytics />} />
            <Route path="profile" element={<D.Profile />} />
          </Route>

          {/* Manufacturer */}
          <Route path="/manufacturer" element={<Protected role="MANUFACTURER"><AppShell navItems={manufacturerNav} role="MANUFACTURER" roleHome="/manufacturer/dashboard" roleLabel="Manufacturer Portal" /></Protected>}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<M.Dashboard />} />
            <Route path="inbox" element={<M.MInbox />} />
            <Route path="inbox/:batchId" element={<M.InboxBatch />} />
            <Route path="facilities" element={<M.Facilities />} />
            <Route path="facilities/schedule" element={<M.FacilitiesSchedule />} />
            <Route path="certificates" element={<M.Certificates />} />
            <Route path="certificates/upload/:batchId" element={<M.CertUpload />} />
            <Route path="fleet-map" element={<M.FleetMap />} />
            <Route path="batches" element={<M.Batches />} />
            <Route path="batches/:batchId" element={<M.MBatchDetail />} />
            <Route path="analytics" element={<M.Analytics />} />
            <Route path="profile" element={<M.Profile />} />
          </Route>

          {/* Regulator */}
          <Route path="/regulator" element={<Protected role="REGULATOR"><AppShell navItems={regulatorNav} role="REGULATOR" roleHome="/regulator/dashboard" roleLabel="Drug Controller — CDSCO" institutional /></Protected>}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<R.Dashboard />} />
            <Route path="alerts" element={<R.Alerts />} />
            <Route path="alerts/:alertId" element={<R.AlertDetail />} />
            <Route path="batches" element={<R.Batches />} />
            <Route path="batches/:batchId" element={<R.BatchAudit />} />
            <Route path="returns" element={<R.Returns />} />
            <Route path="returns/:returnId" element={<R.ReturnAudit />} />
            <Route path="entities" element={<R.Entities />} />
            <Route path="entities/:entityId" element={<R.EntityDetail />} />
            <Route path="fleet-map" element={<R.FleetMap />} />
            <Route path="analytics" element={<R.Analytics />} />
            <Route path="reports" element={<R.Reports />} />
            <Route path="profile" element={<R.Profile />} />
          </Route>

          {/* Pickup Agent (mobile) */}
          <Route path="/agent" element={<Protected role="PICKUP_AGENT"><AgentShell navItems={agentNav} /></Protected>}>
            <Route index element={<Navigate to="today" replace />} />
            <Route path="today" element={<A.Today />} />
            <Route path="stop/:stopId" element={<A.Stop />} />
            <Route path="history" element={<A.HistoryPage />} />
            <Route path="profile" element={<A.Profile />} />
          </Route>

          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
