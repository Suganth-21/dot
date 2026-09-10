import React from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, ShieldCheck, Store, Truck, Bike, Factory, Landmark } from "lucide-react";
import { Logo } from "../components/layout/Logo";
import { Card, Button, Input, Label } from "../components/ui";
import { useAuth, DEMO_ACCOUNTS } from "../store/authStore";

const ICONS = { RETAILER: Store, DISTRIBUTOR: Truck, PICKUP_AGENT: Bike, MANUFACTURER: Factory, REGULATOR: Landmark };

export default function Login() {
  const nav = useNavigate();
  const { login } = useAuth();

  const quickLogin = (acc) => { login(acc); nav(acc.home); };

  return (
    <div className="min-h-screen bg-clay-bg">
      <div className="mx-auto grid min-h-screen max-w-6xl grid-cols-1 items-center gap-10 px-6 py-10 lg:grid-cols-2">
        {/* Left — brand */}
        <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5 }}>
          <Logo size="xl" />
          <h1 className="mt-8 text-4xl font-extrabold leading-tight tracking-tight text-clay-ink">
            The closed loop for India's<br />pharmaceutical returns.
          </h1>
          <p className="mt-4 max-w-md text-base text-clay-muted">
            Track every expired medicine from pharmacy shelf to verified destruction — and catch destroyed batches the instant they reappear.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <div className="flex items-center gap-2 rounded-pill bg-mint-soft px-4 py-2 text-sm font-semibold text-[#1f8a6a]">
              <ShieldCheck className="h-4 w-4" /> CDSCO-aligned reverse logistics
            </div>
            <button onClick={() => nav("/verify")} className="flex items-center gap-2 rounded-pill bg-clay-card px-4 py-2 text-sm font-semibold text-clay-ink ring-1 ring-clay-line hover:bg-clay-surface transition-colors" data-testid="patient-shield-link">
              Patient Shield <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </motion.div>

        {/* Right — login */}
        <motion.div initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.5, delay: 0.1 }}>
          <Card className="p-7">
            <h2 className="text-xl font-bold text-clay-ink">Sign in</h2>
            <p className="mt-1 text-sm text-clay-muted">Use a one-click demo account, or enter credentials.</p>

            <div className="mt-5 space-y-3">
              <div>
                <Label>Email</Label>
                <Input placeholder="you@company.in" defaultValue="" data-testid="login-email" />
              </div>
              <div>
                <Label>Password</Label>
                <Input type="password" placeholder="••••••••" data-testid="login-password" />
              </div>
              <Button className="w-full" onClick={() => quickLogin(DEMO_ACCOUNTS[0])} data-testid="login-submit">
                Sign in <ArrowRight className="h-4 w-4" />
              </Button>
            </div>

            <div className="my-5 flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-clay-muted">
              <span className="h-px flex-1 bg-clay-line" /> Demo accounts <span className="h-px flex-1 bg-clay-line" />
            </div>

            <div className="space-y-2">
              {DEMO_ACCOUNTS.map((acc, i) => {
                const Icon = ICONS[acc.role];
                return (
                  <motion.button
                    key={acc.role}
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.05 }}
                    onClick={() => quickLogin(acc)}
                    data-testid={`quick-login-${acc.role.toLowerCase()}`}
                    className="group flex w-full items-center gap-3 rounded-2xl bg-clay-surface p-3 text-left ring-1 ring-clay-line hover:bg-clay-line transition-all"
                  >
                    <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-white shadow-clay ring-1 ring-clay-line">
                      <Icon className="h-5 w-5 text-accent-ink" />
                    </span>
                    <span className="flex-1">
                      <span className="block text-sm font-bold text-clay-ink">{acc.label}</span>
                      <span className="block text-xs text-clay-muted">{acc.name}</span>
                    </span>
                    <ArrowRight className="h-4 w-4 text-clay-muted transition-transform group-hover:translate-x-1" />
                  </motion.button>
                );
              })}
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
