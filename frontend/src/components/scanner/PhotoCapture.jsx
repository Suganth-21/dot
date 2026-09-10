import React, { useRef, useState } from "react";
import { toast } from "sonner";
import { Camera, Loader2 } from "lucide-react";
import { uploadPhoto } from "../../services/uploadService";
import { cn } from "../../lib/utils";

// Real photo capture, backed by POST /api/uploads/photo — opens the
// device camera on mobile (accept="image/*" capture="environment"), a
// file picker on desktop, actually uploads the bytes, and hands the
// caller back the server-computed SHA-256 photoHash (not a client-side
// placeholder string). Matches the dashed-border button shape every page
// already used for the mock "Photo captured" toggle, so no visual change.
export default function PhotoCapture({ onCaptured, idleLabel = "Tap to capture photo", capturedLabel = "Photo captured ✓", testId, className }) {
  const inputRef = useRef(null);
  const [status, setStatus] = useState("idle"); // idle | uploading | done | error
  const [previewUrl, setPreviewUrl] = useState(null);

  const pick = () => inputRef.current?.click();

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file later
    if (!file) return;
    setStatus("uploading");
    setPreviewUrl(URL.createObjectURL(file));
    try {
      const res = await uploadPhoto(file);
      setStatus("done");
      onCaptured?.(res.photoHash, res.url);
      toast.success("Photo uploaded");
    } catch (err) {
      setStatus("error");
      toast.error(err.message || "Photo upload failed");
    }
  };

  return (
    <div className={className}>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={onFile}
        data-testid={testId ? `${testId}-input` : undefined}
      />
      <button
        type="button"
        onClick={pick}
        disabled={status === "uploading"}
        data-testid={testId}
        className={cn(
          "flex w-full items-center justify-center gap-2 overflow-hidden rounded-2xl border-2 border-dashed py-6 text-sm transition-colors",
          status === "done" ? "border-mint bg-mint-soft text-[#1f8a6a]"
            : status === "error" ? "border-rose2 bg-rose2-soft text-rose2"
            : "border-clay-line text-clay-muted hover:bg-clay-surface"
        )}
      >
        {status === "done" && previewUrl && (
          <img src={previewUrl} alt="" className="h-8 w-8 rounded-lg object-cover" />
        )}
        {status === "uploading" ? <Loader2 className="h-5 w-5 animate-spin" /> : <Camera className="h-5 w-5" />}
        {status === "uploading" ? "Uploading…" : status === "done" ? capturedLabel : status === "error" ? "Upload failed — tap to retry" : idleLabel}
      </button>
    </div>
  );
}
