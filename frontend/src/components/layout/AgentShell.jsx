import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { cn } from "../../lib/utils";
import { Logo } from "./Logo";
import NotificationBell from "./NotificationBell";
import { useAuth } from "../../store/authStore";

export default function AgentShell({ navItems }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col bg-clay-bg">
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-clay-line/70 bg-clay-bg/85 px-4 backdrop-blur-xl">
        <Logo size="sm" />
        <div className="flex items-center gap-2">
          <NotificationBell role="PICKUP_AGENT" />
          <button onClick={() => { logout(); nav("/login"); }} className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent text-xs font-bold text-white" data-testid="agent-avatar">
            {(user?.name || "A")[0]}
          </button>
        </div>
      </header>
      <main className="flex-1 px-4 py-5 pb-24">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 z-20 mx-auto max-w-md border-t border-clay-line bg-clay-card/95 backdrop-blur-xl">
        <div className="grid grid-cols-3">
          {navItems.map((n) => (
            <NavLink key={n.to} to={n.to} data-testid={`agent-nav-${n.label.toLowerCase()}`}
              className={({ isActive }) => cn("flex flex-col items-center gap-1 py-3 text-[11px] font-semibold transition-colors",
                isActive ? "text-accent-ink" : "text-clay-muted")}>
              {({ isActive }) => (
                <>
                  <span className={cn("inline-flex h-9 w-9 items-center justify-center rounded-full transition-colors", isActive ? "bg-accent-soft" : "")}>
                    <n.icon className="h-5 w-5" strokeWidth={2.2} />
                  </span>
                  {n.label}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
