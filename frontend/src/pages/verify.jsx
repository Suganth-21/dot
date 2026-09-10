import React, { useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertOctagon, HelpCircle, ScanLine, ArrowRight, ShieldQuestion, Loader2, MapPin } from "lucide-react";
import { toast } from "sonner";
import { Logo } from "../components/layout/Logo";
import { Button, Card, Textarea, Label, Input } from "../components/ui";
import QrScanner from "../components/scanner/QrScanner";
import { verifyBatch, reportSuspicious } from "../services/verifyService";
import { formatDate } from "../lib/utils";

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-clay-surface to-clay-bg">
      <div className="mx-auto flex min-h-screen max-w-md flex-col px-6 py-8">{children}</div>
    </div>
  );
}

export function Landing() {
  const nav = useNavigate();
  return (
    <Shell>
      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.5 }}>
          <Logo size="xl" />
        </motion.div>
        <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="mt-6 max-w-xs text-lg font-medium text-clay-ink">
          Scan any medicine's QR code to verify it's genuine.
        </motion.p>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }} className="mt-10 w-full">
          <Button size="lg" className="h-16 w-full text-lg" onClick={() => nav("/verify/scan")} data-testid="scan-now-btn">
            <ScanLine className="h-6 w-6" /> Scan Now
          </Button>
        </motion.div>
      </div>
      <footer className="pt-6 text-center text-xs text-clay-muted">
        A public service. No login required. No data stored.
      </footer>
    </Shell>
  );
}

export function Scan() {
  const nav = useNavigate();
  return (
    <Shell>
      <div className="mb-6 flex items-center justify-between">
        <Logo size="sm" />
        <Link to="/verify" className="text-sm font-semibold text-clay-muted">Cancel</Link>
      </div>
      <p className="mb-4 text-center text-sm font-medium text-clay-ink">Point at the QR code on your medicine box</p>
      <QrScanner
        height={340}
        onScan={(code) => nav(`/verify/result/${encodeURIComponent(code)}`)}
        demoCodes={[
          { code: "BATCH-DOX-2026-B04", label: "Destroyed batch" },
          { code: "BATCH-DOX-2026-A17", label: "Genuine batch" },
          { code: "BATCH-FAKE-9999-Z01", label: "Unknown / fake" },
        ]}
      />
      <p className="mt-6 text-center text-xs text-clay-muted">Your camera never leaves your device.</p>
    </Shell>
  );
}

export function Result() {
  const { batchId } = useParams();
  const nav = useNavigate();
  const { data, isLoading } = useQuery({ queryKey: ["verify", batchId], queryFn: () => verifyBatch(batchId) });

  if (isLoading || !data) {
    return <Shell><div className="flex flex-1 flex-col items-center justify-center gap-3 text-clay-muted"><Loader2 className="h-8 w-8 animate-spin" /><p className="text-sm">Verifying with the trust registry…</p></div></Shell>;
  }

  if (data.verdict === "GENUINE") {
    return (
      <Shell>
        <ResultBody
          testid="result-genuine" tone="mint" icon={CheckCircle2}
          title="This medicine is genuine and safe to use."
          batch={data.batch}
        >
          <Button variant="ghost" size="sm" className="mt-2 text-clay-muted" onClick={() => nav("/verify/report")}>Something wrong? Report it</Button>
        </ResultBody>
      </Shell>
    );
  }

  if (data.verdict === "DESTROYED") {
    return (
      <Shell>
        <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center rounded-clay bg-rose2-soft p-6 text-center ring-1 ring-rose2/20" data-testid="result-destroyed">
          <span className="inline-flex h-24 w-24 items-center justify-center rounded-full bg-rose2 text-white shadow-pop">
            <AlertOctagon className="h-12 w-12" />
          </span>
          <h1 className="mt-5 text-2xl font-extrabold text-[#a8443b]">DO NOT USE THIS MEDICINE</h1>
          <p className="mt-3 text-sm text-clay-ink">
            This batch was returned for destruction on <b>{formatDate(data.batch.destroyedDate)}</b>. If it's being sold to you, it may have been illegally repackaged.
          </p>
          <div className="mt-4 w-full rounded-2xl bg-white/70 p-3 text-left text-xs text-clay-muted">
            <div className="font-semibold text-clay-ink">{data.batch.drugName}</div>
            <div>Batch {data.batch.id} · {data.batch.manufacturerName}</div>
            <div className="mt-1">Certificate: {data.batch.certId}</div>
          </div>
          <div className="mt-5 grid w-full grid-cols-1 gap-2">
            <Button variant="danger" onClick={() => nav("/verify/report")} data-testid="report-pharmacy-btn">Report this pharmacy</Button>
            <Button variant="outline" onClick={() => toast.info("Do not consume. Keep the medicine, note the seller, and file a report with the Drug Controller.")}>What do I do now?</Button>
          </div>
        </motion.div>
        <div className="mt-4 text-center text-xs text-clay-muted">Verified via DOT — India's pharmaceutical trust registry</div>
      </Shell>
    );
  }

  // NOT_FOUND
  return (
    <Shell>
      <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
        className="flex flex-col items-center rounded-clay bg-amber2-soft p-6 text-center ring-1 ring-amber2/20" data-testid="result-notfound">
        <span className="inline-flex h-24 w-24 items-center justify-center rounded-full bg-amber2 text-white shadow-pop">
          <HelpCircle className="h-12 w-12" />
        </span>
        <h1 className="mt-5 text-2xl font-extrabold text-[#96702a]">Could not be verified</h1>
        <p className="mt-3 text-sm text-clay-ink">This batch could not be verified. It may be counterfeit.</p>
        <p className="mt-1 text-xs text-clay-muted">Scanned: {batchId}</p>
        <Button variant="dark" className="mt-5 w-full" onClick={() => nav("/verify/report")} data-testid="report-controller-btn">Report this to the Drug Controller</Button>
      </motion.div>
      <div className="mt-4 text-center text-xs text-clay-muted">Verified via DOT — India's pharmaceutical trust registry</div>
    </Shell>
  );
}

function ResultBody({ tone, icon: Icon, title, batch, children, testid }) {
  return (
    <>
      <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
        className="flex flex-1 flex-col items-center justify-center text-center" data-testid={testid}>
        <span className="inline-flex h-24 w-24 items-center justify-center rounded-full bg-mint text-white shadow-pop">
          <Icon className="h-12 w-12" />
        </span>
        <h1 className="mt-6 text-2xl font-extrabold text-[#1f8a6a]">{title}</h1>
        <Card className="mt-6 w-full text-left">
          <Row k="Drug" v={batch.drugName} />
          <Row k="Manufacturer" v={batch.manufacturerName} />
          <Row k="Batch" v={batch.id} />
          <Row k="Expiry" v={formatDate(batch.expiryDate)} />
        </Card>
        <p className="mt-4 text-xs text-clay-muted">Verified via DOT — India's pharmaceutical trust registry</p>
        {children}
      </motion.div>
    </>
  );
}
function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between border-b border-clay-line py-2 last:border-0">
      <span className="text-xs uppercase tracking-wide text-clay-muted">{k}</span>
      <span className="text-sm font-semibold text-clay-ink">{v}</span>
    </div>
  );
}

export function Report() {
  const nav = useNavigate();
  const [notes, setNotes] = useState("");
  const [pharmacyName, setPharmacyName] = useState("");
  const [loc, setLoc] = useState(null);

  const getLocation = () => {
    if (!navigator.geolocation) { toast.error("Geolocation not available"); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => { setLoc({ lat: p.coords.latitude, lng: p.coords.longitude, district: "Detected" }); toast.success("Location captured"); },
      () => { setLoc({ lat: 13.0827, lng: 80.2707, district: "Chennai" }); toast.info("Using approximate location"); }
    );
  };

  const submit = async () => {
    await reportSuspicious({ batchId: null, location: loc, notes, pharmacyName });
    toast.success("Report submitted to the Drug Controller. Thank you for keeping medicines safe.");
    nav("/verify");
  };

  return (
    <Shell>
      <div className="mb-6 flex items-center gap-3">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-rose2-soft"><ShieldQuestion className="h-6 w-6 text-rose2" /></span>
        <div>
          <h1 className="text-xl font-extrabold text-clay-ink">Report a suspicious medicine</h1>
          <p className="text-xs text-clay-muted">Your report goes straight to the Drug Controller.</p>
        </div>
      </div>
      <div className="space-y-4">
        <div>
          <Label>Pharmacy / seller name (optional)</Label>
          <Input value={pharmacyName} onChange={(e) => setPharmacyName(e.target.value)} placeholder="e.g. XYZ Medicals, Anna Nagar" data-testid="report-pharmacy-name" />
        </div>
        <div>
          <Label>What happened? (optional)</Label>
          <Textarea rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Describe what looked wrong…" data-testid="report-notes" />
        </div>
        <Button variant="outline" className="w-full" onClick={getLocation} data-testid="report-location">
          <MapPin className="h-4 w-4" /> {loc ? "Location captured ✓" : "Attach my location"}
        </Button>
        <Button className="w-full" onClick={submit} data-testid="report-submit">Submit report <ArrowRight className="h-4 w-4" /></Button>
        <Link to="/verify" className="block text-center text-sm text-clay-muted">Back to start</Link>
      </div>
    </Shell>
  );
}
