import React, { useState, useMemo } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Boxes, Clock, AlertTriangle, RotateCcw, PlusCircle, ArrowRight, Truck, Phone, Camera,
  Search, ShoppingCart, TrendingUp, ChevronRight, ShieldCheck, X,
} from "lucide-react";
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, XAxis, Tooltip,
} from "recharts";

import { useAuth } from "../store/authStore";
import { useLive } from "../hooks/useDb";
import { useAppMutation } from "../hooks/useAppMutation";
import * as batchSvc from "../services/batchService";
import * as returnSvc from "../services/returnService";
import * as ref from "../services/referenceService";
import * as analytics from "../services/analyticsService";
import { listAlerts } from "../services/alertService";
import { listRoutes } from "../services/pickupService";

import { Card, Button, Input, Select, Label, Textarea, Badge } from "../components/ui";
import {
  KpiCard, KpiSkeleton, PageHeader, SectionTitle, StatusPill, EmptyState,
  LoadingState, HashChain, Stepper, Modal,
} from "../components/common";
import QrScanner from "../components/scanner/QrScanner";
import LiveMap from "../components/maps/LiveMap";
import { SmoothLine, RoundedBars, Donut, Heatmap, StackedBars, ChartCard, PALETTE } from "../components/charts";
import { formatDate, formatDateTime, daysBetween, DEMO_NOW, inr, timeAgo, cn } from "../lib/utils";

const usePid = () => useAuth((s) => s.user?.entityId) || "ph_1";

function rowTint(status, expiryDate) {
  if (status === "IN_RETURN") return "bg-accent-soft/30";
  if (status === "EXPIRED") return "bg-rose2-soft/40";
  const d = daysBetween(DEMO_NOW, expiryDate);
  if (d <= 30 && d >= 0) return "bg-amber2-soft/40";
  return "";
}

// ============================ DASHBOARD ======================================
export function Dashboard() {
  const pid = usePid();
  const nav = useNavigate();
  const { data: stats, isLoading } = useQuery({ queryKey: ["ph-stats", pid], queryFn: () => analytics.pharmacyStats(pid) });
  const { data: spark } = useQuery({ queryKey: ["ph-spark", pid], queryFn: () => analytics.pharmacySparkline(pid) });
  const { data: alerts } = useQuery({ queryKey: ["alerts"], queryFn: () => listAlerts() });
  const routes = useLive((s) => s.routes.filter((r) => r.running));
  const pharm = useLive((s) => s.pharmacies.find((p) => p.id === pid));

  const upcoming = routes.map((r) => ({ id: r.id, reg: r.vehicleReg, eta: r.etaMin, agent: r.agentName }));
  const latestAlerts = (alerts || []).slice(0, 5);

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${pharm?.name?.split("—")[0]?.trim() || "Pharmacy"}`}
        subtitle={`${formatDate(DEMO_NOW, { weekday: "long", day: "numeric", month: "long", year: "numeric" })} · License ${pharm?.licenseNo}`}
        actions={
          <>
            <Button variant="soft" onClick={() => nav("/pharmacy/inventory/add")} data-testid="cta-add-stock"><PlusCircle className="h-4 w-4" /> Add Stock</Button>
            <Button onClick={() => nav("/pharmacy/inventory")} data-testid="cta-start-return"><RotateCcw className="h-4 w-4" /> Start Return</Button>
          </>
        }
      />
      {isLoading ? <KpiSkeleton /> : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
          <KpiCard label="Active Batches" value={stats.activeBatches} icon={Boxes} tint="mint" delay={0} />
          <KpiCard label="Expiring in 30d" value={stats.expiring30} icon={Clock} tint="amber" delay={0.05} />
          <KpiCard label="Expiring in 60d" value={stats.expiring60} icon={Clock} tint="surface" delay={0.1} />
          <KpiCard label="Pending Returns" value={stats.pendingReturns} icon={RotateCcw} tint="accent" delay={0.15} />
          <KpiCard label="Disputes" value={stats.disputes} icon={AlertTriangle} tint="rose" delay={0.2} />
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionTitle right={<Badge tone="mint"><TrendingUp className="h-3 w-3" /> +12% MoM</Badge>}>Sales volume — last 30 days</SectionTitle>
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={spark || []} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
                <defs><linearGradient id="ph-spark" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#5b6cff" stopOpacity={0.3} /><stop offset="100%" stopColor="#5b6cff" stopOpacity={0} /></linearGradient></defs>
                <XAxis dataKey="day" hide />
                <Tooltip cursor={false} contentStyle={{ borderRadius: 14, border: "1px solid #eceae5" }} />
                <Area type="monotone" dataKey="value" stroke="#5b6cff" strokeWidth={2.5} fill="url(#ph-spark)" isAnimationActive={false} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card tint="accent">
          <SectionTitle>Upcoming pickups today</SectionTitle>
          {upcoming.length === 0 ? (
            <p className="py-6 text-center text-sm text-clay-muted">No pickups scheduled today.</p>
          ) : (
            <div className="space-y-2">
              {upcoming.map((u) => (
                <div key={u.id} className="flex items-center gap-3 rounded-2xl bg-white/70 p-3">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white"><Truck className="h-4 w-4" /></span>
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-clay-ink">{u.reg}</div>
                    <div className="text-xs text-clay-muted">{u.agent}</div>
                  </div>
                  <Badge tone="accent">ETA {u.eta}m</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="mt-4">
        <Card>
          <SectionTitle right={<Link to="/pharmacy/alerts" className="text-xs font-semibold text-accent-ink">View all</Link>}>Latest alerts</SectionTitle>
          {latestAlerts.length === 0 ? <p className="py-6 text-center text-sm text-clay-muted">No alerts.</p> : (
            <div className="divide-y divide-clay-line">
              {latestAlerts.map((a) => (
                <div key={a.id} className="flex items-center gap-3 py-3">
                  <span className={cn("h-2.5 w-2.5 rounded-full", a.severity === "critical" ? "bg-rose2" : a.severity === "high" ? "bg-amber2" : "bg-accent")} />
                  <div className="flex-1"><div className="text-sm font-medium text-clay-ink">{a.message}</div><div className="text-xs text-clay-muted">{timeAgo(a.ts)} · {a.district}</div></div>
                  <StatusPill status={a.severity} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ============================ INVENTORY ======================================
export function Inventory() {
  const pid = usePid();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [window, setWindow] = useState("");
  const [status, setStatus] = useState("");
  const { data: batches, isLoading } = useQuery({ queryKey: ["batches"], queryFn: () => batchSvc.listBatches() });

  const rows = useMemo(() => {
    let r = (batches || []).filter((b) => b.pharmacyId === pid);
    if (q) r = r.filter((b) => b.drugName.toLowerCase().includes(q.toLowerCase()) || b.id.toLowerCase().includes(q.toLowerCase()));
    if (status) r = r.filter((b) => b.status === status);
    if (window) r = r.filter((b) => { const d = daysBetween(DEMO_NOW, b.expiryDate); return d >= 0 && d <= Number(window); });
    return r;
  }, [batches, pid, q, status, window]);

  return (
    <div>
      <PageHeader title="Inventory" subtitle="Your active batch ledger" icon={Boxes}
        actions={<Button onClick={() => nav("/pharmacy/inventory/add")} data-testid="add-batch-btn"><PlusCircle className="h-4 w-4" /> Add Stock</Button>} />
      <Card className="mb-4">
        <div className="flex flex-wrap gap-3">
          <div className="relative min-w-[220px] flex-1">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-clay-muted" />
            <Input className="pl-10" placeholder="Search drug or batch…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="inventory-search" />
          </div>
          <Select className="max-w-[160px]" value={window} onChange={(e) => setWindow(e.target.value)} data-testid="inventory-window">
            <option value="">Any expiry</option><option value="30">≤ 30 days</option><option value="60">≤ 60 days</option><option value="90">≤ 90 days</option>
          </Select>
          <Select className="max-w-[170px]" value={status} onChange={(e) => setStatus(e.target.value)} data-testid="inventory-status">
            <option value="">All statuses</option><option value="ACTIVE">Active</option><option value="EXPIRING_SOON">Expiring Soon</option><option value="EXPIRED">Expired</option><option value="IN_RETURN">In Return</option>
          </Select>
        </div>
      </Card>
      {isLoading ? <LoadingState /> : rows.length === 0 ? (
        <EmptyState title="No batches match" subtitle="Try clearing filters or add new stock." icon={Boxes}
          action={<Button onClick={() => nav("/pharmacy/inventory/add")}>Add Stock</Button>} />
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted">
                <th className="px-5 py-3">Drug</th><th className="px-5 py-3">Batch</th><th className="px-5 py-3">Units</th><th className="px-5 py-3">Expiry</th><th className="px-5 py-3">Status</th><th className="px-5 py-3"></th>
              </tr></thead>
              <tbody>
                {rows.map((b) => (
                  <tr key={b.id} onClick={() => nav(`/pharmacy/inventory/${b.id}`)} data-testid={`inventory-row-${b.id}`}
                    className={cn("cursor-pointer border-b border-clay-line/60 transition-colors hover:bg-clay-surface", rowTint(b.status, b.expiryDate))}>
                    <td className="px-5 py-3.5 font-semibold text-clay-ink">{b.drugName}<div className="text-xs font-normal capitalize text-clay-muted">{b.category}</div></td>
                    <td className="px-5 py-3.5 font-mono text-xs text-clay-muted">{b.id}</td>
                    <td className="px-5 py-3.5 font-semibold tnum">{b.quantity}</td>
                    <td className="px-5 py-3.5">{formatDate(b.expiryDate)}<div className="text-xs text-clay-muted">{daysBetween(DEMO_NOW, b.expiryDate)}d left</div></td>
                    <td className="px-5 py-3.5"><StatusPill status={b.status} /></td>
                    <td className="px-5 py-3.5 text-right"><ChevronRight className="inline h-4 w-4 text-clay-muted" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

// ============================ INVENTORY ADD ==================================
const KNOWN = {
  "BATCH-DOX-2026-A17": { drugName: "Doxorubicin 50mg", manufacturerName: "Cipla Ltd.", category: "oncology", drugKey: "DOX", mfg: "2025-05-01", exp: "2026-10-07" },
  "BATCH-DOX-2026-B04": { drugName: "Doxorubicin 50mg", manufacturerName: "Cipla Ltd.", category: "oncology", drugKey: "DOX", mfg: "2024-12-01", exp: "2026-08-16" },
  "BATCH-CEF-2026-A31": { drugName: "Cefixime 200mg", manufacturerName: "Sun Pharmaceutical Industries", category: "antibiotics", drugKey: "CEF", mfg: "2025-03-01", exp: "2027-02-01" },
};
export function InventoryAdd() {
  const pid = usePid();
  const nav = useNavigate();
  const user = useAuth((s) => s.user);
  const [form, setForm] = useState({ batchId: "", drugName: "", manufacturerName: "", mfg: "", exp: "", quantity: "" });
  const [scanned, setScanned] = useState(false);

  const onScan = (code) => {
    const k = KNOWN[code];
    setScanned(true);
    setForm((f) => ({
      ...f, batchId: code,
      drugName: k?.drugName || "", manufacturerName: k?.manufacturerName || "", mfg: k?.mfg || "", exp: k?.exp || "",
      drugKey: k?.drugKey, category: k?.category, quantity: f.quantity || "50",
    }));
    toast.success(`Scanned ${code}`);
  };

  const mut = useAppMutation((payload) => batchSvc.addBatch(payload, { id: pid, name: user?.name, role: "RETAILER" }, pid), {
    onSuccess: (res) => {
      if (res.reentry) { toast.error("RE-ENTRY ALERT: this batch was already destroyed. Regulator notified."); nav("/pharmacy/alerts"); }
      else { toast.success("Batch registered"); nav("/pharmacy/inventory"); }
    },
  });

  const submit = () => {
    if (!form.batchId || !form.drugName || !form.quantity) { toast.error("Fill batch, drug and quantity"); return; }
    mut.mutate({ ...form, quantity: Number(form.quantity), mfgDate: form.mfg, expiryDate: form.exp });
  };

  return (
    <div>
      <PageHeader title="Add stock" subtitle="Scan the batch QR or enter details manually" icon={PlusCircle} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <SectionTitle>Scan batch QR</SectionTitle>
          <QrScanner onScan={onScan} demoCodes={[
            { code: "BATCH-DOX-2026-A17", label: "Doxorubicin (new)" },
            { code: "BATCH-DOX-2026-B04", label: "Destroyed batch (re-entry demo)" },
            { code: "BATCH-CEF-2026-A31", label: "Cefixime" },
          ]} />
        </div>
        <div>
          <SectionTitle>{scanned ? "Confirm details" : "Manual entry"}</SectionTitle>
          <Card className="space-y-3">
            <div><Label>Batch number</Label><Input value={form.batchId} onChange={(e) => setForm({ ...form, batchId: e.target.value })} placeholder="BATCH-XXX-2026-A00" data-testid="add-batch-id" /></div>
            <div><Label>Drug name</Label><Input value={form.drugName} onChange={(e) => setForm({ ...form, drugName: e.target.value })} data-testid="add-drug-name" /></div>
            <div><Label>Manufacturer</Label><Input value={form.manufacturerName} onChange={(e) => setForm({ ...form, manufacturerName: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label>Mfg date</Label><Input type="date" value={form.mfg} onChange={(e) => setForm({ ...form, mfg: e.target.value })} /></div>
              <div><Label>Expiry date</Label><Input type="date" value={form.exp} onChange={(e) => setForm({ ...form, exp: e.target.value })} /></div>
            </div>
            <div><Label>Quantity (from invoice)</Label><Input type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} data-testid="add-quantity" /></div>
            <button className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-clay-line py-4 text-sm text-clay-muted hover:bg-clay-surface" onClick={() => toast.info("Invoice OCR coming soon")}>
              <Camera className="h-4 w-4" /> Photograph invoice (OCR — coming soon)
            </button>
            <Button className="w-full" onClick={submit} disabled={mut.isPending} data-testid="add-batch-submit">Register batch</Button>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ============================ BATCH DETAIL ===================================
export function BatchDetail() {
  const { batchId } = useParams();
  const nav = useNavigate();
  const { data: batch, isLoading } = useQuery({ queryKey: ["batch", batchId], queryFn: () => batchSvc.getBatch(batchId) });

  const salesSeries = useMemo(() => {
    if (!batch) return [];
    const evts = batch.events.filter((e) => e.type === "SALE");
    let cum = 0;
    return evts.map((e) => { cum += e.meta?.units || 0; return { date: formatDate(e.ts, { day: "2-digit", month: "short" }), units: cum }; });
  }, [batch]);

  if (isLoading || !batch) return <LoadingState rows={6} />;
  const canReturn = ["ACTIVE", "EXPIRING_SOON", "EXPIRED"].includes(batch.status);

  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-4 text-sm font-semibold text-clay-muted hover:text-clay-ink">← Back</button>
      <Card className="mb-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-3"><h1 className="text-2xl font-extrabold text-clay-ink">{batch.drugName}</h1><StatusPill status={batch.status} /></div>
            <p className="mt-1 font-mono text-sm text-clay-muted">{batch.id}</p>
            <div className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
              <Meta k="Manufacturer" v={batch.manufacturerName} />
              <Meta k="Mfg date" v={formatDate(batch.mfgDate)} />
              <Meta k="Expiry" v={formatDate(batch.expiryDate)} />
              <Meta k="Quantity" v={`${batch.quantity} / ${batch.initialQuantity}`} />
            </div>
          </div>
          {canReturn && <Button onClick={() => nav(`/pharmacy/returns/new/${batch.id}`)} data-testid="start-return-btn"><RotateCcw className="h-4 w-4" /> Start Return</Button>}
        </div>
      </Card>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionTitle>Event timeline · hash-chained</SectionTitle>
          <HashChain events={batch.events} />
        </Card>
        <Card>
          <SectionTitle>Units sold over time</SectionTitle>
          {salesSeries.length === 0 ? <EmptyState title="No sales yet" subtitle="Sales for this batch will appear here." icon={ShoppingCart} /> : (
            <div style={{ height: 240 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={salesSeries} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <XAxis dataKey="date" tick={{ fill: "#8a8681", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 14, border: "1px solid #eceae5" }} />
                  <Line type="monotone" dataKey="units" stroke="#5b6cff" strokeWidth={2.5} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
function Meta({ k, v }) { return <div><div className="text-xs uppercase tracking-wide text-clay-muted">{k}</div><div className="font-semibold text-clay-ink">{v}</div></div>; }

// ============================ RETURNS ========================================
export function Returns() {
  const pid = usePid();
  const nav = useNavigate();
  const { data: rows, isLoading } = useQuery({ queryKey: ["returns", pid], queryFn: () => returnSvc.listReturns({ pharmacyId: pid }) });
  const dists = useLive((s) => s.distributors);
  const dName = (id) => dists.find((d) => d.id === id)?.name || "—";

  return (
    <div>
      <PageHeader title="Returns" subtitle="Every return you've initiated" icon={RotateCcw} />
      {isLoading ? <LoadingState /> : (rows || []).length === 0 ? (
        <EmptyState title="No returns yet" subtitle="Start a return from any batch in your inventory." icon={RotateCcw}
          action={<Button onClick={() => nav("/pharmacy/inventory")}>Go to inventory</Button>} />
      ) : (
        <Card className="overflow-hidden p-0">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted">
              <th className="px-5 py-3">Batch</th><th className="px-5 py-3">Qty</th><th className="px-5 py-3">Distributor</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Initiated</th><th className="px-5 py-3"></th>
            </tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="cursor-pointer border-b border-clay-line/60 hover:bg-clay-surface" onClick={() => nav(`/pharmacy/returns/${r.id}/track`)} data-testid={`return-row-${r.id}`}>
                  <td className="px-5 py-3.5"><div className="font-semibold text-clay-ink">{r.drugName}</div><div className="font-mono text-xs text-clay-muted">{r.batchId}</div></td>
                  <td className="px-5 py-3.5 tnum">{r.quantityClaimed}</td>
                  <td className="px-5 py-3.5">{dName(r.distributorId)}</td>
                  <td className="px-5 py-3.5"><StatusPill status={r.status} /></td>
                  <td className="px-5 py-3.5 text-clay-muted">{formatDate(r.createdAt)}</td>
                  <td className="px-5 py-3.5 text-right"><ChevronRight className="inline h-4 w-4 text-clay-muted" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

// ============================ RETURN NEW =====================================
export function ReturnNew() {
  const { batchId } = useParams();
  const pid = usePid();
  const nav = useNavigate();
  const user = useAuth((s) => s.user);
  const { data: batch } = useQuery({ queryKey: ["batch", batchId], queryFn: () => batchSvc.getBatch(batchId) });
  const { data: distributors } = useQuery({ queryKey: ["distributors"], queryFn: () => ref.getDistributors() });
  const [qty, setQty] = useState("");
  const [dist, setDist] = useState("");
  const [reason, setReason] = useState("EXPIRED");
  const [photo, setPhoto] = useState(false);

  React.useEffect(() => { if (batch) setQty(String(batch.quantity)); }, [batch]);

  const mut = useAppMutation(() => returnSvc.createReturn(batchId, { quantity: Number(qty), distributorId: dist, reason, photoHash: "0xstrip" + batchId }, { id: pid, name: user?.name, role: "RETAILER" }), {
    onSuccess: (r) => { toast.success("Return created — tracking live"); nav(`/pharmacy/returns/${r.id}/track`); },
  });

  if (!batch) return <LoadingState rows={4} />;

  return (
    <div className="max-w-2xl">
      <PageHeader title="Start a return" subtitle="Send this batch into the reverse-logistics loop" icon={RotateCcw} />
      <Card tint="accent" className="mb-4">
        <div className="flex items-center justify-between">
          <div><div className="text-lg font-bold text-clay-ink">{batch.drugName}</div><div className="font-mono text-xs text-clay-muted">{batch.id}</div></div>
          <StatusPill status={batch.status} />
        </div>
      </Card>
      <Card className="space-y-4">
        <div>
          <Label>Photograph the batch strip</Label>
          <button onClick={() => { setPhoto(true); toast.success("Photo captured (mock)"); }} className={cn("flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-6 text-sm transition-colors", photo ? "border-mint bg-mint-soft text-[#1f8a6a]" : "border-clay-line text-clay-muted hover:bg-clay-surface")} data-testid="return-photo">
            <Camera className="h-5 w-5" /> {photo ? "Photo captured ✓" : "Tap to photograph strip"}
          </button>
        </div>
        <div><Label>Confirm remaining quantity</Label><Input type="number" value={qty} onChange={(e) => setQty(e.target.value)} data-testid="return-qty" /></div>
        <div><Label>Select distributor</Label>
          <Select value={dist} onChange={(e) => setDist(e.target.value)} data-testid="return-distributor">
            <option value="">Choose distributor…</option>
            {(distributors || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </Select>
        </div>
        <div><Label>Reason</Label>
          <Select value={reason} onChange={(e) => setReason(e.target.value)} data-testid="return-reason">
            <option value="EXPIRED">Expired</option><option value="DAMAGED">Damaged</option><option value="RECALL">Recall</option>
          </Select>
        </div>
        <Button className="w-full" disabled={!dist || mut.isPending} onClick={() => mut.mutate()} data-testid="return-submit">Create return <ArrowRight className="h-4 w-4" /></Button>
      </Card>
    </div>
  );
}

// ============================ RETURN TRACK ===================================
const RET_STEPS = ["Requested", "Assigned", "En Route", "Arrived", "Confirmed"];
const RET_STEP_IDX = { REQUESTED: 0, SCHEDULED: 1, ASSIGNED: 1, EN_ROUTE: 2, PICKED_UP: 3, ARRIVED: 3, CONFIRMED: 4, DISPUTED: 3, FORWARDED: 4 };
export function ReturnTrack() {
  const { returnId } = useParams();
  const { data: ret } = useQuery({ queryKey: ["return", returnId], queryFn: () => returnSvc.getReturn(returnId) });
  const routes = useLive((s) => s.routes);
  const route = routes.find((r) => r.id === ret?.routeId) || routes.find((r) => r.running);
  const batch = useLive((s) => s.batches.find((b) => b.id === ret?.batchId));

  if (!ret) return <LoadingState rows={5} />;
  const stepIdx = RET_STEP_IDX[ret.status] ?? 0;
  const stopNo = route ? (route.stops.findIndex((s) => s.status === "CURRENT" || s.status === "ARRIVED") + 1) || 1 : 1;

  return (
    <div>
      <PageHeader title="Track your pickup" subtitle={`${ret.drugName} · ${ret.batchId}`} icon={Truck} />
      <div className="relative">
        <LiveMap height={420}
          center={route ? [route.pos.lat, route.pos.lng] : [13.0827, 80.2707]}
          vehicles={route ? [{ pos: route.pos, reg: route.vehicleReg, agent: route.agentName, eta: route.etaMin }] : []}
          stops={route?.stops || []}
          routePath={route?.path}
          follow
        />
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="absolute left-4 top-4 z-[500] w-64 rounded-clay bg-clay-card/95 p-4 shadow-pop ring-1 ring-clay-line backdrop-blur">
          <div className="text-xs font-semibold uppercase tracking-wide text-clay-muted">Your pickup</div>
          <div className="mt-1 text-lg font-extrabold text-clay-ink">Stop {stopNo} of {route?.stops.length || 1}</div>
          <div className="mt-1 flex items-center gap-1.5 text-sm text-accent-ink"><Clock className="h-4 w-4" /> ETA {route?.etaMin ?? "—"} minutes</div>
          <Button variant="soft" size="sm" className="mt-3 w-full" onClick={() => toast.info(`Calling ${route?.agentName || "agent"}…`)} data-testid="call-agent">
            <Phone className="h-4 w-4" /> Call agent
          </Button>
        </motion.div>
      </div>

      <Card className="mt-4"><SectionTitle>Pickup status</SectionTitle><Stepper steps={RET_STEPS} current={stepIdx} /></Card>

      <Card className="mt-4">
        <SectionTitle>Timeline</SectionTitle>
        {batch ? <HashChain events={batch.events.filter((e) => !["SALE", "REGISTERED"].includes(e.type))} /> : <p className="text-sm text-clay-muted">No events yet.</p>}
      </Card>
    </div>
  );
}

// ============================ SALES ==========================================
export function Sales() {
  const pid = usePid();
  const user = useAuth((s) => s.user);
  const batches = useLive((s) => s.batches.filter((b) => b.pharmacyId === pid && ["ACTIVE", "EXPIRING_SOON"].includes(b.status)));
  const recent = useLive((s) => s.sales.filter((x) => x.pharmacyId === pid).slice(0, 12));
  const batchName = useLive((s) => (id) => s.batches.find((b) => b.id === id)?.drugName);
  const [sel, setSel] = useState("");
  const [units, setUnits] = useState("1");

  const record = async (batchId, u) => {
    const res = await batchSvc.simulateSale(batchId, u, { id: pid, name: user?.name, role: "RETAILER" });
    if (res) toast.success(`Recorded ${u} sale${u > 1 ? "s" : ""} — ${res.quantity} left`);
    else toast.error("Not enough stock");
  };

  return (
    <div>
      <PageHeader title="Sales" subtitle="Record daily sales — inventory updates live" icon={ShoppingCart} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <SectionTitle>Record a sale</SectionTitle>
          <div className="space-y-3">
            <Select value={sel} onChange={(e) => setSel(e.target.value)} data-testid="sale-batch"><option value="">Pick a batch…</option>{batches.map((b) => <option key={b.id} value={b.id}>{b.drugName} ({b.quantity})</option>)}</Select>
            <Input type="number" min="1" value={units} onChange={(e) => setUnits(e.target.value)} data-testid="sale-units" />
            <Button className="w-full" disabled={!sel} onClick={() => record(sel, Number(units))} data-testid="record-sale">Record sale</Button>
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <SectionTitle>Quick simulate</SectionTitle>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {batches.slice(0, 8).map((b) => (
              <div key={b.id} className="flex items-center gap-3 rounded-2xl bg-clay-surface p-3">
                <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{b.drugName}</div><div className="text-xs text-clay-muted">{b.quantity} units</div></div>
                <Button variant="soft" size="sm" onClick={() => record(b.id, 1)} data-testid={`sim-sale-${b.id}`}>Simulate 1 sale</Button>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <Card className="mt-4 p-0">
        <div className="p-5 pb-0"><SectionTitle>Recent sales</SectionTitle></div>
        {recent.length === 0 ? <p className="px-5 pb-6 text-sm text-clay-muted">No sales recorded yet.</p> : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted"><th className="px-5 py-3">Drug</th><th className="px-5 py-3">Units</th><th className="px-5 py-3">Time</th></tr></thead>
            <tbody>{recent.map((s) => <tr key={s.id} className="border-b border-clay-line/60"><td className="px-5 py-3 font-medium text-clay-ink">{batchName(s.batchId)}</td><td className="px-5 py-3 tnum">{s.units}</td><td className="px-5 py-3 text-clay-muted">{formatDateTime(s.ts)}</td></tr>)}</tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

// ============================ ANALYTICS ======================================
export function Analytics() {
  const pid = usePid();
  const { data, isLoading } = useQuery({ queryKey: ["ph-analytics", pid], queryFn: () => analytics.pharmacyAnalytics(pid) });
  if (isLoading || !data) return <LoadingState rows={6} />;
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const hours = Array.from({ length: 14 }, (_, i) => i + 8);
  return (
    <div>
      <PageHeader title="Analytics" subtitle="Sales, stock health & returns" icon={TrendingUp} />
      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
        <KpiCard label="Returns YTD" value={data.kpis.returnsYTD} tint="mint" />
        <KpiCard label="Value returned" value={inr(data.kpis.valueReturned)} tint="accent" />
        <KpiCard label="Dispute rate" value={`${data.kpis.disputeRate}%`} tint="amber" />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Monthly sales volume (12 months)"><SmoothLine data={data.monthlySales} xKey="month" yKey="units" /></ChartCard>
        <ChartCard title="Top 10 selling drugs"><RoundedBars data={data.topDrugs} xKey="name" yKey="units" horizontal color="#3fbf9a" /></ChartCard>
        <ChartCard title="Stock composition"><Donut data={data.composition} centerLabel="Batches" /></ChartCard>
        <ChartCard title="Expiry by month · by category" height={260}><StackedBars data={data.expiryByMonth} xKey="month" keys={["oncology", "antibiotics", "cardiovascular", "other"]} /></ChartCard>
      </div>
      <Card className="mt-4"><SectionTitle>Sales pattern · day × hour</SectionTitle><Heatmap data={data.heatmap} days={days} hours={hours} /></Card>
    </div>
  );
}

// ============================ ALERTS =========================================
export function Alerts() {
  const pid = usePid();
  const { data: alerts, isLoading } = useQuery({ queryKey: ["alerts"], queryFn: () => listAlerts() });
  const [dismissed, setDismissed] = useState([]);
  const nav = useNavigate();
  if (isLoading) return <LoadingState />;

  const mine = (alerts || []).filter((a) => a.entityId === pid || a.district === "Chennai");
  const groups = {
    "Expiring Soon": mine.filter((a) => a.type === "EXPIRY"),
    "Disputes on Your Returns": mine.filter((a) => a.type === "QUANTITY_MISMATCH"),
    "Pickup Updates": mine.filter((a) => a.type === "REENTRY" || a.type === "PATIENT_REPORT"),
  };
  // ensure at least expiring soon shows from batches
  return (
    <div>
      <PageHeader title="Alerts" subtitle="Grouped by what needs your attention" icon={AlertTriangle} />
      <div className="space-y-6">
        {Object.entries(groups).map(([title, items]) => (
          <div key={title}>
            <SectionTitle>{title} <Badge tone="gray">{items.filter((i) => !dismissed.includes(i.id)).length}</Badge></SectionTitle>
            {items.filter((i) => !dismissed.includes(i.id)).length === 0 ? (
              <p className="rounded-clay bg-clay-surface px-4 py-6 text-center text-sm text-clay-muted ring-1 ring-clay-line/60">Nothing here right now.</p>
            ) : (
              <div className="space-y-2">
                {items.filter((i) => !dismissed.includes(i.id)).map((a) => (
                  <motion.div key={a.id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3 rounded-clay bg-clay-card p-4 ring-1 ring-clay-line/60">
                    <span className={cn("h-2.5 w-2.5 rounded-full", a.severity === "critical" ? "bg-rose2" : "bg-amber2")} />
                    <button className="flex-1 text-left" onClick={() => nav(`/pharmacy/inventory/${a.batchId}`)}>
                      <div className="text-sm font-medium text-clay-ink">{a.message}</div><div className="text-xs text-clay-muted">{timeAgo(a.ts)}</div>
                    </button>
                    <button onClick={() => setDismissed((d) => [...d, a.id])} className="rounded-full p-1.5 text-clay-muted hover:bg-clay-line" data-testid={`dismiss-${a.id}`}><X className="h-4 w-4" /></button>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================ PROFILE ========================================
export function Profile() {
  const pid = usePid();
  const pharm = useLive((s) => s.pharmacies.find((p) => p.id === pid));
  if (!pharm) return null;
  return (
    <div className="max-w-2xl">
      <PageHeader title="Profile" subtitle="Your pharmacy on the DOT registry" icon={ShieldCheck} />
      <Card className="space-y-3">
        <Meta k="Name" v={pharm.name} /><Meta k="License" v={pharm.licenseNo} /><Meta k="Address" v={pharm.address} /><Meta k="Phone" v={pharm.phone} /><Meta k="City" v={pharm.city} />
      </Card>
    </div>
  );
}
