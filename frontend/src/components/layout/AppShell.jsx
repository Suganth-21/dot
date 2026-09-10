import React, { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, LogOut, RotateCcw, ChevronDown, User } from "lucide-react";
import { Logo } from "./Logo";
import NotificationBell from "./NotificationBell";
import CommandPalette from "./CommandPalette";
import { useAuth, ROLE_COLORS } from "../../store/authStore";
import { resetDemo } from "../../services/db";
import { cn } from "../../lib/utils";
import { toast } from "sonner";

export default function AppShell({ navItems, role, roleHome, roleLabel, institutional }) {
  const themeColor = ROLE_COLORS[role];
  const [mobileNav, setMobileNav] = useState(false);
  const [menu, setMenu] = useState(false);
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const doLogout = () => { logout(); nav("/login"); };
  const doReset = () => { resetDemo(); toast.success("Demo data reset to seed"); setMenu(false); };

  const NavItem = ({ to, label, icon: Icon, onClick }) => (
    <NavLink
      to={to}
      onClick={onClick}
      data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
      className={({ isActive }) => cn(
        "flex items-center gap-2 rounded-pill px-3.5 py-2 text-sm font-semibold transition-all",
        isActive ? "bg-accent text-white shadow-clay" : "text-clay-muted hover:bg-clay-line hover:text-clay-ink"
      )}
    >
      {Icon && <Icon className="h-4 w-4" strokeWidth={2.2} />}
      <span>{label}</span>
    </NavLink>
  );

  return (
    <div className={cn("min-h-screen", institutional ? "bg-[#eef0f3]" : "bg-clay-bg")}>
      <header className="sticky top-0 z-30 border-b border-clay-line/70 bg-clay-bg/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-3 px-4 lg:px-6">
          <button className="lg:hidden" onClick={() => setMobileNav(true)} data-testid="mobile-nav-toggle">
            <Menu className="h-6 w-6 text-clay-ink" />
          </button>
          <div className="flex items-center gap-2.5">
            <Logo size="md" dotColor={themeColor} />
            <span className="hidden text-xs font-semibold text-clay-muted sm:inline">{roleLabel}</span>
          </div>
          <nav className="ml-4 hidden items-center gap-1 lg:flex">
            {navItems.map((n) => <NavItem key={n.to} {...n} />)}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <CommandPalette roleHome={roleHome} />
            <NotificationBell role={role} />
            <div className="relative">
              <button onClick={() => setMenu((m) => !m)} data-testid="profile-menu-trigger" className="flex items-center gap-2 rounded-pill bg-clay-surface py-1.5 pl-1.5 pr-2.5 ring-1 ring-clay-line hover:bg-clay-line transition-colors">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-accent text-xs font-bold text-white">{(user?.name || "U")[0]}</span>
                <ChevronDown className="h-4 w-4 text-clay-muted" />
              </button>
              <AnimatePresence>
                {menu && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setMenu(false)} />
                    <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                      className="absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-clay bg-clay-card shadow-pop ring-1 ring-clay-line">
                      <div className="border-b border-clay-line px-4 py-3">
                        <div className="text-sm font-bold text-clay-ink">{user?.name}</div>
                        <div className="text-xs text-clay-muted">{roleLabel}</div>
                      </div>
                      <button onClick={() => { setMenu(false); nav(roleHome.replace(/dashboard|today/, "profile")); }} className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-clay-ink hover:bg-clay-surface" data-testid="profile-link">
                        <User className="h-4 w-4" /> Profile
                      </button>
                      <button onClick={doReset} className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-clay-ink hover:bg-clay-surface" data-testid="reset-demo-btn">
                        <RotateCcw className="h-4 w-4" /> Reset demo data
                      </button>
                      <button onClick={doLogout} className="flex w-full items-center gap-2.5 border-t border-clay-line px-4 py-2.5 text-sm text-rose2 hover:bg-rose2-soft" data-testid="logout-btn">
                        <LogOut className="h-4 w-4" /> Log out
                      </button>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile nav drawer */}
      <AnimatePresence>
        {mobileNav && (
          <motion.div className="fixed inset-0 z-50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-clay-ink/30 backdrop-blur-sm" onClick={() => setMobileNav(false)} />
            <motion.div initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} transition={{ type: "spring", stiffness: 320, damping: 30 }}
              className="absolute inset-y-0 left-0 w-72 bg-clay-card p-4 shadow-pop">
              <div className="mb-6 flex items-center justify-between">
                <Logo size="md" dotColor={themeColor} />
                <button onClick={() => setMobileNav(false)}><X className="h-6 w-6 text-clay-ink" /></button>
              </div>
              <div className="space-y-1">
                {navItems.map((n) => <NavItem key={n.to} {...n} onClick={() => setMobileNav(false)} />)}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <main className="mx-auto max-w-[1400px] px-4 py-6 lg:px-6 lg:py-8">
        <Outlet />
      </main>
    </div>
  );
}
