import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertTriangle, Inbox, RefreshCw, X, Link2, MapPin, Camera, ShieldCheck } from "lucide-react";
import { cn, formatDateTime } from "../../lib/utils";
import { Badge, Button, Card, Skeleton } from "../ui";

// ---- Status → badge mapping --------------------------------------------------
const STATUS_MAP = {
  ACTIVE: { tone: "mint", label: "Active" },
  EXPIRING_SOON: { tone: "amber", label: "Expiring Soon" },
  EXPIRED: { tone: "rose", label: "Expired" },
  IN_RETURN: { tone: "accent", label: "In Return" },
  DESTROYED: { tone: "gray", label: "Destroyed" },
  REQUESTED: { tone: "sky", label: "Requested" },
  SCHEDULED: { tone: "lilac", label: "Scheduled" },
  ASSIGNED: { tone: "lilac", label: "Assigned" },
  EN_ROUTE: { tone: "accent", label: "En Route" },
  ARRIVED: { tone: "amber", label: "Arrived" },
  PICKED_UP: { tone: "sky", label: "Picked Up" },
  CONFIRMED: { tone: "mint", label: "Confirmed" },
  DISPUTED: { tone: "rose", label: "Disputed" },
  FORWARDED: { tone: "mint", label: "Forwarded" },
  NEW: { tone: "sky", label: "New" },
  OPEN: { tone: "rose", label: "Open" },
  INVESTIGATING: { tone: "amber", label: "Investigating" },
  ESCALATED: { tone: "rose", label: "Escalated" },
  CLOSED: { tone: "gray", label: "Closed" },
  idle: { tone: "gray", label: "Idle" },
  active: { tone: "mint", label: "Active" },
  offline: { tone: "rose", label: "Offline" },
  LOW: { tone: "mint", label: "Low Risk" },
  MEDIUM: { tone: "amber", label: "Medium Risk" },
  HIGH: { tone: "rose", label: "High Risk" },
  critical: { tone: "rose", label: "Critical" },
  high: { tone: "amber", label: "High" },
  medium: { tone: "lilac", label: "Medium" },
  low: { tone: "gray", label: "Low" },
};

export function StatusPill({ status, className }) {
  const m = STATUS_MAP[status] || { tone: "gray", label: status };
  return <Badge tone={m.tone} className={className}>{m.label}</Badge>;
}

// ---- KPI card ----------------------------------------------------------------
export function KpiCard({ label, value, icon, tint, hint, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
    >
      <Card tint={tint} className="flex flex-col gap-3">
        <div className="flex items-start justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-clay-muted">{label}</span>
          {icon && (
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/80 shadow-clay">
              {React.createElement(icon, { className: "h-4 w-4 text-clay-ink", strokeWidth: 2 })}
            </span>
          )}
        </div>
        <div className="text-3xl font-extrabold tracking-tight text-clay-ink tnum">{value}</div>
        {hint && <div className="text-xs text-clay-muted">{hint}</div>}
      </Card>
    </motion.div>
  );
}

// ---- Page header -------------------------------------------------------------
export function PageHeader({ title, subtitle, actions, icon }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="flex items-center gap-3">
          {icon && React.createElement(icon, { className: "h-6 w-6 text-accent-ink", strokeWidth: 2 })}
          <h1 className="text-2xl font-extrabold tracking-tight text-clay-ink">{title}</h1>
        </div>
        {subtitle && <p className="mt-1 text-sm text-clay-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionTitle({ children, right }) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-sm font-bold uppercase tracking-wide text-clay-muted">{children}</h3>
      {right}
    </div>
  );
}

// ---- Empty / Loading / Error states -----------------------------------------
export function EmptyState({ title, subtitle, icon = Inbox, action }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-clay bg-clay-surface px-6 py-16 text-center ring-1 ring-clay-line/60">
      <span className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-clay">
        {React.createElement(icon, { className: "h-6 w-6 text-clay-muted" })}
      </span>
      <p className="text-base font-semibold text-clay-ink">{title}</p>
      {subtitle && <p className="mt-1 max-w-sm text-sm text-clay-muted">{subtitle}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function LoadingState({ rows = 4, className }) {
  return (
    <div className={cn("space-y-3", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="rounded-clay bg-clay-card p-4 ring-1 ring-clay-line/60">
          <div className="flex items-center gap-4">
            <Skeleton className="h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3.5 w-1/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-6 w-20 rounded-pill" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function KpiSkeleton({ n = 5 }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="rounded-clay bg-clay-card p-5 ring-1 ring-clay-line/60">
          <Skeleton className="mb-4 h-3 w-2/3" />
          <Skeleton className="h-8 w-1/2" />
        </div>
      ))}
    </div>
  );
}

export function ErrorState({ message = "Something went wrong.", onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-clay bg-rose2-soft px-6 py-14 text-center ring-1 ring-rose2/20">
      <span className="mb-4 inline-flex h-14 w-14 items-center justify-center rounded-full bg-white shadow-clay">
        <AlertTriangle className="h-6 w-6 text-rose2" />
      </span>
      <p className="text-base font-semibold text-clay-ink">{message}</p>
      {onRetry && (
        <Button variant="outline" className="mt-5" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" /> Try again
        </Button>
      )}
    </div>
  );
}

// ---- Modal -------------------------------------------------------------------
export function Modal({ open, onClose, title, children, size = "md" }) {
  const w = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[size];
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-clay-ink/30 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            className={cn("relative z-10 w-full rounded-clay bg-clay-card p-6 shadow-pop", w)}
            initial={{ scale: 0.96, y: 12 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.96, y: 12 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-clay-ink">{title}</h3>
              <button onClick={onClose} className="rounded-full p-1.5 text-clay-muted hover:bg-clay-line" data-testid="modal-close">
                <X className="h-5 w-5" />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ---- Stepper -----------------------------------------------------------------
export function Stepper({ steps, current }) {
  return (
    <div className="flex items-center">
      {steps.map((s, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <React.Fragment key={s}>
            <div className="flex flex-col items-center gap-1.5">
              <div className={cn(
                "flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-all",
                done ? "bg-mint text-white" : active ? "bg-accent text-white ring-4 ring-accent-soft" : "bg-clay-line text-clay-muted"
              )}>{i + 1}</div>
              <span className={cn("text-[11px] font-medium", active ? "text-clay-ink" : "text-clay-muted")}>{s}</span>
            </div>
            {i < steps.length - 1 && <div className={cn("mx-1 h-0.5 flex-1 rounded-full", i < current ? "bg-mint" : "bg-clay-line")} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ---- Hash-chain timeline (the differentiator) --------------------------------
const EVENT_META = {
  REGISTERED: { tone: "mint", label: "Registered", icon: ShieldCheck },
  SALE: { tone: "sky", label: "Sale", icon: MapPin },
  RETURN_INITIATED: { tone: "amber", label: "Return Initiated", icon: RefreshCw },
  PICKUP_ASSIGNED: { tone: "lilac", label: "Pickup Assigned", icon: MapPin },
  AGENT_ARRIVED: { tone: "sky", label: "Agent Arrived", icon: MapPin },
  PICKED_UP: { tone: "sky", label: "Picked Up", icon: Camera },
  DISTRIBUTOR_CONFIRMED: { tone: "mint", label: "Distributor Confirmed", icon: ShieldCheck },
  DISPUTE_RESOLVED: { tone: "amber", label: "Dispute Resolved", icon: ShieldCheck },
  FORWARDED: { tone: "accent", label: "Forwarded to Manufacturer", icon: MapPin },
  FACILITY_SCHEDULED: { tone: "lilac", label: "Facility Scheduled", icon: MapPin },
  DESTROYED: { tone: "rose", label: "Destroyed", icon: AlertTriangle },
  REENTRY_BLOCKED: { tone: "rose", label: "Re-entry Blocked", icon: AlertTriangle },
};

export function HashChain({ events = [], showGps = false }) {
  return (
    <ol className="relative space-y-1">
      {events.map((e, i) => {
        const meta = EVENT_META[e.type] || { tone: "gray", label: e.type, icon: MapPin };
        const Icon = meta.icon;
        const iconColor = { mint: "text-mint", amber: "text-amber2", rose: "text-rose2", accent: "text-accent-ink", lilac: "text-lilac", sky: "text-sky2", gray: "text-clay-muted" }[meta.tone];
        return (
          <li key={e.id} className="group relative pl-12">
            {i < events.length - 1 && <span className="absolute left-[19px] top-9 h-full w-0.5 bg-clay-line" />}
            <span className="absolute left-0 top-1 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-clay ring-1 ring-clay-line">
              <Icon className={cn("h-[18px] w-[18px]", iconColor)} />
            </span>
            <div className="rounded-2xl bg-clay-surface p-3.5 ring-1 ring-clay-line/60">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-clay-ink">{meta.label}</span>
                  <Badge tone={meta.tone}>{e.actor?.role || "SYSTEM"}</Badge>
                </div>
                <span className="text-xs text-clay-muted">{formatDateTime(e.ts)}</span>
              </div>
              <div className="mt-1 text-xs text-clay-muted">
                by <span className="font-medium text-clay-ink">{e.actor?.name}</span>
                {e.meta?.units != null && ` · ${e.meta.units} units`}
                {e.meta?.quantity != null && ` · ${e.meta.quantity} units`}
                {e.meta?.received != null && ` · received ${e.meta.received}`}
                {e.meta?.counted != null && ` · counted ${e.meta.counted}`}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-clay-muted">
                <span className="group/hash relative inline-flex cursor-help items-center gap-1 font-mono">
                  <Link2 className="h-3.5 w-3.5 text-accent-ink" />
                  <span className="text-accent-ink">hash link</span>
                  <span className="pointer-events-none absolute bottom-full left-0 mb-1.5 hidden whitespace-nowrap rounded-lg bg-clay-ink px-2.5 py-1.5 font-mono text-[10px] text-white shadow-pop group-hover/hash:block">
                    hash: {e.hash}<br />prev: {e.prevHash}
                  </span>
                </span>
                <span className="font-mono">📷 {e.photoHash?.slice(0, 14)}…</span>
                {showGps && e.gps && (
                  <span className="font-mono">◎ {e.gps.lat.toFixed(3)}, {e.gps.lng.toFixed(3)}</span>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
