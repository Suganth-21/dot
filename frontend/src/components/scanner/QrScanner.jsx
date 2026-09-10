import React, { useEffect, useRef, useState } from "react";
import { Html5Qrcode, Html5QrcodeScannerState } from "html5-qrcode";
import { Camera, CameraOff, Zap } from "lucide-react";
import { Button } from "../ui";
import { cn } from "../../lib/utils";

export default function QrScanner({ onScan, demoCodes = [], height = 300, className }) {
  const ref = useRef(null);
  const scannerRef = useRef(null);
  const [status, setStatus] = useState("starting"); // starting | scanning | error
  const idRef = useRef("qr-" + Math.random().toString(36).slice(2, 8));

  useEffect(() => {
    let mounted = true;
    const el = document.getElementById(idRef.current);
    if (!el) return;
    const scanner = new Html5Qrcode(idRef.current, { verbose: false });
    scannerRef.current = scanner;
    Html5Qrcode.getCameras()
      .then((cams) => {
        if (!mounted || !cams || cams.length === 0) { setStatus("error"); return; }
        const camId = cams[cams.length - 1].id;
        return scanner.start(
          camId,
          { fps: 10, qrbox: { width: 220, height: 220 } },
          (decoded) => { onScan?.(decoded); },
          () => {}
        ).then(() => {
          if (!mounted) {
            scanner.stop().then(() => { try { scanner.clear(); } catch (e) {} }).catch(() => {});
            return;
          }
          setStatus("scanning");
        });
      })
      .catch(() => mounted && setStatus("error"));

    return () => {
      mounted = false;
      const s = scannerRef.current;
      if (!s) return;
      try {
        const state = s.getState();
        if (state === Html5QrcodeScannerState.SCANNING || state === Html5QrcodeScannerState.PAUSED) {
          s.stop().then(() => { try { s.clear(); } catch (e) {} }).catch(() => {});
        } else {
          try { s.clear(); } catch (e) {}
        }
      } catch (e) {
        // scanner never started — nothing to stop
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="relative overflow-hidden rounded-clay bg-clay-ink ring-1 ring-clay-line" style={{ minHeight: height }}>
        <div id={idRef.current} ref={ref} style={{ width: "100%" }} />
        {status !== "scanning" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-clay-ink text-center text-white/90" style={{ minHeight: height }}>
            {status === "starting" ? (
              <>
                <Camera className="h-10 w-10 animate-pulse" />
                <p className="text-sm">Requesting camera…</p>
              </>
            ) : (
              <>
                <CameraOff className="h-10 w-10 text-white/60" />
                <p className="max-w-xs text-sm text-white/70">Camera unavailable in this environment. Use a demo code below to simulate a scan.</p>
              </>
            )}
          </div>
        )}
        {status === "scanning" && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <div className="h-56 w-56 rounded-3xl border-2 border-accent/80 shadow-[0_0_0_9999px_rgba(28,27,25,0.45)]" />
          </div>
        )}
      </div>
      {demoCodes.length > 0 && (
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-clay-muted">
            <Zap className="h-3.5 w-3.5 text-accent-ink" /> Simulate a scan
          </p>
          <div className="flex flex-wrap gap-2">
            {demoCodes.map((c) => (
              <Button key={c.code} variant="soft" size="sm" onClick={() => onScan?.(c.code)} data-testid={`demo-scan-${c.code}`}>
                {c.label || c.code}
              </Button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
