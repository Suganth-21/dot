import React, { useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Truck, Inbox as InboxIcon, AlertTriangle, Send, CheckCircle2, Phone, MapPin,
  Route as RouteIcon, TrendingUp, ShieldAlert, Camera, ChevronRight, Building2, GripVertical,
} from "lucide-react";

import { useAuth } from "../store/authStore";
import { useLive } from "../hooks/useDb";
import { useAppMutation } from "../hooks/useAppMutation";
import * as returnSvc from "../services/returnService";
import * as pickupSvc from "../services/pickupService";
import * as ref from "../services/referenceService";
import * as analytics from "../services/analyticsService";

import { Card, Button, Input, Select, Label, Textarea, Badge } from "../components/ui";
import { KpiCard, KpiSkeleton, PageHeader, SectionTitle, StatusPill, EmptyState, LoadingState } from "../components/common";
import LiveMap from "../components/maps/LiveMap";
import PhotoCapture from "../components/scanner/PhotoCapture";
import { SmoothLine, RoundedBars, FunnelCard, ChartCard } from "../components/charts";
import { formatDate, cn } from "../lib/utils";

const useDid = () => useAuth((s) => s.user?.entityId) || "dist_1";

// ============================ DASHBOARD ======================================
export function Dashboard() {
  const did = useDid();
  const nav = useNavigate();
  const { data: stats, isLoading } = useQuery({ queryKey: ["dist-stats", did], queryFn: () => analytics.distributorStats(did) });
  const routes = useLive((s) => s.routes.filter((r) => r.distributorId === did && r.running));
  const allRoutes = useLive((s) => s.routes.filter((r) => r.distributorId === did));

  return (
    <div>
      <PageHeader title="Distributor control room" subtitle="Live pickups, confirmations & disputes" />
      {isLoading ? <KpiSkeleton /> : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
          <KpiCard label="Pending pickups" value={stats.pendingPickups} icon={Truck} tint="accent" />
          <KpiCard label="Pending confirm" value={stats.pendingConfirmations} icon={CheckCircle2} tint="amber" />
          <KpiCard label="Open disputes" value={stats.openDisputes} icon={AlertTriangle} tint="rose" />
          <KpiCard label="Ready to forward" value={stats.readyToForward} icon={Send} tint="mint" />
          <KpiCard label="Active vehicles" value={stats.activeVehicles} icon={RouteIcon} tint="surface" />
        </div>
      )}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <SectionTitle right={<Button variant="soft" size="sm" onClick={() => nav("/distributor/pickups/new")}>New route</Button>}>Today's routes</SectionTitle>
          {allRoutes.length === 0 ? <EmptyState title="No routes yet" icon={RouteIcon} /> : (
            <div className="space-y-2">
              {allRoutes.map((r) => (
                <div key={r.id} onClick={() => nav(`/distributor/pickups/${r.id}`)} className="flex cursor-pointer items-center gap-3 rounded-2xl bg-clay-surface p-3 hover:bg-clay-line" data-testid={`route-${r.id}`}>
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-clay"><Truck className="h-4 w-4 text-accent-ink" /></span>
                  <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{r.vehicleReg} · {r.stops.length} stops</div><div className="text-xs text-clay-muted">{r.agentName}</div></div>
                  <StatusPill status={r.running ? "active" : r.status === "completed" ? "CONFIRMED" : "SCHEDULED"} />
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card className="p-0">
          <div className="p-5 pb-3"><SectionTitle>Live fleet</SectionTitle></div>
          <LiveMap height={320}
            vehicles={routes.map((r) => ({ pos: r.pos, reg: r.vehicleReg, agent: r.agentName, eta: r.etaMin }))}
            stops={routes.flatMap((r) => r.stops)}
            routePath={routes[0]?.path}
          />
        </Card>
      </div>
    </div>
  );
}

// ============================ INBOX (Kanban, drag-and-drop) ==================
const COLS = [["REQUESTED", "New"], ["SCHEDULED", "Scheduled"], ["PICKED_UP", "Picked Up"], ["CONFIRMED", "Confirmed"]];
const COL_LABEL = { REQUESTED: "New", SCHEDULED: "Scheduled", PICKED_UP: "Picked Up", CONFIRMED: "Confirmed" };
export function Inbox() {
  const did = useDid();
  const nav = useNavigate();
  const user = useAuth((s) => s.user);
  const { data: rows, isLoading } = useQuery({ queryKey: ["returns", did], queryFn: () => returnSvc.listReturns({ distributorId: did }) });
  const pharmacies = useLive((s) => s.pharmacies);
  const warehouse = useLive((s) => s.distributors.find((d) => d.id === did));
  const [sel, setSel] = useState([]);
  const [dragId, setDragId] = useState(null);
  const [overCol, setOverCol] = useState(null);

  const moveMut = useAppMutation(({ id, status }) => returnSvc.setReturnStatus(id, status, { id: did, name: user?.name, role: "DISTRIBUTOR" }));

  const dist = (r) => {
    const p = pharmacies.find((x) => x.id === r.pharmacyId);
    if (!p || !warehouse) return "—";
    const km = Math.round(Math.hypot(p.lat - warehouse.lat, p.lng - warehouse.lng) * 111);
    return `${km} km`;
  };
  const pName = (id) => pharmacies.find((p) => p.id === id)?.name || "—";

  const onDrop = (status) => {
    setOverCol(null);
    const r = (rows || []).find((x) => x.id === dragId);
    setDragId(null);
    if (!r || r.status === status) return;
    if (r.status === "DISPUTED") { toast.error("Resolve the dispute before moving this return"); return; }
    moveMut.mutate({ id: r.id, status });
    toast.success(`Moved to ${COL_LABEL[status]}`);
  };

  if (isLoading) return <LoadingState />;

  const newRets = (rows || []).filter((r) => r.status === "REQUESTED");
  return (
    <div>
      <PageHeader title="Returns inbox" subtitle="Drag cards across the pickup lifecycle" icon={InboxIcon}
        actions={sel.length > 0 && <Button onClick={() => nav("/distributor/pickups/new", { state: { returnIds: sel } })} data-testid="create-route-from-sel"><RouteIcon className="h-4 w-4" /> Create route ({sel.length})</Button>} />
      {newRets.length > 0 && (
        <Card className="mb-4">
          <div className="flex items-center gap-2 text-sm text-clay-muted">
            <input type="checkbox" checked={sel.length === newRets.length} onChange={(e) => setSel(e.target.checked ? newRets.map((r) => r.id) : [])} data-testid="select-all-returns" />
            Bulk-select new returns for a route
          </div>
        </Card>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {COLS.map(([status, label]) => {
          const items = (rows || []).filter((r) => r.status === status);
          const isOver = overCol === status;
          return (
            <div
              key={status}
              data-testid={`kanban-col-${status}`}
              onDragOver={(e) => { e.preventDefault(); if (overCol !== status) setOverCol(status); }}
              onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOverCol((c) => (c === status ? null : c)); }}
              onDrop={() => onDrop(status)}
              className={cn("rounded-clay p-3 ring-1 transition-colors", isOver ? "bg-accent-soft ring-2 ring-accent/40" : "bg-clay-surface ring-clay-line/60")}
            >
              <div className="mb-3 flex items-center justify-between px-1"><span className="text-sm font-bold text-clay-ink">{label}</span><Badge tone="gray">{items.length}</Badge></div>
              <div className="min-h-[80px] space-y-2">
                {items.length === 0 && <p className={cn("px-1 py-6 text-center text-xs", isOver ? "text-accent-ink" : "text-clay-muted")}>{isOver ? "Drop here" : "Empty"}</p>}
                {items.map((r) => (
                  <div
                    key={r.id}
                    draggable
                    onDragStart={(e) => { setDragId(r.id); if (e.dataTransfer) { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", r.id); } }}
                    onDragEnd={() => { setDragId(null); setOverCol(null); }}
                    className={cn("cursor-grab rounded-2xl bg-clay-card p-3 shadow-clay ring-1 ring-clay-line/60 transition-opacity active:cursor-grabbing", dragId === r.id && "opacity-40")}
                    data-testid={`kanban-card-${r.id}`}
                  >
                    <div className="flex items-start gap-2">
                      {status === "REQUESTED" && <input type="checkbox" className="mt-1" checked={sel.includes(r.id)} onChange={(e) => setSel((s) => e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id))} onClick={(e) => e.stopPropagation()} data-testid={`select-${r.id}`} />}
                      <button className="flex-1 text-left" onClick={() => nav(`/distributor/returns/${r.id}`)}>
                        <div className="text-sm font-semibold text-clay-ink">{r.drugName}</div>
                        <div className="text-xs text-clay-muted">{pName(r.pharmacyId)}</div>
                        <div className="mt-2 flex items-center justify-between text-xs"><span className="text-clay-muted">{r.quantityClaimed} units</span><span className="flex items-center gap-1 text-accent-ink"><MapPin className="h-3 w-3" />{dist(r)}</span></div>
                      </button>
                      <GripVertical className="mt-0.5 h-4 w-4 shrink-0 text-clay-muted" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================ RETURN DETAIL (dispute gate) ===================
export function ReturnDetail() {
  const { returnId } = useParams();
  const { data: ret, isLoading } = useQuery({ queryKey: ["return", returnId], queryFn: () => returnSvc.getReturn(returnId) });
  const [received, setReceived] = useState("");
  const [notes, setNotes] = useState("");
  const [resolution, setResolution] = useState("");
  const [photoHash, setPhotoHash] = useState(null);

  React.useEffect(() => { if (ret && ret.quantityReceived != null) setReceived(String(ret.quantityReceived)); }, [ret]);

  const recvMut = useAppMutation(() => returnSvc.distributorReceive(returnId, { quantityReceived: Number(received), photoHash: photoHash || ret.distributorPhotoHash, notes }), {
    onSuccess: (r) => { r.dispute ? toast.error("Quantity dispute — chain halted") : toast.success("Confirmed — ready to forward"); },
  });
  const resolveMut = useAppMutation(() => returnSvc.resolveDispute(returnId, resolution), {
    onSuccess: () => toast.success("Dispute resolved — forwarding unlocked"),
  });
  const fwdMut = useAppMutation(() => returnSvc.forwardReturns([returnId], { id: ret.distributorId, name: ret.distributor?.name, role: "DISTRIBUTOR" }), {
    onSuccess: () => toast.success("Forwarded to manufacturer"),
  });

  if (isLoading || !ret) return <LoadingState rows={5} />;
  const isDispute = ret.status === "DISPUTED";
  const isConfirmed = ret.status === "CONFIRMED";
  const isForwarded = ret.status === "FORWARDED";

  return (
    <div className={cn("rounded-clay transition-colors", isDispute && "bg-amber2-soft/40 p-4 -m-1")}>
      <PageHeader title="Verify received quantity" subtitle={`${ret.drugName} · ${ret.batchId}`} icon={ShieldAlert} />
      {isDispute && (
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="mb-4 flex items-center gap-3 rounded-clay bg-amber2 px-5 py-4 text-white shadow-pop" data-testid="dispute-banner">
          <AlertTriangle className="h-6 w-6" />
          <div><div className="text-base font-extrabold">Quantity Dispute — Chain Halted</div><div className="text-sm text-white/90">Forwarding is blocked until resolution notes are filed.</div></div>
        </motion.div>
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Pharmacy claim */}
        <Card className="bg-clay-surface">
          <SectionTitle>Pharmacy claim</SectionTitle>
          <div className="mb-3 rounded-2xl bg-clay-line/60 p-4 text-center text-sm text-clay-muted">
            <Camera className="mx-auto mb-2 h-8 w-8 opacity-50" />Strip photo · {ret.photoHash?.slice(0, 16)}…
          </div>
          <div className="opacity-70">
            <Field k="Claimed quantity" v={<span className="text-2xl font-extrabold text-clay-ink tnum">{ret.quantityClaimed}</span>} />
            <Field k="Reason" v={ret.reason} />
            <Field k="Pharmacy" v={ret.pharmacy?.name} />
          </div>
        </Card>
        {/* Distributor received */}
        <Card>
          <SectionTitle>Distributor received</SectionTitle>
          {isConfirmed || isForwarded || ret.distributorPhotoHash ? (
            <div className="mb-3 flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-mint bg-mint-soft py-6 text-sm text-[#1f8a6a]">
              <Camera className="h-5 w-5" /> Photo captured ✓
            </div>
          ) : (
            <PhotoCapture idleLabel="Photograph received goods" onCaptured={setPhotoHash} testId="distributor-received-photo" className="mb-3" />
          )}
          <Label>Received quantity</Label>
          <Input type="number" value={received} onChange={(e) => setReceived(e.target.value)} disabled={isConfirmed || isForwarded} data-testid="received-qty" />
          <div className="mt-3"><Label>Notes</Label><Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} disabled={isConfirmed || isForwarded} /></div>
          {!isConfirmed && !isForwarded && !isDispute && (
            <Button className="mt-3 w-full" disabled={!received || !photoHash || recvMut.isPending} onClick={() => recvMut.mutate()} data-testid="save-received">Save & check</Button>
          )}
        </Card>
      </div>

      {isDispute && (
        <Card className="mt-4 ring-amber2/30">
          <SectionTitle>Mandatory resolution notes</SectionTitle>
          <Textarea rows={3} value={resolution} onChange={(e) => setResolution(e.target.value)} placeholder="e.g. 5 units water damaged — verified against strip photo" data-testid="resolution-notes" />
          <Button variant="success" className="mt-3" disabled={!resolution.trim() || resolveMut.isPending} onClick={() => resolveMut.mutate()} data-testid="submit-resolution">Submit resolution</Button>
        </Card>
      )}

      <div className="mt-4 flex justify-end">
        <Button variant={isConfirmed ? "primary" : "outline"} disabled={!isConfirmed || fwdMut.isPending} onClick={() => fwdMut.mutate()} data-testid="forward-btn">
          <Send className="h-4 w-4" /> {isForwarded ? "Forwarded ✓" : "Forward to manufacturer"}
        </Button>
      </div>
    </div>
  );
}
function Field({ k, v }) { return <div className="flex items-center justify-between border-b border-clay-line py-2 last:border-0"><span className="text-xs uppercase tracking-wide text-clay-muted">{k}</span><span className="font-semibold text-clay-ink">{v}</span></div>; }

// ============================ PICKUPS list ===================================
export function Pickups() {
  const did = useDid();
  const nav = useNavigate();
  const routes = useLive((s) => s.routes.filter((r) => r.distributorId === did));
  return (
    <div>
      <PageHeader title="Pickups" subtitle="Routes & schedules" icon={Truck}
        actions={<Button onClick={() => nav("/distributor/pickups/new")} data-testid="new-route-btn"><RouteIcon className="h-4 w-4" /> New route</Button>} />
      {routes.length === 0 ? <EmptyState title="No routes" subtitle="Create a pickup route from the inbox." icon={RouteIcon} /> : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {routes.map((r) => (
            <Card key={r.id} className="cursor-pointer hover:shadow-clay-hover" onClick={() => nav(`/distributor/pickups/${r.id}`)} data-testid={`pickup-${r.id}`}>
              <div className="flex items-center justify-between"><div className="text-lg font-bold text-clay-ink">{r.vehicleReg}</div><StatusPill status={r.running ? "active" : r.status === "completed" ? "CONFIRMED" : "SCHEDULED"} /></div>
              <div className="mt-1 text-sm text-clay-muted">{r.agentName} · {r.stops.length} stops · ETA {r.etaMin}m</div>
              <div className="mt-3 flex -space-x-1">{r.stops.slice(0, 6).map((s, i) => <span key={i} className={cn("h-2.5 w-2.5 rounded-full ring-2 ring-white", s.status === "DONE" ? "bg-mint" : s.status === "CURRENT" ? "bg-amber2" : "bg-clay-line")} />)}</div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================ PICKUP NEW (route builder) =====================
export function PickupNew() {
  const did = useDid();
  const nav = useNavigate();
  const { data: rows } = useQuery({ queryKey: ["returns", did], queryFn: () => returnSvc.listReturns({ distributorId: did }) });
  const { data: agents } = useQuery({ queryKey: ["agents", did], queryFn: () => ref.getAgents(did) });
  const { data: vehicles } = useQuery({ queryKey: ["vehicles", did], queryFn: () => ref.getVehicles(did) });
  const pharmacies = useLive((s) => s.pharmacies);
  const warehouse = useLive((s) => s.distributors.find((d) => d.id === did));
  const [sel, setSel] = useState([]);
  const [agent, setAgent] = useState("");
  const [veh, setVeh] = useState("");
  const [dragIdx, setDragIdx] = useState(null);
  const [overIdx, setOverIdx] = useState(null);
  const location = useLocation();
  React.useEffect(() => {
    const pre = location.state?.returnIds;
    if (pre && pre.length) setSel(pre);
  }, [location.state]);

  const pending = (rows || []).filter((r) => r.status === "REQUESTED");
  const selStops = sel.map((id) => { const r = pending.find((x) => x.id === id); const p = pharmacies.find((x) => x.id === r?.pharmacyId); return p ? { ...p, returnId: id, drugName: r.drugName } : null; }).filter(Boolean);
  const legs = warehouse ? [{ lat: warehouse.lat, lng: warehouse.lng }, ...selStops.map((p) => ({ lat: p.lat, lng: p.lng }))] : [];
  const totalKm = legs.length > 1 ? Math.round(legs.slice(1).reduce((acc, p, i) => acc + Math.hypot(p.lat - legs[i].lat, p.lng - legs[i].lng) * 111, 0)) : 0;

  const reorder = (from, to) => {
    if (from == null || to == null || from === to) return;
    setSel((s) => { const a = [...s]; const [m] = a.splice(from, 1); a.splice(to, 0, m); return a; });
  };
  const optimize = () => {
    if (!warehouse || selStops.length < 2) return;
    const pool = [...selStops];
    const out = [];
    let cur = { lat: warehouse.lat, lng: warehouse.lng };
    while (pool.length) {
      const from = cur; // captured per-iteration — the comparator below must not close over the loop-mutated `cur` itself
      pool.sort((a, b) => (Math.hypot(a.lat - from.lat, a.lng - from.lng)) - (Math.hypot(b.lat - from.lat, b.lng - from.lng)));
      const next = pool.shift(); out.push(next); cur = next;
    }
    setSel(out.map((p) => p.returnId));
    toast.success("Route optimised — nearest first");
  };

  const mut = useAppMutation(() => pickupSvc.createRoute({ distributorId: did, returnIds: sel, agentId: agent, vehicleId: veh, manualOrder: true }), {
    onSuccess: async (route) => { await pickupSvc.dispatchRoute(route.id); toast.success("Route dispatched — vehicle rolling"); nav(`/distributor/pickups/${route.id}`); },
  });

  return (
    <div>
      <PageHeader title="Build a pickup route" subtitle="Select returns, assign a crew, dispatch" icon={RouteIcon} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <SectionTitle>Pending returns</SectionTitle>
          {pending.length === 0 ? <EmptyState title="No pending returns" icon={InboxIcon} /> : (
            <div className="space-y-2">
              {pending.map((r) => {
                const p = pharmacies.find((x) => x.id === r.pharmacyId);
                return (
                  <label key={r.id} className={cn("flex cursor-pointer items-center gap-3 rounded-2xl p-3 ring-1 transition-colors", sel.includes(r.id) ? "bg-accent-soft ring-accent/30" : "bg-clay-surface ring-clay-line/60")} data-testid={`builder-return-${r.id}`}>
                    <input type="checkbox" checked={sel.includes(r.id)} onChange={(e) => setSel((s) => e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id))} />
                    <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{r.drugName}</div><div className="text-xs text-clay-muted">{p?.name} · {p?.city}</div></div>
                    <Badge tone="gray">{r.quantityClaimed}u</Badge>
                  </label>
                );
              })}
            </div>
          )}
        </Card>
        <div className="space-y-4">
          <Card className="p-0">
            <div className="p-5 pb-3"><SectionTitle>Route preview {selStops.length > 0 && <span className="text-clay-muted">· {selStops.length} stops · ~{totalKm} km · ~{selStops.length * 12} min</span>}</SectionTitle></div>
            <LiveMap height={280}
              markers={selStops.map((p, i) => ({ lat: p.lat, lng: p.lng, label: `${i + 1}. ${p.name}` }))}
              routePath={legs.length > 1 ? legs : null}
              center={warehouse ? [warehouse.lat, warehouse.lng] : undefined} />
          </Card>

          <Card>
            <SectionTitle right={selStops.length > 1 && <Button variant="soft" size="sm" onClick={optimize} data-testid="optimize-route"><RouteIcon className="h-4 w-4" /> Auto-optimise</Button>}>
              Stop order {selStops.length > 1 && <span className="font-normal text-clay-muted">· drag to reorder</span>}
            </SectionTitle>
            {selStops.length === 0 ? (
              <p className="rounded-2xl bg-clay-surface px-4 py-6 text-center text-sm text-clay-muted">Select returns to build the stop order.</p>
            ) : (
              <ol className="space-y-2" data-testid="stop-order-list">
                {selStops.map((p, i) => (
                  <li
                    key={p.returnId}
                    draggable
                    onDragStart={(e) => { setDragIdx(i); if (e.dataTransfer) { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(i)); } }}
                    onDragEnter={() => setOverIdx(i)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => { reorder(dragIdx, i); setDragIdx(null); setOverIdx(null); }}
                    onDragEnd={() => { setDragIdx(null); setOverIdx(null); }}
                    className={cn("flex cursor-grab items-center gap-3 rounded-2xl p-3 ring-1 transition-all active:cursor-grabbing",
                      dragIdx === i ? "opacity-40" : overIdx === i ? "bg-accent-soft ring-accent/40" : "bg-clay-surface ring-clay-line/60")}
                    data-testid={`stop-order-${i}`}
                  >
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-bold text-white">{i + 1}</span>
                    <div className="flex-1 min-w-0"><div className="truncate text-sm font-semibold text-clay-ink">{p.name}</div><div className="truncate text-xs text-clay-muted">{p.drugName} · {p.city}</div></div>
                    <GripVertical className="h-4 w-4 shrink-0 text-clay-muted" />
                  </li>
                ))}
              </ol>
            )}
          </Card>

          <Card className="space-y-3">
            <div><Label>Assign pickup agent</Label><Select value={agent} onChange={(e) => setAgent(e.target.value)} data-testid="assign-agent"><option value="">Choose…</option>{(agents || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</Select></div>
            <div><Label>Assign vehicle</Label><Select value={veh} onChange={(e) => setVeh(e.target.value)} data-testid="assign-vehicle"><option value="">Choose…</option>{(vehicles || []).map((v) => <option key={v.id} value={v.id}>{v.regNo}</option>)}</Select></div>
            <Button className="w-full" disabled={sel.length === 0 || !agent || !veh || mut.isPending} onClick={() => mut.mutate()} data-testid="dispatch-route"><Send className="h-4 w-4" /> Dispatch route</Button>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ============================ ROUTE VIEW (live) ==============================
export function RouteView() {
  const { routeId } = useParams();
  const route = useLive((s) => s.routes.find((r) => r.id === routeId));
  if (!route) return <LoadingState rows={4} />;
  const current = route.stops.find((s) => s.status === "CURRENT" || s.status === "ARRIVED");
  return (
    <div>
      <PageHeader title={`Route · ${route.vehicleReg}`} subtitle={`${route.agentName} · ${route.stops.length} stops`} icon={Truck}
        actions={<Button variant="soft" onClick={() => toast.info(`Calling ${route.agentName}…`)} data-testid="call-agent-route"><Phone className="h-4 w-4" /> Call agent</Button>} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="p-0 lg:col-span-2">
          <LiveMap height={440} follow center={[route.pos.lat, route.pos.lng]} vehicles={[{ pos: route.pos, reg: route.vehicleReg, agent: route.agentName, eta: route.etaMin }]} stops={route.stops} routePath={route.path} />
        </Card>
        <Card>
          <SectionTitle>Stops</SectionTitle>
          <div className="mb-3 rounded-2xl bg-accent-soft p-3 text-sm font-semibold text-accent-ink">{current ? `At Stop ${current.order} — ${current.status === "ARRIVED" ? "picking up" : "en route"}` : route.running ? "En route" : "Route complete"}</div>
          <ol className="space-y-2">
            {route.stops.map((s) => (
              <li key={s.order} className="flex items-center gap-3 rounded-2xl bg-clay-surface p-3">
                <span className={cn("flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold text-white", s.status === "DONE" ? "bg-mint" : s.status === "CURRENT" || s.status === "ARRIVED" ? "bg-amber2" : "bg-clay-muted")}>{s.order}</span>
                <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{s.pharmacyName}</div><div className="text-xs text-clay-muted">{s.address}</div></div>
                <StatusPill status={s.status === "DONE" ? "CONFIRMED" : s.status === "CURRENT" ? "EN_ROUTE" : s.status === "ARRIVED" ? "ARRIVED" : "REQUESTED"} />
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  );
}

// ============================ FLEET ==========================================
export function Fleet() {
  const did = useDid();
  const vehicles = useLive((s) => s.vehicles.filter((v) => v.distributorId === did));
  const agents = useLive((s) => s.agents.filter((a) => a.distributorId === did));
  const routes = useLive((s) => s.routes.filter((r) => r.distributorId === did && r.running));
  const [selVeh, setSelVeh] = useState(null);
  const activeRoute = routes.find((r) => r.vehicleId === selVeh);

  return (
    <div>
      <PageHeader title="Fleet" subtitle="Vehicles & pickup agents" icon={RouteIcon} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-0">
          <div className="p-5 pb-3"><SectionTitle>Vehicles</SectionTitle></div>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted"><th className="px-5 py-3">Vehicle</th><th className="px-5 py-3">Status</th><th className="px-5 py-3"></th></tr></thead>
            <tbody>{vehicles.map((v) => (
              <tr key={v.id} className={cn("cursor-pointer border-b border-clay-line/60 hover:bg-clay-surface", selVeh === v.id && "bg-accent-soft/40")} onClick={() => setSelVeh(v.id)} data-testid={`vehicle-${v.id}`}>
                <td className="px-5 py-3 font-semibold text-clay-ink">{v.regNo}</td><td className="px-5 py-3"><StatusPill status={v.status} /></td><td className="px-5 py-3 text-right"><ChevronRight className="inline h-4 w-4 text-clay-muted" /></td>
              </tr>
            ))}</tbody>
          </table>
          <div className="p-5 pt-3"><SectionTitle>Agents</SectionTitle>
            <div className="space-y-2">{agents.map((a) => <div key={a.id} className="flex items-center gap-3 rounded-2xl bg-clay-surface p-3"><span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-clay text-sm font-bold">{a.name[0]}</span><div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{a.name}</div><div className="text-xs text-clay-muted">{a.phone}</div></div><StatusPill status={a.status} /></div>)}</div>
          </div>
        </Card>
        <Card className="p-0">
          <div className="p-5 pb-3"><SectionTitle>{selVeh ? "Live location" : "Select a vehicle"}</SectionTitle></div>
          <LiveMap height={420} follow={!!activeRoute} center={activeRoute ? [activeRoute.pos.lat, activeRoute.pos.lng] : undefined}
            vehicles={activeRoute ? [{ pos: activeRoute.pos, reg: activeRoute.vehicleReg, agent: activeRoute.agentName, eta: activeRoute.etaMin }] : routes.map((r) => ({ pos: r.pos, reg: r.vehicleReg }))}
            stops={activeRoute?.stops || []} routePath={activeRoute?.path} />
        </Card>
      </div>
    </div>
  );
}

// ============================ DISPUTES =======================================
export function Disputes() {
  const did = useDid();
  const nav = useNavigate();
  const { data: rows, isLoading } = useQuery({ queryKey: ["returns", did], queryFn: () => returnSvc.listReturns({ distributorId: did }) });
  if (isLoading) return <LoadingState />;
  const disputes = (rows || []).filter((r) => r.status === "DISPUTED");
  return (
    <div>
      <PageHeader title="Disputes" subtitle="Quantity mismatches halting the chain" icon={AlertTriangle} />
      {disputes.length === 0 ? <EmptyState title="No open disputes" subtitle="Every return matched at receipt." icon={CheckCircle2} /> : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted"><th className="px-5 py-3">Drug</th><th className="px-5 py-3">Category</th><th className="px-5 py-3">Claimed</th><th className="px-5 py-3">Received</th><th className="px-5 py-3">Age</th><th className="px-5 py-3"></th></tr></thead>
            <tbody>{disputes.map((r) => (
              <tr key={r.id} className="cursor-pointer border-b border-clay-line/60 hover:bg-clay-surface" onClick={() => nav(`/distributor/returns/${r.id}`)} data-testid={`dispute-${r.id}`}>
                <td className="px-5 py-3 font-semibold text-clay-ink">{r.drugName}</td><td className="px-5 py-3 capitalize text-clay-muted">{r.category}</td>
                <td className="px-5 py-3 tnum">{r.quantityClaimed}</td><td className="px-5 py-3 tnum text-rose2">{r.quantityReceived}</td>
                <td className="px-5 py-3 text-clay-muted">{formatDate(r.createdAt)}</td><td className="px-5 py-3 text-right"><ChevronRight className="inline h-4 w-4 text-clay-muted" /></td>
              </tr>
            ))}</tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// ============================ FORWARD ========================================
export function Forward() {
  const did = useDid();
  const { data: rows, isLoading } = useQuery({ queryKey: ["returns", did], queryFn: () => returnSvc.listReturns({ distributorId: did }) });
  const [sel, setSel] = useState([]);
  const ready = (rows || []).filter((r) => r.status === "CONFIRMED");
  const mut = useAppMutation(() => returnSvc.forwardReturns(sel, { id: did, name: "Distributor", role: "DISTRIBUTOR" }), {
    onSuccess: () => { toast.success(`Forwarded ${sel.length} batch(es) to manufacturer`); setSel([]); },
  });
  if (isLoading) return <LoadingState />;
  return (
    <div>
      <PageHeader title="Forward to manufacturer" subtitle="Confirmed batches ready to move up the chain" icon={Send}
        actions={<Button disabled={sel.length === 0 || mut.isPending} onClick={() => mut.mutate()} data-testid="bulk-forward">Forward {sel.length > 0 ? `(${sel.length})` : "all"}</Button>} />
      {ready.length === 0 ? <EmptyState title="Nothing to forward" subtitle="Confirm returns first." icon={Send} /> : (
        <Card className="p-0">
          <div className="flex items-center gap-2 border-b border-clay-line px-5 py-3 text-sm text-clay-muted">
            <input type="checkbox" checked={sel.length === ready.length} onChange={(e) => setSel(e.target.checked ? ready.map((r) => r.id) : [])} data-testid="forward-select-all" /> Select all
          </div>
          {ready.map((r) => (
            <label key={r.id} className="flex cursor-pointer items-center gap-3 border-b border-clay-line/60 px-5 py-3.5 hover:bg-clay-surface" data-testid={`forward-item-${r.id}`}>
              <input type="checkbox" checked={sel.includes(r.id)} onChange={(e) => setSel((s) => e.target.checked ? [...s, r.id] : s.filter((x) => x !== r.id))} />
              <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{r.drugName}</div><div className="font-mono text-xs text-clay-muted">{r.batchId}</div></div>
              <Badge tone="mint">{r.quantityReceived ?? r.quantityClaimed} units</Badge>
            </label>
          ))}
        </Card>
      )}
    </div>
  );
}

// ============================ ANALYTICS ======================================
export function Analytics() {
  const did = useDid();
  const { data, isLoading } = useQuery({ queryKey: ["dist-analytics", did], queryFn: () => analytics.distributorAnalytics(did) });
  if (isLoading || !data) return <LoadingState rows={6} />;
  return (
    <div>
      <PageHeader title="Analytics" subtitle="Throughput, disputes & geography" icon={TrendingUp} />
      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
        <KpiCard label="Avg completion" value={data.kpis.avgCompletion} tint="accent" />
        <KpiCard label="Dispute rate" value={`${data.kpis.disputeRate}%`} tint="rose" />
        <KpiCard label="On-time pickup" value={`${data.kpis.onTime}%`} tint="mint" />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Returns processed per week"><SmoothLine data={data.weekly} xKey="week" yKey="returns" /></ChartCard>
        <ChartCard title="Pipeline funnel"><FunnelCard data={data.funnel} /></ChartCard>
        <ChartCard title="Returns by pharmacy · top 15"><RoundedBars data={data.byPharmacy} xKey="name" yKey="returns" horizontal color="#a78bfa" height={320} /></ChartCard>
        <ChartCard title="Dispute frequency per pharmacy · fraud hint"><RoundedBars data={data.disputeFreq} xKey="name" yKey="disputes" color="#e0655b" /></ChartCard>
      </div>
      <Card className="mt-4 p-0"><div className="p-5 pb-3"><SectionTitle>Pickup concentration</SectionTitle></div><LiveMap height={340} bubbles={data.heat.map((h) => ({ lat: h.lat, lng: h.lng, value: h.weight * 30, label: "pickups" }))} /></Card>
    </div>
  );
}

export function Profile() {
  const did = useDid();
  const d = useLive((s) => s.distributors.find((x) => x.id === did));
  if (!d) return null;
  return (
    <div className="max-w-2xl">
      <PageHeader title="Profile" subtitle="Distributor on the DOT registry" icon={Building2} />
      <Card className="space-y-3">
        <Field k="Name" v={d.name} /><Field k="License" v={d.licenseNo} /><Field k="Address" v={d.address} /><Field k="City" v={d.city} />
      </Card>
    </div>
  );
}
