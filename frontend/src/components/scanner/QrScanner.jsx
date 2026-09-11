import React, { useEffect, useRef, useState } from "react";
import { Html5Qrcode, Html5QrcodeScannerState } from "html5-qrcode";
import { Camera, CameraOff, Zap, RefreshCw } from "lucide-react";
import { Button } from "../ui";
import { cn } from "../../lib/utils";

// Camera failures aren't all the same problem, and "camera unavailable"
// with no way to retry made every real cause (permission blocked, no
// device, Brave/Chrome auto-denying until a site setting is flipped) look
// identical and unrecoverable without a full page reload. Classified below
// so the message tells the user what to actually do, and a real retry
// button re-runs getCameras() on a fresh click (a new user gesture is
// sometimes what a browser needs to re-offer the permission prompt after
// an earlier dismissal).
function classifyCameraError(err) {
  const s = String(err?.name || err?.message || err || "").toLowerCase();
  if (s.includes("notallowed") || s.includes("permission") || s.includes("denied")) return "denied";
  if (s.includes("notfound") || s.includes("no camera") || s.includes("nocamerasfound")) return "notfound";
  if (s.includes("notreadable") || s.includes("trackstart")) return "busy";
  return "error";
}

const STATUS_COPY = {
  denied: "Camera permission is blocked. Click the camera icon in the address bar → Allow, then retry.",
  notfound: "No camera found on this device. Use a demo code below.",
  busy: "Camera is in use by another app or tab. Close it, then retry.",
  error: "Camera unavailable in this browser. Use a demo code below.",
};

export default function QrScanner({ onScan, demoCodes = [], height = 300, className }) {
  const ref = useRef(null);
  const scannerRef = useRef(null);
  const [status, setStatus] = useState("starting"); // starting | scanning | denied | notfound | busy | error
  const [attempt, setAttempt] = useState(0);
  const idRef = useRef("qr-" + Math.random().toString(36).slice(2, 8));
  // The camera keeps decoding the same code every frame (~10fps) while it's
  // still in view — without this, one physical scan fired onScan (and every
  // toast/mutation/sale it triggers) dozens of times. Only the first read of
  // a given code per mount gets through.
  const lastCodeRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    setStatus("starting");
    lastCodeRef.current = null;
    const el = document.getElementById(idRef.current);
    if (!el) return undefined;
    const scanner = new Html5Qrcode(idRef.current, { verbose: false });
    scannerRef.current = scanner;
    Html5Qrcode.getCameras()
      .then((cams) => {
        if (!mounted) return;
        if (!cams || cams.length === 0) { setStatus("notfound"); return; }
        const camId = cams[cams.length - 1].id;
        return scanner.start(
          camId,
          { fps: 10, qrbox: { width: 220, height: 220 } },
          (decoded) => {
            if (decoded === lastCodeRef.current) return;
            lastCodeRef.current = decoded;
            onScan?.(decoded);
          },
          () => {}
        ).then(() => {
          if (!mounted) {
            scanner.stop().then(() => { try { scanner.clear(); } catch (e) {} }).catch(() => {});
            return;
          }
          setStatus("scanning");
        });
      })
      .catch((err) => mounted && setStatus(classifyCameraError(err)));

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
  }, [attempt]);

  return (
    <div className={cn("space-y-3", className)}>
      <div className="relative overflow-hidden rounded-clay bg-clay-ink ring-1 ring-clay-line" style={{ minHeight: height }}>
        <div id={idRef.current} ref={ref} style={{ width: "100%" }} />
        {status !== "scanning" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-clay-ink px-6 text-center text-white/90" style={{ minHeight: height }}>
            {status === "starting" ? (
              <>
                <Camera className="h-10 w-10 animate-pulse" />
                <p className="text-sm">Requesting camera…</p>
              </>
            ) : (
              <>
                <CameraOff className="h-10 w-10 text-white/60" />
                <p className="max-w-xs text-sm text-white/70" data-testid="camera-error-message">{STATUS_COPY[status] || STATUS_COPY.error}</p>
                <Button size="sm" variant="soft" onClick={() => setAttempt((a) => a + 1)} data-testid="camera-retry-btn">
                  <RefreshCw className="h-4 w-4" /> Try again
                </Button>
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
