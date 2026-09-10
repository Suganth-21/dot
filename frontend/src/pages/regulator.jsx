import React, { useState, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  AlertTriangle, Boxes, Trash2, Clock, Users, Map as MapIcon, TrendingUp, FileText,
  Search, ChevronRight, ShieldCheck, Printer, Download, Landmark, Activity, Lock,
} from "lucide-react";

import { useLive } from "../hooks/useDb";
import { useAppMutation } from "../hooks/useAppMutation";
import * as batchSvc from "../services/batchService";
import * as alertSvc from "../services/alertService";
import * as entitySvc from "../services/entityService";
import * as analytics from "../services/analyticsService";

import { Card, Button, Input, Select, Label, Badge } from "../components/ui";
import { KpiCard, KpiSkeleton, PageHeader, SectionTitle, StatusPill, EmptyState, LoadingState, HashChain } from "../components/common";
import LiveMap from "../components/maps/LiveMap";
import { MultiLine, StackedBars, RoundedBars, NetworkGraph, ChartCard } from "../components/charts";
import { formatDate, formatDateTime, timeAgo, cn, inr } from "../lib/utils";

// ============================ DASHBOARD ======================================
export function Dashboard() {
  const nav = useNavigate();
  const { data: stats, isLoading } = useQuery({ queryKey: ["reg-stats"], queryFn: () => analytics.regulatorStats() });
  const { data: alerts } = useQuery({ queryKey: ["alerts"], queryFn: () => alertSvc.listAlerts() });
  const routes = useLive((s) => s.routes.filter((r) => r.running));
  const districts = ["Chennai", "Coimbatore", "Madurai", "Trichy", "Salem", "Tirunelveli"];
  const compliance = { Chennai: 92, Coimbatore: 85, Madurai: 78, Trichy: 88, Salem: 74, Tirunelveli: 81 };
  const live = (alerts || []).filter((a) => a.status !== "CLOSED");

  return (
    <div>
      <PageHeader title="Drug Controller — CDSCO Tamil Nadu" subtitle="National reverse-logistics compliance monitor" icon={Landmark} />
      {isLoading ? <KpiSkeleton n={4} /> : (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <KpiCard label="In return pipeline" value={stats.inPipeline} icon={Boxes} tint="accent" />
          <KpiCard label="Destroyed this week" value={stats.destroyedThisWeek} icon={Trash2} tint="mint" />
          <KpiCard label="Active alerts" value={stats.activeAlerts} icon={AlertTriangle} tint="rose" />
          <KpiCard label="Disputes > 7 days" value={stats.oldDisputes} icon={Clock} tint="amber" />
        </div>
      )}

      <Card className="mt-6" data-testid="reg-live-alerts">
        <SectionTitle right={<Button variant="soft" size="sm" onClick={() => nav("/regulator/alerts")}>All alerts</Button>}>
          <span className="flex items-center gap-2"><span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-rose2 opacity-60" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose2" /></span> Live alert feed</span>
        </SectionTitle>
        {live.length === 0 ? <p className="py-8 text-center text-sm text-clay-muted">No active alerts.</p> : (
          <div className="max-h-[38vh] space-y-2 overflow-y-auto pr-1">
            {live.map((a) => (
              <motion.button key={a.id} layout initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                onClick={() => nav(`/regulator/alerts/${a.id}`)} data-testid={`reg-alert-${a.id}`}
                className="flex w-full items-center gap-3 rounded-2xl bg-clay-surface p-3 text-left hover:bg-clay-line">
                <StatusPill status={a.severity} />
                <div className="flex-1"><div className="text-sm font-medium text-clay-ink">{a.message}</div><div className="text-xs text-clay-muted">{timeAgo(a.ts)} · {a.district} · <span className="capitalize">{a.drugCategory}</span></div></div>
                <ChevronRight className="h-4 w-4 text-clay-muted" />
              </motion.button>
            ))}
          </div>
        )}
      </Card>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="p-0 lg:col-span-2"><div className="p-5 pb-3"><SectionTitle>Active pickup routes</SectionTitle></div>
          <LiveMap height={340} vehicles={routes.map((r) => ({ pos: r.pos, reg: r.vehicleReg, agent: r.agentName, eta: r.etaMin }))} stops={routes.flatMap((r) => r.stops)} /></Card>
        <Card>
          <SectionTitle>Compliance by district</SectionTitle>
          <div className="space-y-3">
            {districts.map((d) => (
              <div key={d}>
                <div className="mb-1 flex items-center justify-between text-sm"><span className="font-medium text-clay-ink">{d}</span><span className="tnum text-clay-muted">{compliance[d]}%</span></div>
                <div className="h-2 overflow-hidden rounded-full bg-clay-line"><div className={cn("h-full rounded-full", compliance[d] >= 85 ? "bg-mint" : compliance[d] >= 78 ? "bg-amber2" : "bg-rose2")} style={{ width: `${compliance[d]}%` }} /></div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

// ============================ ALERTS =========================================
export function Alerts() {
  const nav = useNavigate();
  const { data: alerts, isLoading } = useQuery({ queryKey: ["alerts"], queryFn: () => alertSvc.listAlerts() });
  const [type, setType] = useState("");
  const [cat, setCat] = useState("");
  const [district, setDistrict] = useState("");
  const rows = useMemo(() => (alerts || []).filter((a) => (!type || a.type === type) && (!cat || a.drugCategory === cat) && (!district || a.district === district)), [alerts, type, cat, district]);

  const actMut = useAppMutation(({ id, status }) => alertSvc.updateAlertStatus(id, status, "Officer R. Menon"), {
    onSuccess: (_, v) => toast.success(`Alert ${v.status.toLowerCase()}`),
  });

  if (isLoading) return <LoadingState />;
  return (
    <div>
      <PageHeader title="Alerts" subtitle="Re-entry, mismatch, certificate & public reports" icon={AlertTriangle} />
      <Card className="mb-4"><div className="flex flex-wrap gap-3">
        <Select className="max-w-[180px]" value={type} onChange={(e) => setType(e.target.value)} data-testid="alert-type-filter"><option value="">All types</option><option value="REENTRY">Re-entry</option><option value="QUANTITY_MISMATCH">Quantity mismatch</option><option value="CERT_MISMATCH">Certificate</option><option value="PATIENT_REPORT">Patient report</option></Select>
        <Select className="max-w-[170px]" value={cat} onChange={(e) => setCat(e.target.value)} data-testid="alert-cat-filter"><option value="">All categories</option><option value="oncology">Oncology</option><option value="antibiotics">Antibiotics</option><option value="cardiovascular">Cardiovascular</option><option value="other">Other</option></Select>
        <Select className="max-w-[160px]" value={district} onChange={(e) => setDistrict(e.target.value)} data-testid="alert-district-filter"><option value="">All districts</option>{["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem"].map((d) => <option key={d}>{d}</option>)}</Select>
      </div></Card>
      {rows.length === 0 ? <EmptyState title="No alerts match" icon={ShieldCheck} /> : (
        <div className="space-y-2">
          {rows.map((a) => (
            <Card key={a.id} className={cn("border-l-4", a.severity === "critical" ? "border-l-rose2" : a.severity === "high" ? "border-l-amber2" : "border-l-lilac")} data-testid={`alert-card-${a.id}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <button className="flex-1 text-left" onClick={() => nav(`/regulator/alerts/${a.id}`)}>
                  <div className="flex items-center gap-2"><StatusPill status={a.severity} /><Badge tone="gray">{a.type.replace("_", " ")}</Badge><span className="text-xs capitalize text-clay-muted">{a.drugCategory}</span></div>
                  <div className="mt-1.5 text-sm font-semibold text-clay-ink">{a.message}</div>
                  <div className="text-xs text-clay-muted">{a.rule} · {a.district} · {timeAgo(a.ts)}</div>
                </button>
                <div className="flex items-center gap-2">
                  <StatusPill status={a.status} />
                  <Button size="sm" variant="outline" onClick={() => actMut.mutate({ id: a.id, status: "INVESTIGATING" })} data-testid={`investigate-${a.id}`}>Investigate</Button>
                  <Button size="sm" variant="danger" onClick={() => actMut.mutate({ id: a.id, status: "ESCALATED" })} data-testid={`escalate-${a.id}`}>Escalate</Button>
                  <Button size="sm" variant="ghost" onClick={() => actMut.mutate({ id: a.id, status: "CLOSED" })} data-testid={`close-${a.id}`}>Close</Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export function AlertDetail() {
  const { alertId } = useParams();
  const nav = useNavigate();
  const { data: alert } = useQuery({ queryKey: ["alert", alertId], queryFn: () => alertSvc.getAlert(alertId) });
  const actMut = useAppMutation(({ status }) => alertSvc.updateAlertStatus(alertId, status, "Officer R. Menon"), { onSuccess: (_, v) => toast.success(`Marked ${v.status.toLowerCase()}`) });
  if (!alert) return <LoadingState rows={5} />;
  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-3 text-sm font-semibold text-clay-muted">← Back to alerts</button>
      <PageHeader title="Alert investigation" subtitle={alert.message} icon={AlertTriangle}
        actions={<><Button variant="outline" onClick={() => actMut.mutate({ status: "INVESTIGATING" })} data-testid="detail-investigate">Mark investigating</Button><Button variant="danger" onClick={() => actMut.mutate({ status: "ESCALATED" })} data-testid="detail-escalate">Escalate</Button><Button variant="ghost" onClick={() => actMut.mutate({ status: "CLOSED" })} data-testid="detail-close">Close</Button></>} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card tint="rose" className="lg:col-span-1">
          <SectionTitle>Trigger</SectionTitle>
          <div className="space-y-2 text-sm">
            <Row k="Rule fired" v={alert.rule} /><Row k="Severity" v={<StatusPill status={alert.severity} />} /><Row k="Type" v={alert.type.replace("_", " ")} /><Row k="Entity" v={alert.entityName} /><Row k="District" v={alert.district} /><Row k="When" v={formatDateTime(alert.ts)} /><Row k="Status" v={<StatusPill status={alert.status} />} />
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <SectionTitle>Batch history embedded</SectionTitle>
          {alert.batch ? <HashChain events={alert.batch.events} showGps /> : <p className="text-sm text-clay-muted">No batch linked.</p>}
        </Card>
      </div>
      <Card className="mt-4">
        <SectionTitle>Officer action log</SectionTitle>
        <div className="space-y-2">
          {alert.auditTrail.map((t, i) => (
            <div key={i} className="flex items-center gap-3 rounded-2xl bg-clay-surface p-3 text-sm"><Activity className="h-4 w-4 text-accent-ink" /><div className="flex-1"><span className="font-semibold text-clay-ink">{t.action.replace(/_/g, " ")}</span> <span className="text-clay-muted">by {t.officer}</span></div><span className="text-xs text-clay-muted">{formatDateTime(t.ts)}</span></div>
          ))}
        </div>
      </Card>
    </div>
  );
}
function Row({ k, v }) { return <div className="flex items-center justify-between border-b border-white/40 py-2 last:border-0"><span className="text-xs uppercase tracking-wide text-clay-muted">{k}</span><span className="font-semibold text-clay-ink">{v}</span></div>; }

// ============================ BATCHES + AUDIT ================================
export function Batches() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const { data: batches, isLoading } = useQuery({ queryKey: ["batches"], queryFn: () => batchSvc.listBatches() });
  const rows = useMemo(() => (batches || []).filter((b) => !q || b.drugName.toLowerCase().includes(q.toLowerCase()) || b.id.toLowerCase().includes(q.toLowerCase())), [batches, q]);
  if (isLoading) return <LoadingState />;
  return (
    <div>
      <PageHeader title="Batch registry" subtitle="Audit any batch across the national ledger" icon={Boxes} />
      <Card className="mb-4"><div className="relative"><Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-clay-muted" /><Input className="pl-10" placeholder="Search batch or drug…" value={q} onChange={(e) => setQ(e.target.value)} data-testid="reg-batch-search" /></div></Card>
      <Card className="overflow-hidden p-0"><div className="overflow-x-auto"><table className="w-full text-sm">
        <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted"><th className="px-5 py-3">Batch</th><th className="px-5 py-3">Drug</th><th className="px-5 py-3">Category</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Holder</th><th className="px-5 py-3"></th></tr></thead>
        <tbody>{rows.slice(0, 60).map((b) => (
          <tr key={b.id} className="cursor-pointer border-b border-clay-line/60 hover:bg-clay-surface" onClick={() => nav(`/regulator/batches/${b.id}`)} data-testid={`reg-batch-${b.id}`}>
            <td className="px-5 py-3 font-mono text-xs text-clay-muted">{b.id}</td><td className="px-5 py-3 font-semibold text-clay-ink">{b.drugName}</td><td className="px-5 py-3 capitalize text-clay-muted">{b.category}</td><td className="px-5 py-3"><StatusPill status={b.status} /></td><td className="px-5 py-3 text-clay-muted">{b.holder?.name}</td><td className="px-5 py-3 text-right"><ChevronRight className="inline h-4 w-4 text-clay-muted" /></td>
          </tr>
        ))}</tbody>
      </table></div></Card>
    </div>
  );
}

export function BatchAudit() {
  const { batchId } = useParams();
  const nav = useNavigate();
  const { data: batch } = useQuery({ queryKey: ["batch", batchId], queryFn: () => batchSvc.getBatch(batchId) });
  if (!batch) return <LoadingState rows={6} />;
  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-3 text-sm font-semibold text-clay-muted">← Back</button>
      <PageHeader title="Audit trail" subtitle={`${batch.drugName} · ${batch.id}`} icon={ShieldCheck}
        actions={<Button variant="dark" onClick={() => { toast.success("Generating court-ready PDF…"); setTimeout(() => window.print(), 400); }} data-testid="export-pdf"><Printer className="h-4 w-4" /> Print / Export PDF</Button>} />
      <Card tint="accent" className="mb-4">
        <div className="flex items-start gap-3"><span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-clay"><Lock className="h-5 w-5 text-accent-ink" /></span>
          <div><div className="font-bold text-clay-ink">Tamper-evident record</div><p className="mt-0.5 text-sm text-clay-ink/80">This record cannot be silently rewritten — every event is cryptographically linked to the previous one and signed by its actor.</p></div></div>
      </Card>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2"><SectionTitle>Cryptographic event chain</SectionTitle><HashChain events={batch.events} showGps /></Card>
        <Card className="p-0"><div className="p-5 pb-3"><SectionTitle>Event GPS trail</SectionTitle></div>
          <LiveMap height={420} markers={batch.events.map((e, i) => ({ lat: e.gps.lat, lng: e.gps.lng, label: `${i + 1}. ${e.type}`, color: "#5b6cff" }))} routePath={batch.events.map((e) => e.gps)} center={[batch.events[0]?.gps.lat || 13.08, batch.events[0]?.gps.lng || 80.27]} />
        </Card>
      </div>
    </div>
  );
}

// ============================ ENTITIES =======================================
export function Entities() {
  const nav = useNavigate();
  const { data: rows, isLoading } = useQuery({ queryKey: ["entities"], queryFn: () => entitySvc.listEntities() });
  if (isLoading) return <LoadingState />;
  return (
    <div>
      <PageHeader title="Entities" subtitle="Compliance profiles for every registered party" icon={Users} />
      <Card className="overflow-hidden p-0"><div className="overflow-x-auto"><table className="w-full text-sm">
        <thead><tr className="border-b border-clay-line text-left text-xs uppercase tracking-wide text-clay-muted"><th className="px-5 py-3">Entity</th><th className="px-5 py-3">Type</th><th className="px-5 py-3">City</th><th className="px-5 py-3">Score</th><th className="px-5 py-3">Alerts</th><th className="px-5 py-3">Risk</th><th className="px-5 py-3"></th></tr></thead>
        <tbody>{(rows || []).map((e) => (
          <tr key={e.id} className="cursor-pointer border-b border-clay-line/60 hover:bg-clay-surface" onClick={() => nav(`/regulator/entities/${e.id}`)} data-testid={`entity-${e.id}`}>
            <td className="px-5 py-3 font-semibold text-clay-ink">{e.name}</td><td className="px-5 py-3 text-clay-muted">{e.type}</td><td className="px-5 py-3 text-clay-muted">{e.city}</td>
            <td className="px-5 py-3"><span className={cn("font-bold tnum", e.score >= 80 ? "text-mint" : e.score >= 55 ? "text-amber2" : "text-rose2")}>{e.score}</span></td>
            <td className="px-5 py-3 tnum">{e.alertsOn}</td><td className="px-5 py-3"><StatusPill status={e.risk} /></td><td className="px-5 py-3 text-right"><ChevronRight className="inline h-4 w-4 text-clay-muted" /></td>
          </tr>
        ))}</tbody>
      </table></div></Card>
    </div>
  );
}

export function EntityDetail() {
  const { entityId } = useParams();
  const nav = useNavigate();
  const { data: e } = useQuery({ queryKey: ["entity", entityId], queryFn: () => entitySvc.getEntity(entityId) });
  if (!e) return <LoadingState rows={4} />;
  return (
    <div>
      <button onClick={() => nav(-1)} className="mb-3 text-sm font-semibold text-clay-muted">← Back</button>
      <PageHeader title={e.name} subtitle={`${e.type} · ${e.city}`} icon={Users} actions={<StatusPill status={e.risk} />} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card tint={e.score >= 80 ? "mint" : e.score >= 55 ? "amber" : "rose"} className="flex flex-col items-center justify-center">
          <div className="text-xs font-semibold uppercase tracking-wide text-clay-muted">Compliance score</div>
          <div className="my-2 text-6xl font-extrabold text-clay-ink tnum">{e.score}</div>
          <div className="text-sm text-clay-muted">out of 100</div>
        </Card>
        <Card><SectionTitle>Signals</SectionTitle><div className="space-y-2 text-sm"><Row k="Alerts triggered" v={e.alertsOn} /><Row k="Return rate" v={e.returnRate} /><Row k="Dispute rate" v={`${e.disputeRate}%`} /><Row k="Batches" v={e.batchCount} /><Row k="License" v={e.licenseNo} /></div></Card>
        <Card><SectionTitle>Alerts on their watch</SectionTitle>
          {e.alerts.length === 0 ? <p className="py-6 text-center text-sm text-clay-muted">Clean record.</p> : (
            <div className="space-y-2">{e.alerts.map((a) => <button key={a.id} onClick={() => nav(`/regulator/alerts/${a.id}`)} className="block w-full rounded-2xl bg-clay-surface p-3 text-left text-sm hover:bg-clay-line"><div className="font-medium text-clay-ink">{a.type.replace("_", " ")}</div><div className="text-xs text-clay-muted">{timeAgo(a.ts)}</div></button>)}</div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ============================ FLEET MAP ======================================
export function FleetMap() {
  const routes = useLive((s) => s.routes.filter((r) => r.running));
  const distributors = useLive((s) => s.distributors);
  const [f, setF] = useState("");
  const shown = routes.filter((r) => !f || r.distributorId === f);
  return (
    <div>
      <PageHeader title="Regional fleet map" subtitle="Every pickup vehicle across all distributors" icon={MapIcon} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <Card className="space-y-3"><SectionTitle>Filters</SectionTitle>
          <Select value={f} onChange={(e) => setF(e.target.value)} data-testid="reg-fleet-filter"><option value="">All distributors</option>{distributors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select>
          <div className="space-y-2 pt-1">{shown.map((r) => <div key={r.id} className="rounded-2xl bg-clay-surface p-3 text-sm"><div className="font-semibold text-clay-ink">{r.vehicleReg}</div><div className="text-xs text-clay-muted">{r.agentName} · {r.stops.length} stops</div></div>)}{shown.length === 0 && <p className="text-sm text-clay-muted">No active vehicles.</p>}</div>
        </Card>
        <Card className="p-0 lg:col-span-3"><LiveMap height={480} vehicles={shown.map((r) => ({ pos: r.pos, reg: r.vehicleReg, agent: r.agentName, eta: r.etaMin }))} stops={shown.flatMap((r) => r.stops)} /></Card>
      </div>
    </div>
  );
}

// ============================ ANALYTICS ======================================
export function Analytics() {
  const { data, isLoading } = useQuery({ queryKey: ["reg-analytics"], queryFn: () => analytics.regulatorAnalytics() });
  if (isLoading || !data) return <LoadingState rows={6} />;
  return (
    <div>
      <PageHeader title="National analytics" subtitle="Compliance, geography & fraud networks" icon={TrendingUp} />
      <div className="mb-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label="National compliance" value={`${data.kpis.nationalCompliance}%`} tint="mint" />
        <KpiCard label="Investigations" value={data.kpis.investigations} tint="amber" />
        <KpiCard label="Resolved (mo)" value={data.kpis.resolved} tint="accent" />
        <KpiCard label="Flagged value" value={inr(data.kpis.flaggedValue)} tint="rose" />
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <ChartCard title="National trend · returns / destroyed / alerts"><MultiLine data={data.national} xKey="month" lines={[{ key: "returns", name: "Returns", color: "#5b6cff" }, { key: "destroyed", name: "Destroyed", color: "#3fbf9a" }, { key: "alerts", name: "Alerts", color: "#e0655b" }]} /></ChartCard>
        <ChartCard title="Returns by drug category"><StackedBars data={data.byCategory} xKey="month" keys={["oncology", "antibiotics", "cardiovascular", "other"]} /></ChartCard>
        <Card>
          <SectionTitle>Compliance by district · choropleth</SectionTitle>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {data.districts.map((d) => (
              <div key={d.district} className="rounded-2xl p-3 text-center" style={{ background: d.compliance >= 85 ? "#e2f6ef" : d.compliance >= 78 ? "#fbf1dc" : "#fbe6e3" }}>
                <div className="text-2xl font-extrabold text-clay-ink tnum">{d.compliance}%</div><div className="text-xs text-clay-muted">{d.district}</div>
              </div>
            ))}
          </div>
        </Card>
        <ChartCard title="Average time to close alerts (weekly)"><RoundedBars data={data.timeToClose} xKey="week" yKey="days" color="#a78bfa" /></ChartCard>
      </div>
      <Card className="mt-4"><SectionTitle>Fraud network · entities linked by co-occurring alerts</SectionTitle>
        {data.network.nodes.length === 0 ? <EmptyState title="No fraud clusters detected" icon={ShieldCheck} /> : <NetworkGraph nodes={data.network.nodes} links={data.network.links} />}
      </Card>
    </div>
  );
}

// ============================ REPORTS ========================================
export function Reports() {
  const { data: reports } = useQuery({ queryKey: ["reports"], queryFn: () => alertSvc.listReports() });
  const [region, setRegion] = useState("Tamil Nadu");
  const [category, setCategory] = useState("all");
  const mut = useAppMutation(() => alertSvc.generateReport({ region, category }), { onSuccess: () => toast.success("CDSCO report generated") });
  return (
    <div>
      <PageHeader title="Compliance reports" subtitle="One-click CDSCO-format exports" icon={FileText} />
      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[160px] flex-1"><Label>Region</Label><Select value={region} onChange={(e) => setRegion(e.target.value)} data-testid="report-region"><option>Tamil Nadu</option><option>Chennai</option><option>Coimbatore</option><option>Madurai</option></Select></div>
          <div className="min-w-[160px] flex-1"><Label>Drug category</Label><Select value={category} onChange={(e) => setCategory(e.target.value)} data-testid="report-category"><option value="all">All</option><option value="oncology">Oncology</option><option value="antibiotics">Antibiotics</option><option value="cardiovascular">Cardiovascular</option></Select></div>
          <Button disabled={mut.isPending} onClick={() => mut.mutate()} data-testid="generate-report"><FileText className="h-4 w-4" /> Generate</Button>
        </div>
      </Card>
      <SectionTitle>Generated reports</SectionTitle>
      <Card className="p-0">
        {(reports || []).map((r) => (
          <div key={r.id} className="flex items-center gap-3 border-b border-clay-line/60 px-5 py-3.5" data-testid={`report-${r.id}`}>
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-rose2-soft"><FileText className="h-5 w-5 text-rose2" /></span>
            <div className="flex-1"><div className="text-sm font-semibold text-clay-ink">{r.title}</div><div className="text-xs text-clay-muted">{r.region} · {r.category} · {formatDate(r.createdAt)} · {r.size}</div></div>
            <Button size="sm" variant="outline" onClick={() => toast.success("Downloading PDF…")}><Download className="h-4 w-4" /> Download</Button>
          </div>
        ))}
      </Card>
    </div>
  );
}

export function Profile() {
  return (
    <div className="max-w-2xl">
      <PageHeader title="Officer profile" subtitle="CDSCO — Tamil Nadu Drug Control" icon={Landmark} />
      <Card className="space-y-3"><Row k="Officer" v="R. Menon" /><Row k="Designation" v="Assistant Drug Controller" /><Row k="Jurisdiction" v="Tamil Nadu" /><Row k="ID" v="CDSCO-TN-4471" /></Card>
    </div>
  );
}
