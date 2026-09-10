import React, { useState, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Boxes, FileCheck2, Trash2, AlertTriangle, ShieldAlert, Building2, Calendar,
  Map as MapIcon, TrendingUp, Search, ChevronRight, Upload, FileText, CheckCircle2, Lock,
} from "lucide-react";

import { useAuth } from "../store/authStore";
import { useLive } from "../hooks/useDb";
import { useAppMutation } from "../hooks/useAppMutation";
import * as batchSvc from "../services/batchService";
import * as mfrSvc from "../services/manufacturerService";
import * as ref from "../services/referenceService";
import * as analytics from "../services/analyticsService";
import { listAlerts } from "../services/alertService";

import { Card, Button, Input, Select, Label, Badge } from "../components/ui";
import { KpiCard, KpiSkeleton, PageHeader, SectionTitle, StatusPill, EmptyState, LoadingState, HashChain } from "../components/common";
import LiveMap from "../components/maps/LiveMap";
import { SmoothLine, RoundedBars, FlowDiagram, ChartCard } from "../components/charts";
import { formatDate, timeAgo, cn, inr } from "../lib/utils";

const useMid = () => useAuth((s) => s.user?.entityId) || "mfr_1";

// ============================ DASHBOARD ======================================
export function Dashboard() {
  const mid = useMid();
  const { data: stats, isLoading } = useQuery({ queryKey: ["mfr-stats", mid], queryFn: () => analytics.manufacturerStats(mid) });
  const { data: alerts } = useQuery({ queryKey: ["alerts"], queryFn: () => listAlerts({ manufacturerId: mid }) });
  const routes = useLive((s) => s.routes.filter((r) => r.running));
  const reentry = (alerts || []).filter((a) => a.type === "REENTRY").slice(0, 4);

  return (
    <div>
      <PageHeader title="Manufacturer console" subtitle="Your batches across the reverse chain" />
      {isLoading ? <KpiSkeleton /> : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
          <KpiCard label="Awaiting pickup" value={stats.awaitingPickup} icon={Boxes} tint="accent" />
          <KpiCard label="Certs pending" value={stats.certsPending} icon={FileCheck2} tint="amber" />
          <KpiCard label="Destroyed (mo)" value={stats.destroyedThisMonth} icon={Trash2} tint="mint" />
          <KpiCard label="Active recalls" value={stats.activeRecalls} icon={AlertTriangle} tint="rose" />
          <KpiCard label="Alerts on batches" value={stats.alertsOnBatches} icon={ShieldAlert} tint="lilac" />
        </div>
      )}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-0"><div className="p-5 pb-3"><SectionTitle>Fleet carrying your batches</SectionTitle></div>
          <LiveMap height={340} vehicles={routes.map((r) => ({ pos: r.pos, reg: r.vehicleReg, agent: r.agentName, eta: r.etaMin }))} stops={routes.flatMap((r) => r.stops)} />
        </Card>
        <Card tint="rose">
          <SectionTitle>Re-entry alerts on your batches</SectionTitle>
          {reentry.length === 0 ? <p className="py-6 text-center text-sm text-clay-muted">No re-entry alerts. Brand integrity intact.</p> : (
            <div className="space-y-2">
              {reentry.map((a) => (
                <div key={a.id} className="flex items-start gap-3 rounded-2xl bg-white/70 p-3">
                  <span className="mt-1 h-2.5 w-2.5 rounded-full bg-rose2" />
                  <div className="flex-1"><div className="text-sm font-medium text-clay-ink">{a.message}</div><div className="text-xs text-clay-muted">{timeAgo(a.ts)} · {a.district}</div></div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ============================ INBOX ==========================================
export function MInbox() {
  const mid = useMid();
  const nav = useNavigate();
  const { data: rows, isLoading } = useQuery({ queryKey: ["mfr-inbox", mid], queryFn: () => mfrSvc.listInbox(mid) });
  const [sel, setSel] = useState([]);
  if (isLoading) return <LoadingState />;
  return (
    <div>
      <PageHeader title="Confirmed returns" subtitle="Forwarded batches awaiting facility scheduling" icon={Boxes}
        actions={<Button disabled={sel.length === 0} onClick={() => nav("/manufacturer/facilities/schedule", { state: { batchIds: sel } })} data-testid="schedule-selected"><Calendar className="h-4 w-4" /> Schedule ({sel.length})</Button>} />
      {(rows || []).length === 0 ? <EmptyState title="Inbox empty" subtitle="Confirmed returns from distributors will appear here." icon={Boxes} /> : (
        <Card className="p-0">
          <div className="flex items-center gap-2 border-b border-clay-line px-5 py-3 text-sm text-clay-muted">
            <input type="checkbox" checked={sel.length === rows.length} onChange={(e) => setSel(e.target.checked ? rows.map((r) => r.batchId) : [])} data-testid="inbox-select-all" /> Select all
          </div>
          {rows.map((r) => (
            <div key={r.id} className="flex items-center gap-3 border-b border-clay-line/60 px-5 py-3.5 hover:bg-clay-surface">
              <input type="checkbox" checked={sel.includes(r.batchId)} onChange={(e) => setSel((s) => e.target.checked ? [...s, r.batchId] : s.filter((x) => x !== r.batchId))} data-testid={`inbox-${r.batchId}`} />
              <button className="flex-1 text-left" onClick={() => nav(`/manufacturer/inbox/${r.batchId}`)}>
                <div className="text-sm font-semibold text-clay-ink">{r.drugName}</div><div className="font-mono text-xs text-clay-muted">{r.batchId}</div>
              </button>
              <Badge tone="mint">{r.quantityReceived ?? r.quantityClaimed} units</Badge>
              <ChevronRight className="h-4 w-4 text-clay-muted" />
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

export function InboxBatch() {
  const { batchId } = useParams();
  const nav = useNavigate();
  const { data: batch } = useQuery({ queryKey: ["batch", batchId], queryFn: () => batchSvc.getBatch(batchId) });
  if (!batch) return <LoadingState rows={4} />;
  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-3 text-sm font-semibold text-clay-muted">← Back</button>
      <PageHeader title={batch.drugName} subtitle={batch.id} actions={<>
        <Button variant="soft" onClick={() => nav("/manufacturer/facilities/schedule", { state: { batchIds: [batch.id] } })}><Calendar className="h-4 w-4" /> Schedule pickup</Button>
        <Button onClick={() => nav(`/manufacturer/certificates/upload/${batch.id}`)}><FileCheck2 className="h-4 w-4" /> Upload certificate</Button>
      </>} />
      <Card><SectionTitle>History · hash-chained</SectionTitle><HashChain events={batch.events} /></Card>
    </div>
  );
}

// ============================ FACILITIES =====================================
export function Facilities() {
  const nav = useNavigate();
  const { data: facilities } = useQuery({ queryKey: ["facilities"], queryFn: () => ref.getFacilities() });
  return (
    <div>
      <PageHeader title="Licensed facilities" subtitle="Biomedical waste partners" icon={Building2}
        actions={<Button onClick={() => nav("/manufacturer/facilities/schedule")} data-testid="schedule-pickup-btn"><Calendar className="h-4 w-4" /> Schedule pickup</Button>} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {(facilities || []).map((f) => (
          <Card key={f.id} tint="lilac">
            <div className="flex items-center gap-3"><span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-white shadow-clay"><Building2 className="h-5 w-5 text-lilac" /></span>
              <div><div className="font-bold text-clay-ink">{f.name}</div><div className="text-xs text-clay-muted">{f.city}</div></div></div>
            <div className="mt-3 text-xs text-clay-muted">License {f.licenseNo}</div>
          </Card>
        ))}
      </div>
    </div>
  );
}

export function FacilitiesSchedule() {
  const mid = useMid();
  const nav = useNavigate();
  const user = useAuth((s) => s.user);
  const { data: facilities } = useQuery({ queryKey: ["facilities"], queryFn: () => ref.getFacilities() });
  const { data: inbox } = useQuery({ queryKey: ["mfr-inbox", mid], queryFn: () => mfrSvc.listInbox(mid) });
  const preselected = (typeof window !== "undefined" && window.history.state?.usr?.batchIds) || [];
  const [sel, setSel] = useState(preselected);
  const [facility, setFacility] = useState("");
  const [date, setDate] = useState("");

  const mut = useAppMutation(() => mfrSvc.scheduleFacility(sel, facility, date, { id: mid, name: user?.name, role: "MANUFACTURER" }), {
    onSuccess: () => { toast.success("Facility pickup scheduled"); nav("/manufacturer/certificates"); },
  });

  return (
    <div className="max-w-2xl">
      <PageHeader title="Schedule facility pickup" subtitle="Assign confirmed batches to a licensed facility" icon={Calendar} />
      <Card className="space-y-4">
        <div>
          <Label>Batches</Label>
          <div className="space-y-2">
            {(inbox || []).length === 0 && <p className="text-sm text-clay-muted">No confirmed batches available.</p>}
            {(inbox || []).map((r) => (
              <label key={r.batchId} className="flex items-center gap-3 rounded-2xl bg-clay-surface p-3 ring-1 ring-clay-line/60" data-testid={`sched-batch-${r.batchId}`}>
                <input type="checkbox" checked={sel.includes(r.batchId)} onChange={(e) => setSel((s) => e.target.checked ? [...s, r.batchId] : s.filter((x) => x !== r.batchId))} />
                <span className="flex-1 text-sm font-semibold text-clay-ink">{r.drugName}</span><span className="font-mono text-xs text-clay-muted">{r.batchId}</span>
              </label>
            ))}
          </div>
        </div>
        <div><Label>Facility</Label><Select value={facility} onChange={(e) => setFacility(e.target.value)} data-testid="sched-facility"><option value="">Choose facility…</option>{(facilities || []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</Select></div>
        <div><Label>Pickup date</Label><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="sched-date" /></div>
        <Button className="w-full" disabled={sel.length === 0 || !facility || !date || mut.isPending} onClick={() => mut.mutate()} data-testid="confirm-schedule">Confirm schedule</Button>
      </Card>
    </div>
  );
}

// ============================ CERTIFICATES ===================================
export function Certificates() {
  const mid = useMid();
  const nav = useNavigate();
  const batches = useLive((s) => s.batches.filter((b) => b.manufacturerId === mid && (b.scheduledFacility || b.status === "DESTROYED" || b.events.some((e) => e.type === "FORWARDED"))));
  return (
    <div>
      <PageHeader title="Destruction certificates" subtitle="Bind certificates to confirmed batches" icon={FileCheck2} />
      {batches.length === 0 ? <EmptyState title="No batches to certify" subtitle="Schedule facility pickups first." icon={FileCheck2} /> : (
        <Card className="p-0">
          {batches.map((b) => {
            const elig = mfrSvc.certEligibility(b);
            return (
              <div key={b.id} className="flex items-center gap-3 border-b border-clay-line/60 px-5 py-3.5">
                <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{b.drugName}</div><div className="font-mono text-xs text-clay-muted">{b.id}</div></div>
                <StatusPill status={b.status} />
                {b.status === "DESTROYED" ? <Badge tone="gray">{b.certId}</Badge> : (
                  <Button size="sm" variant={elig.eligible ? "primary" : "outline"} onClick={() => nav(`/manufacturer/certificates/upload/${b.id}`)} data-testid={`cert-${b.id}`}>
                    {elig.eligible ? <><Upload className="h-4 w-4" /> Upload</> : <><Lock className="h-4 w-4" /> Blocked</>}
                  </Button>
                )}
              </div>
            );
          })}
        </Card>
      )}
    </div>
  );
}

export function CertUpload() {
  const { batchId } = useParams();
  const mid = useMid();
  const nav = useNavigate();
  const user = useAuth((s) => s.user);
  const { data: batch } = useQuery({ queryKey: ["batch", batchId], queryFn: () => batchSvc.getBatch(batchId) });
  const [file, setFile] = useState(false);

  const mut = useAppMutation(() => mfrSvc.uploadCertificate(batchId, { certId: `CERT-${batch.code}-2026`, fileName: "destruction-cert.pdf" }, { id: mid, name: user?.name, role: "MANUFACTURER" }), {
    onSuccess: () => { toast.success("Certificate bound — batch DESTROYED"); nav("/manufacturer/certificates"); },
    onError: (err) => toast.error(err.message || "Certificate upload blocked"),
  });

  if (!batch) return <LoadingState rows={4} />;
  const elig = mfrSvc.certEligibility(batch);

  return (
    <div className="max-w-2xl">
      <PageHeader title="Upload destruction certificate" subtitle={`${batch.drugName} · ${batch.id}`} icon={FileCheck2} />
      <Card className="mb-4">
        <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <Meta k="Drug" v={batch.drugName} /><Meta k="Batch" v={batch.id} /><Meta k="Status" v={<StatusPill status={batch.status} />} /><Meta k="Facility" v={batch.scheduledFacility?.name || "—"} />
        </div>
      </Card>

      {!elig.eligible ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-4 flex items-center gap-3 rounded-clay bg-rose2-soft px-5 py-4 ring-1 ring-rose2/20" data-testid="cert-blocked-banner">
          <Lock className="h-6 w-6 text-rose2" />
          <div className="text-sm font-semibold text-[#a8443b]">{elig.reason}</div>
        </motion.div>
      ) : null}

      <Card>
        <SectionTitle>Certificate PDF</SectionTitle>
        <button disabled={!elig.eligible} onClick={() => { setFile(true); toast.success("PDF attached"); }}
          className={cn("flex w-full flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed py-10 text-sm transition-colors",
            !elig.eligible ? "cursor-not-allowed border-clay-line bg-clay-surface text-clay-muted opacity-50" : file ? "border-mint bg-mint-soft text-[#1f8a6a]" : "border-clay-line text-clay-muted hover:bg-clay-surface")}
          data-testid="cert-upload-area">
          {file ? <CheckCircle2 className="h-8 w-8" /> : <FileText className="h-8 w-8" />}
          {file ? "destruction-cert.pdf attached ✓" : "Drop or select the certificate PDF"}
        </button>
        {file && elig.eligible && (
          <div className="mt-4 rounded-2xl bg-clay-surface p-3 text-sm">
            <div className="text-xs uppercase tracking-wide text-clay-muted">This certificate covers</div>
            <div className="mt-1 font-mono text-clay-ink">{batch.id}</div>
          </div>
        )}
        <Button className="mt-4 w-full" disabled={!elig.eligible || !file || mut.isPending} onClick={() => mut.mutate()} data-testid="cert-submit">Submit — mark destroyed</Button>
      </Card>
    </div>
  );
}
function Meta({ k, v }) { return <div><div className="text-xs uppercase tracking-wide text-clay-muted">{k}</div><div className="font-semibold text-clay-ink">{v}</div></div>; }

// ============================ FLEET MAP ======================================
export function FleetMap() {
  const routes = useLive((s) => s.routes.filter((r) => r.running));
  const distributors = useLive((s) => s.distributors);
  const [distFilter, setDistFilter] = useState("");
  const shown = routes.filter((r) => !distFilter || r.distributorId === distFilter);
  return (
    <div>
      <PageHeader title="Fleet map" subtitle="Distributor vehicles carrying your batches" icon={MapIcon} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <Card className="space-y-3">
          <SectionTitle>Filters</SectionTitle>
          <div><Label>Distributor</Label><Select value={distFilter} onChange={(e) => setDistFilter(e.target.value)} data-testid="fleet-dist-filter"><option value="">All distributors</option>{distributors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></div>
          <div className="space-y-2 pt-2">
            {shown.map((r) => (
              <div key={r.id} className="rounded-2xl bg-clay-surface p-3 text-sm"><div className="font-semibold text-clay-ink">{r.vehicleReg}</div><div className="text-xs text-clay-muted">{r.agentName} · ETA {r.etaMin}m · next: {r.stops.find((s) => s.status === "CURRENT")?.pharmacyName || "—"}</div></div>
            ))}
            {shown.length === 0 && <p className="text-sm text-clay-muted">No vehicles in transit.</p>}
          </div>
        </Card>
        <Card className="p-0 lg:col-span-3">
          <LiveMap height={480} vehicles={shown.map((r) => ({ pos: r.pos, reg: r.vehicleReg, agent: r.agentName, eta: r.etaMin }))} stops={shown.flatMap((r) => r.stops)} routePath={shown[0]?.path} />
        </Card>
      </div>
    </div>
  );
}

// ============================ BATCHES ========================================
export function Batches() {
  const mid = useMid();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const { data: batches, isLoading } = useQuery({ queryKey: ["batches"], queryFn: () => batchSvc.listBatches() });
  const alerts = useLive((s) => s.alerts);
  const rows = useMemo(() => (batches || []).filter((b) => b.manufacturerId === mid).filter((b) => !q || b.drugName.toLowerCase().includes(q.toLowerCase()) || b.id.toLowerCase().includes(q.toLowerCase())), [batches, mid, q]);
  if (isLoading) return <LoadingState />;
  const alertCount = (id) => alerts.filter((a) => a.batchId === id).length;
  return (
    <div>
      <PageHeader title="All batches" subtitle="Every batch you've manufactured" icon={Boxes} />
      <Card className="mb-4"><div className="relative"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-clay-muted" /><Input className="pl-10" placeholder="Search batch or drug…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="mfr-batch-search" /></div></Card>
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted"><th className="px-5 py-3">Batch</th><th className="px-5 py-3">Drug</th><th className="px-5 py-3">Expiry</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Holder</th><th className="px-5 py-3">Events</th><th className="px-5 py-3">Alerts</th></tr></thead>
            <tbody>{rows.map((b) => (
              <tr key={b.id} className="cursor-pointer border-b border-clay-line/60 hover:bg-clay-surface" onClick={() => nav(`/manufacturer/batches/${b.id}`)} data-testid={`mfr-batch-${b.id}`}>
                <td className="px-5 py-3 font-mono text-xs text-clay-muted">{b.id}</td><td className="px-5 py-3 font-semibold text-clay-ink">{b.drugName}</td>
                <td className="px-5 py-3">{formatDate(b.expiryDate)}</td><td className="px-5 py-3"><StatusPill status={b.status} /></td>
                <td className="px-5 py-3 text-clay-muted">{b.holder?.name}</td><td className="px-5 py-3 tnum">{b.events.length}</td>
                <td className="px-5 py-3">{alertCount(b.id) > 0 ? <Badge tone="rose">{alertCount(b.id)}</Badge> : <span className="text-clay-muted">—</span>}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

export function MBatchDetail() {
  const { batchId } = useParams();
  const nav = useNavigate();
  const { data: batch } = useQuery({ queryKey: ["batch", batchId], queryFn: () => batchSvc.getBatch(batchId) });
  if (!batch) return <LoadingState rows={5} />;
  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-3 text-sm font-semibold text-clay-muted">← Back</button>
      <Card className="mb-4"><div className="flex items-center gap-3"><h1 className="text-2xl font-extrabold text-clay-ink">{batch.drugName}</h1><StatusPill status={batch.status} /></div><p className="mt-1 font-mono text-sm text-clay-muted">{batch.id}</p></Card>
      <Card><SectionTitle>Full history · hash-chained</SectionTitle><HashChain events={batch.events} showGps /></Card>
    </div>
  );
}

// ============================ ANALYTICS ======================================
export function Analytics() {
  const mid = useMid();
  const { data, isLoading } = useQuery({ queryKey: ["mfr-analytics", mid], queryFn: () => analytics.manufacturerAnalytics(mid) });
  const facilities = useLive((s) => s.facilities);
  const distributors = useLive((s) => s.distributors);
  const pharmacies = useLive((s) => s.pharmacies);
  if (isLoading || !data) return <LoadingState rows={6} />;
  const flowCols = [
    { title: "Pharmacies", items: pharmacies.slice(0, 4).map((p, i) => ({ name: p.name.split("—")[0].trim(), value: 8 + i * 3 })) },
    { title: "Distributors", items: distributors.map((d, i) => ({ name: d.name.split(" ")[0], value: 20 + i * 6 })) },
    { title: "Facilities", items: facilities.map((f, i) => ({ name: f.name.split(" ")[0], value: 14 + i * 4 })) },
  ];
  return (
    <div>
      <PageHeader title="Analytics" subtitle="Destruction, compliance & re-entry" icon={TrendingUp} />
      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-3">
        <KpiCard label="Compliance rate" value={`${data.kpis.complianceRate}%`} tint="mint" />
        <KpiCard label="Value destroyed" value={inr(data.kpis.valueDestroyed)} tint="accent" />
        <KpiCard label="Avg chain time" value={data.kpis.avgChain} tint="lilac" />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="Batches destroyed per month (24 mo)"><SmoothLine data={data.destroyed} xKey="month" yKey="count" /></ChartCard>
        <ChartCard title="Top drugs by return volume"><RoundedBars data={data.topDrugs} xKey="name" yKey="value" horizontal color="#e0a53d" height={280} /></ChartCard>
        <ChartCard title="Re-entry alerts per month"><RoundedBars data={data.reentry} xKey="month" yKey="alerts" color="#e0655b" /></ChartCard>
        <Card><SectionTitle>Flow · pharmacies → distributors → facilities</SectionTitle><FlowDiagram columns={flowCols} /></Card>
      </div>
      <Card className="mt-4 p-0"><div className="p-5 pb-3"><SectionTitle>Geographic returns · bubble map</SectionTitle></div><LiveMap height={360} bubbles={data.bubbles} /></Card>
    </div>
  );
}

export function Profile() {
  const mid = useMid();
  const m = useLive((s) => s.manufacturers.find((x) => x.id === mid));
  if (!m) return null;
  return (
    <div className="max-w-2xl">
      <PageHeader title="Profile" subtitle="Manufacturer on the DOT registry" icon={Building2} />
      <Card className="space-y-3"><Meta k="Name" v={m.name} /><Meta k="License" v={m.licenseNo} /><Meta k="Address" v={m.address} /><Meta k="City" v={m.city} /></Card>
    </div>
  );
}
