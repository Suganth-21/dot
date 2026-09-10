import React, { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { Download, Printer } from "lucide-react";
import { Button } from "../ui";
import { cn } from "../../lib/utils";

// On-device barcode generation for the retail layer — a retailer registering
// stock generates their own scannable QR for the batch right there on the
// phone, rather than depending on a code already printed on the strip. The
// QR encodes the batch id itself; anyone downstream (agent, distributor,
// manufacturer, /verify) can scan it back in through the exact same
// QrScanner component that already reads printed codes.
export default function QrCodeGenerator({ value, drugName, batchId, size = 220, className, actions = true }) {
  const canvasRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!canvasRef.current || !value) return;
    setReady(false);
    QRCode.toCanvas(
      canvasRef.current,
      value,
      { width: size, margin: 1, color: { dark: "#1c1b19", light: "#ffffff" } },
      (err) => setReady(!err)
    );
  }, [value, size]);

  const download = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `${batchId || "batch"}-qr.png`;
    a.click();
  };

  const print = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dataUrl = canvas.toDataURL("image/png");
    const win = window.open("", "_blank", "width=420,height=560");
    if (!win) return;
    win.document.write(`
      <html><head><title>${batchId || "Batch"} label</title>
      <style>
        body { font-family: system-ui, sans-serif; text-align: center; padding: 24px; }
        img { width: 240px; height: 240px; }
        .id { font-size: 15px; font-weight: 700; margin-top: 12px; letter-spacing: 0.02em; }
        .name { font-size: 13px; color: #555; margin-top: 4px; }
      </style></head>
      <body>
        <img src="${dataUrl}" />
        <div class="id">${batchId || ""}</div>
        <div class="name">${drugName || ""}</div>
        <script>window.onload = () => { window.print(); };</script>
      </body></html>
    `);
    win.document.close();
  };

  return (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      <div className="rounded-2xl bg-white p-3 shadow-clay ring-1 ring-clay-line" data-testid="generated-qr-wrap">
        <canvas ref={canvasRef} width={size} height={size} data-testid="generated-qr-canvas" />
      </div>
      {batchId && <div className="text-center text-sm font-bold tracking-wide text-clay-ink">{batchId}</div>}
      {actions && (
        <div className="flex gap-2">
          <Button variant="soft" size="sm" onClick={download} disabled={!ready} data-testid="qr-download-btn">
            <Download className="h-4 w-4" /> Download
          </Button>
          <Button variant="soft" size="sm" onClick={print} disabled={!ready} data-testid="qr-print-btn">
            <Printer className="h-4 w-4" /> Print label
          </Button>
        </div>
      )}
    </div>
  );
}
