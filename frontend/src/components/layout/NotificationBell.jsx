import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bell, CheckCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useLive } from "../../hooks/useDb";
import { markAllRead, markRead } from "../../services/notificationService";
import { timeAgo, cn } from "../../lib/utils";

// Unread-dot color by severity — a re-entry alert (danger) should read
// differently at a glance from a routine info notification, not just by
// its text.
const KIND_DOT = {
  info: "bg-accent",
  warning: "bg-amber2",
  danger: "bg-rose2",
  success: "bg-mint",
};

export default function NotificationBell({ role }) {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const items = useLive((s) => s.notifications[role] || []);
  const unread = items.filter((n) => !n.read).length;

  return (
    <div className="relative">
      <button
        data-testid="notification-bell"
        onClick={() => { setOpen((o) => !o); if (!open) markAllRead(role); }}
        className="relative inline-flex h-10 w-10 items-center justify-center rounded-full bg-clay-surface ring-1 ring-clay-line hover:bg-clay-line transition-colors"
      >
        <Bell className="h-[18px] w-[18px] text-clay-ink" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-rose2 px-1 text-[10px] font-bold text-white" data-testid="notification-count">{unread}</span>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <>
            <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
            <motion.div
              initial={{ opacity: 0, y: -8, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.98 }}
              className="absolute right-0 z-50 mt-2 w-80 overflow-hidden rounded-clay bg-clay-card shadow-pop ring-1 ring-clay-line"
              data-testid="notification-panel"
            >
              <div className="flex items-center justify-between border-b border-clay-line px-4 py-3">
                <span className="text-sm font-bold text-clay-ink">Notifications</span>
                <button onClick={() => markAllRead(role)} className="flex items-center gap-1 text-xs text-clay-muted hover:text-clay-ink">
                  <CheckCheck className="h-3.5 w-3.5" /> Mark all read
                </button>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {items.length === 0 && <div className="px-4 py-10 text-center text-sm text-clay-muted">You're all caught up.</div>}
                {items.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => { markRead(role, n.id); if (n.link) { nav(n.link); setOpen(false); } }}
                    className={cn("flex w-full gap-3 border-b border-clay-line/60 px-4 py-3 text-left hover:bg-clay-surface transition-colors", !n.read && "bg-accent-soft/30")}
                  >
                    <span className={cn("mt-0.5 h-2 w-2 shrink-0 rounded-full", n.read ? "bg-transparent" : (KIND_DOT[n.kind] || "bg-accent"))} />
                    <span className="flex-1">
                      <span className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold text-clay-ink">{n.title}</span>
                        <span className="shrink-0 text-[10px] text-clay-muted">{timeAgo(n.ts)}</span>
                      </span>
                      <span className="mt-0.5 block text-xs text-clay-muted">{n.body}</span>
                    </span>
                  </button>
                ))}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
