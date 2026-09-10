import React from "react";
import { cn } from "../../lib/utils";

export function Logo({ className, size = "md", mono }) {
  const s = { sm: "text-lg", md: "text-2xl", lg: "text-4xl", xl: "text-6xl" }[size];
  const dot = { sm: "h-2 w-2", md: "h-2.5 w-2.5", lg: "h-3.5 w-3.5", xl: "h-5 w-5" }[size];
  return (
    <span className={cn("inline-flex items-end gap-1 font-extrabold tracking-tight lowercase", s, mono ? "text-clay-ink" : "text-clay-ink", className)}>
      dot
      <span className={cn("mb-1 rounded-full bg-accent", dot)} />
    </span>
  );
}
