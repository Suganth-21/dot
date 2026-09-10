import React, { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Play, MapPin, Phone, CheckCircle2, Camera, ArrowRight, Navigation, History as HistoryIcon } from "lucide-react";
import { useAuth } from "../store/authStore";
import { useLive } from "../hooks/useDb";
import * as pickupSvc from "../services/pickupService";
import { Card, Button, Input, Label, Badge } from "../components/ui";
import { StatusPill, EmptyState, SectionTitle } from "../components/common";
import { cn } from "../lib/utils";

const useAid = () => useAuth((s) => s.user?.entityId) || "agent_1";

export function Today() {
  const aid = useAid();
  const nav = useNavigate();
  const route = useLive((s) => s.routes.find((r) => r.agentId === aid && r.status !== "completed") || s.routes.find((r) => r.agentId === aid));
  const routeIndex = useLive((s) => s.routes.findIndex((r) => r.id === route?.id) + 1);

  if (!route) return <EmptyState title="No route assigned" subtitle="Check back when your distributor assigns a route." icon={Navigation} />;

  const done = route.stops.filter((s) => s.status === "DONE").length;
  const progress = Math.round((done / route.stops.length) * 100);

  const start = async () => { await pickupSvc.dispatchRoute(route.id); toast.success("Route started — GPS emitting"); };

  return (
    <div>
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-clay-muted">Today</div>
      <h1 className="text-2xl font-extrabold text-clay-ink">Route {routeIndex} — {route.stops.length} stops</h1>
      <div className="mt-1 text-sm text-clay-muted">{route.vehicleReg}</div>

      {!route.running && route.status !== "completed" ? (
        <Button size="lg" className="mt-5 h-16 w-full text-lg" onClick={start} data-testid="start-route"><Play className="h-6 w-6" /> Start Route</Button>
      ) : (
        <Card tint="mint" className="mt-5">
          <div className="flex items-center justify-between text-sm font-semibold text-[#1f8a6a]"><span>{route.status === "completed" ? "Route complete" : "Route in progress"}</span><span>{progress}%</span></div>
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-white/60"><motion.div className="h-full rounded-full bg-mint" animate={{ width: `${progress}%` }} /></div>
        </Card>
      )}

      <div className="mt-5 space-y-2">
        {route.stops.map((s, i) => (
          <button key={i} onClick={() => nav(`/agent/stop/${route.id}__${i}`)} data-testid={`stop-card-${i}`}
            className={cn("flex w-full items-center gap-3 rounded-clay p-4 text-left ring-1 transition-all",
              s.status === "CURRENT" || s.status === "ARRIVED" ? "bg-accent-soft ring-accent/30" : "bg-clay-card ring-clay-line/60")}>
            <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white", s.status === "DONE" ? "bg-mint" : s.status === "CURRENT" || s.status === "ARRIVED" ? "bg-accent" : "bg-clay-muted")}>{s.order}</span>
            <div className="flex-1">
              <div className="text-sm font-bold text-clay-ink">{s.pharmacyName}</div>
              <div className="text-xs text-clay-muted">{s.address}</div>
              <div className="mt-1 text-xs text-accent-ink">{s.expectedBatches} batch(es) expected</div>
            </div>
            {s.status === "DONE" ? <CheckCircle2 className="h-5 w-5 text-mint" /> : <ArrowRight className="h-5 w-5 text-clay-muted" />}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Stop() {
  const { stopId } = useParams();
  const nav = useNavigate();
  const [routeId, idxStr] = stopId.split("__");
  const idx = Number(idxStr);
  const route = useLive((s) => s.routes.find((r) => r.id === routeId));
  const [counted, setCounted] = useState("");
  const [scanned, setScanned] = useState(false);

  if (!route || !route.stops[idx]) return <EmptyState title="Stop not found" icon={MapPin} />;
  const stop = route.stops[idx];

  const arrive = async () => { await pickupSvc.agentArrive(routeId, idx); toast.success("Arrival broadcast to distributor"); };
  const complete = async () => {
    if (!counted) { toast.error("Enter counted quantity"); return; }
    await pickupSvc.agentPickup(routeId, idx, Number(counted));
    toast.success("Pickup complete");
    nav("/agent/today");
  };

  return (
    <div>
      <button onClick={() => nav("/agent/today")} className="mb-3 text-sm font-semibold text-clay-muted">← Back to route</button>
      <Card>
        <div className="text-lg font-extrabold text-clay-ink">{stop.pharmacyName}</div>
        <div className="mt-1 flex items-start gap-1.5 text-sm text-clay-muted"><MapPin className="mt-0.5 h-4 w-4 shrink-0" /> {stop.address}</div>
        <Button variant="soft" size="sm" className="mt-3" onClick={() => toast.info("Calling pharmacy…")} data-testid="call-pharmacy"><Phone className="h-4 w-4" /> Call pharmacy</Button>
      </Card>

      <div className="mt-4">
        <Button className="h-14 w-full" variant={stop.status === "ARRIVED" || stop.status === "DONE" ? "success" : "primary"} onClick={arrive} disabled={stop.status === "ARRIVED" || stop.status === "DONE"} data-testid="arrived-btn">
          <MapPin className="h-5 w-5" /> {stop.status === "ARRIVED" || stop.status === "DONE" ? "Arrival broadcast ✓" : "I have arrived"}
        </Button>
      </div>

      <Card className="mt-4">
        <SectionTitle>Expected batches</SectionTitle>
        <div className="mb-4 rounded-2xl bg-clay-surface p-3 text-sm"><div className="font-semibold text-clay-ink">Doxorubicin 50mg</div><div className="text-xs text-clay-muted">Claimed 50 units</div></div>
        <Label>Scan / photograph</Label>
        <button onClick={() => { setScanned(true); toast.success("Batch scanned"); }} className={cn("mb-3 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-6 text-sm", scanned ? "border-mint bg-mint-soft text-[#1f8a6a]" : "border-clay-line text-clay-muted")} data-testid="agent-scan">
          <Camera className="h-5 w-5" /> {scanned ? "Scanned ✓" : "Scan QR / photograph"}
        </button>
        <Label>Counted quantity</Label>
        <Input type="number" value={counted} onChange={(e) => setCounted(e.target.value)} placeholder="e.g. 45" data-testid="counted-qty" />
      </Card>

      <Button className="mt-4 h-14 w-full" onClick={complete} data-testid="pickup-complete">Pickup complete — go to next stop <ArrowRight className="h-5 w-5" /></Button>
    </div>
  );
}

export function HistoryPage() {
  const aid = useAid();
  const completed = useLive((s) => s.routes.filter((r) => r.agentId === aid).flatMap((r) => r.stops.filter((st) => st.status === "DONE").map((st) => ({ ...st, route: r.vehicleReg }))));
  return (
    <div>
      <h1 className="mb-4 text-2xl font-extrabold text-clay-ink">History</h1>
      {completed.length === 0 ? <EmptyState title="No pickups yet" subtitle="Completed pickups from the last 30 days appear here." icon={HistoryIcon} /> : (
        <div className="space-y-2">
          {completed.map((s, i) => (
            <Card key={i} className="flex items-center gap-3">
              <CheckCircle2 className="h-5 w-5 text-mint" />
              <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{s.pharmacyName}</div><div className="text-xs text-clay-muted">{s.route}{s.counted != null ? ` · ${s.counted} units` : ""}</div></div>
              <Badge tone="mint">Done</Badge>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export function Profile() {
  const aid = useAid();
  const agent = useLive((s) => s.agents.find((a) => a.id === aid));
  const user = useAuth((s) => s.user);
  if (!agent) return null;
  return (
    <div>
      <h1 className="mb-4 text-2xl font-extrabold text-clay-ink">Profile</h1>
      <Card className="flex items-center gap-4">
        <span className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-accent text-2xl font-bold text-white">{agent.name[0]}</span>
        <div><div className="text-lg font-bold text-clay-ink">{agent.name}</div><div className="text-sm text-clay-muted">{agent.phone}{user?.email ? ` · ${user.email}` : ""}</div><StatusPill status={agent.status} /></div>
      </Card>
    </div>
  );
}
