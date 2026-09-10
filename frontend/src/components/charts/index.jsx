import React from "react";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, Area, AreaChart, FunnelChart, Funnel, LabelList,
} from "recharts";
import { Card } from "../ui";
import { SectionTitle } from "../common";
import { cn } from "../../lib/utils";

export const PALETTE = ["#5b6cff", "#3fbf9a", "#e0a53d", "#e0655b", "#a78bfa", "#5aa9e6", "#f0a8c0", "#84cc8f"];

const axis = { tick: { fill: "#8a8681", fontSize: 11 }, axisLine: false, tickLine: false };
const grid = { stroke: "#eceae5", vertical: false };

function TT({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-2xl bg-clay-card p-3 shadow-pop ring-1 ring-clay-line">
      {label != null && <div className="mb-1 text-xs font-bold text-clay-ink">{label}</div>}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2 text-xs text-clay-muted">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: p.color || p.fill }} />
          <span className="capitalize">{p.name}:</span>
          <span className="font-semibold text-clay-ink tnum">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

export function ChartCard({ title, right, children, className, height = 260 }) {
  return (
    <Card className={cn("flex flex-col", className)}>
      {title && <SectionTitle right={right}>{title}</SectionTitle>}
      <div style={{ height }}>{children}</div>
    </Card>
  );
}

export function SmoothLine({ data, xKey, yKey, color = "#5b6cff", height = 260, area = true }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <defs>
          <linearGradient id={`g-${yKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.28} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid {...grid} />
        <XAxis dataKey={xKey} {...axis} />
        <YAxis {...axis} width={38} />
        <Tooltip content={<TT />} />
        <Area type="monotone" dataKey={yKey} stroke={color} strokeWidth={2.5} fill={area ? `url(#g-${yKey})` : "none"} isAnimationActive={false} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function MultiLine({ data, xKey, lines, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid {...grid} />
        <XAxis dataKey={xKey} {...axis} />
        <YAxis {...axis} width={38} />
        <Tooltip content={<TT />} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        {lines.map((l, i) => (
          <Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={l.color || PALETTE[i]} strokeWidth={2.5} dot={false} isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function RoundedBars({ data, xKey, yKey, color = "#5b6cff", height = 260, horizontal = false }) {
  if (horizontal) {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid stroke="#eceae5" horizontal={false} />
          <XAxis type="number" {...axis} />
          <YAxis type="category" dataKey={xKey} {...axis} width={120} />
          <Tooltip content={<TT />} cursor={{ fill: "#f4f2ee" }} />
          <Bar dataKey={yKey} fill={color} radius={[0, 999, 999, 0]} barSize={14} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid {...grid} />
        <XAxis dataKey={xKey} {...axis} />
        <YAxis {...axis} width={38} />
        <Tooltip content={<TT />} cursor={{ fill: "#f4f2ee" }} />
        <Bar dataKey={yKey} fill={color} radius={[999, 999, 0, 0]} barSize={22} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function StackedBars({ data, xKey, keys, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid {...grid} />
        <XAxis dataKey={xKey} {...axis} />
        <YAxis {...axis} width={38} />
        <Tooltip content={<TT />} cursor={{ fill: "#f4f2ee" }} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        {keys.map((k, i) => (
          <Bar key={k} dataKey={k} stackId="a" fill={PALETTE[i]} radius={i === keys.length - 1 ? [8, 8, 0, 0] : 0} barSize={22} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({ data, height = 260, centerLabel }) {
  const total = data.reduce((a, b) => a + b.value, 0);
  return (
    <div className="relative" style={{ height }}>
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="90%" paddingAngle={3} stroke="none" isAnimationActive={false}>
            {data.map((d, i) => <Cell key={i} fill={d.color || PALETTE[i]} />)}
          </Pie>
          <Tooltip content={<TT />} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center pb-8">
        <span className="text-2xl font-extrabold text-clay-ink tnum">{total}</span>
        <span className="text-[11px] uppercase tracking-wide text-clay-muted">{centerLabel || "Total"}</span>
      </div>
    </div>
  );
}

export function FunnelCard({ data, height = 280 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <FunnelChart>
        <Tooltip content={<TT />} />
        <Funnel dataKey="value" data={data.map((d, i) => ({ ...d, fill: PALETTE[i] }))} isAnimationActive={false}>
          <LabelList position="right" fill="#1c1b19" stroke="none" dataKey="stage" fontSize={12} />
          <LabelList position="left" fill="#8a8681" stroke="none" dataKey="value" fontSize={12} />
        </Funnel>
      </FunnelChart>
    </ResponsiveContainer>
  );
}

// Custom heatmap grid (day x hour)
export function Heatmap({ data, days, hours }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="overflow-x-auto no-scrollbar">
      <div className="inline-grid gap-1" style={{ gridTemplateColumns: `48px repeat(${hours.length}, 20px)` }}>
        <div />
        {hours.map((h) => <div key={h} className="text-center text-[9px] text-clay-muted">{h}</div>)}
        {days.map((d) => (
          <React.Fragment key={d}>
            <div className="flex items-center text-[11px] font-medium text-clay-muted">{d}</div>
            {hours.map((h) => {
              const cell = data.find((x) => x.day === d && x.hour === h);
              const v = cell ? cell.value : 0;
              const op = 0.12 + (v / max) * 0.88;
              return <div key={d + h} title={`${d} ${h}:00 — ${v}`} className="h-5 w-5 rounded-md" style={{ background: `rgba(91,108,255,${op})` }} />;
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

// Simple proportional flow (Sankey-lite): pharmacies -> distributors -> facilities
export function FlowDiagram({ columns }) {
  return (
    <div className="flex items-stretch justify-between gap-6">
      {columns.map((col, ci) => (
        <div key={ci} className="flex-1">
          <div className="mb-3 text-center text-xs font-bold uppercase tracking-wide text-clay-muted">{col.title}</div>
          <div className="space-y-2">
            {col.items.map((it, i) => (
              <div key={i} className="rounded-2xl px-3 py-2.5 text-center text-xs font-semibold text-clay-ink" style={{ background: `${PALETTE[(ci * 3 + i) % PALETTE.length]}22` }}>
                {it.name}
                <div className="text-[10px] font-normal text-clay-muted tnum">{it.value} batches</div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// Force-directed-ish network on a circle layout (SVG)
export function NetworkGraph({ nodes, links, height = 320 }) {
  const cx = 250, cy = height / 2, r = Math.min(cx, cy) - 50;
  const pos = {};
  nodes.forEach((n, i) => {
    const a = (i / Math.max(1, nodes.length)) * Math.PI * 2 - Math.PI / 2;
    pos[n.id] = { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) };
  });
  return (
    <svg viewBox={`0 0 500 ${height}`} className="w-full" style={{ height }}>
      {links.map((l, i) => {
        const a = pos[l.source], b = pos[l.target];
        if (!a || !b) return null;
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#e0655b" strokeWidth={l.value} opacity={0.5} />;
      })}
      {nodes.map((n) => {
        const p = pos[n.id];
        const rad = 10 + (n.weight || 1) * 5;
        return (
          <g key={n.id}>
            <circle cx={p.x} cy={p.y} r={rad} fill="#5b6cff" opacity={0.85} />
            <text x={p.x} y={p.y + rad + 12} textAnchor="middle" fontSize="10" fill="#8a8681">{n.name}</text>
          </g>
        );
      })}
    </svg>
  );
}
