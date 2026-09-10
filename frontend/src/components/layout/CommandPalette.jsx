import React, { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, Package, Store, CornerDownLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { searchAll } from "../../services/batchService";
import { StatusPill } from "../common";

export default function CommandPalette({ roleHome }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const nav = useNavigate();

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    let active = true;
    if (!q.trim()) { setResults([]); return; }
    searchAll(q).then((r) => active && setResults(r));
    return () => { active = false; };
  }, [q]);

  const go = useCallback((r) => {
    setOpen(false); setQ("");
    const root = roleHome.split("/")[1];
    if (r.type === "batch") {
      const map = {
        pharmacy: `/pharmacy/inventory/${r.id}`,
        manufacturer: `/manufacturer/batches/${r.id}`,
        regulator: `/regulator/batches/${r.id}`,
        distributor: `/regulator/batches/${r.id}`,
        agent: `/regulator/batches/${r.id}`,
      };
      nav(map[root] || `/regulator/batches/${r.id}`);
    } else {
      nav("/regulator/entities/" + r.id);
    }
  }, [nav, roleHome]);

  return (
    <>
      <button
        data-testid="command-palette-trigger"
        onClick={() => setOpen(true)}
        className="hidden items-center gap-2 rounded-pill bg-clay-surface px-3.5 py-2 text-sm text-clay-muted ring-1 ring-clay-line hover:bg-clay-line transition-colors md:inline-flex"
      >
        <Search className="h-4 w-4" />
        <span>Search…</span>
        <kbd className="ml-2 rounded-md bg-white px-1.5 py-0.5 text-[10px] font-semibold text-clay-muted ring-1 ring-clay-line">⌘K</kbd>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[12vh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-clay-ink/30 backdrop-blur-sm" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ scale: 0.97, y: -8 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.97, y: -8 }}
              className="relative z-10 w-full max-w-xl overflow-hidden rounded-clay bg-clay-card shadow-pop ring-1 ring-clay-line"
              data-testid="command-palette"
            >
              <div className="flex items-center gap-3 border-b border-clay-line px-4">
                <Search className="h-5 w-5 text-clay-muted" />
                <input
                  autoFocus value={q} onChange={(e) => setQ(e.target.value)}
                  placeholder="Search batch ID, drug or pharmacy…"
                  data-testid="command-palette-input"
                  className="h-14 w-full bg-transparent text-base text-clay-ink outline-none placeholder:text-clay-muted"
                />
              </div>
              <div className="max-h-80 overflow-y-auto p-2">
                {q && results.length === 0 && <div className="px-3 py-8 text-center text-sm text-clay-muted">No matches for "{q}"</div>}
                {!q && <div className="px-3 py-8 text-center text-sm text-clay-muted">Type to search the shared batch ledger.</div>}
                {results.map((r) => (
                  <button key={r.type + r.id} onClick={() => go(r)} className="flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left hover:bg-clay-surface transition-colors" data-testid="command-result">
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-clay-surface ring-1 ring-clay-line">
                      {r.type === "batch" ? <Package className="h-4 w-4 text-accent-ink" /> : <Store className="h-4 w-4 text-mint" />}
                    </span>
                    <span className="flex-1">
                      <span className="block text-sm font-semibold text-clay-ink">{r.title}</span>
                      <span className="block text-xs text-clay-muted">{r.subtitle}</span>
                    </span>
                    {r.status && <StatusPill status={r.status} />}
                    <CornerDownLeft className="h-4 w-4 text-clay-muted" />
                  </button>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
