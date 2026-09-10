import React from "react";
import { cn } from "../../lib/utils";

export function Button({ className, variant = "primary", size = "md", asChild, ...props }) {
  const variants = {
    primary: "bg-accent text-white hover:bg-accent-ink shadow-clay",
    soft: "bg-accent-soft text-accent-ink hover:bg-[#dfe3ff]",
    ghost: "bg-transparent text-clay-ink hover:bg-clay-line",
    outline: "bg-white text-clay-ink ring-1 ring-clay-line hover:bg-clay-surface",
    danger: "bg-rose2 text-white hover:brightness-95 shadow-clay",
    success: "bg-mint text-white hover:brightness-95 shadow-clay",
    dark: "bg-clay-ink text-white hover:bg-black",
  };
  const sizes = { sm: "h-9 px-3.5 text-sm", md: "h-11 px-5 text-sm", lg: "h-12 px-6 text-base", icon: "h-10 w-10" };
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-pill font-semibold transition-all duration-200 active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}

export function Card({ className, tint, ...props }) {
  const tints = {
    mint: "bg-mint-soft", amber: "bg-amber2-soft", rose: "bg-rose2-soft",
    accent: "bg-accent-soft", lilac: "bg-lilac-soft", sky: "bg-sky2-soft", surface: "bg-clay-surface",
  };
  return (
    <div
      className={cn("rounded-clay bg-clay-card p-5 shadow-clay ring-1 ring-clay-line/60", tint && tints[tint], className)}
      {...props}
    />
  );
}

export function IconBadge({ icon: Icon, className, tone = "accent" }) {
  const tones = {
    accent: "text-accent-ink", mint: "text-mint", amber: "text-amber2",
    rose: "text-rose2", lilac: "text-lilac", sky: "text-sky2", ink: "text-clay-ink",
  };
  return (
    <span className={cn("inline-flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-clay ring-1 ring-clay-line/70", className)}>
      <Icon className={cn("h-[18px] w-[18px]", tones[tone])} strokeWidth={2} />
    </span>
  );
}

export function Input({ className, ...props }) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-2xl bg-clay-surface px-4 text-sm text-clay-ink placeholder:text-clay-muted outline-none ring-1 ring-clay-line focus:ring-2 focus:ring-accent/50 transition-all",
        className
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        "w-full rounded-2xl bg-clay-surface px-4 py-3 text-sm text-clay-ink placeholder:text-clay-muted outline-none ring-1 ring-clay-line focus:ring-2 focus:ring-accent/50 transition-all",
        className
      )}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }) {
  return (
    <select
      className={cn(
        "h-11 w-full rounded-2xl bg-clay-surface px-4 text-sm text-clay-ink outline-none ring-1 ring-clay-line focus:ring-2 focus:ring-accent/50 transition-all appearance-none cursor-pointer",
        className
      )}
      {...props}
    >
      {children}
    </select>
  );
}

export function Label({ className, ...props }) {
  return <label className={cn("mb-1.5 block text-xs font-semibold uppercase tracking-wide text-clay-muted", className)} {...props} />;
}

export function Badge({ className, children, tone = "gray" }) {
  const tones = {
    gray: "bg-clay-line text-clay-muted",
    mint: "bg-mint-soft text-[#1f8a6a]",
    amber: "bg-amber2-soft text-[#96702a]",
    rose: "bg-rose2-soft text-[#a8443b]",
    accent: "bg-accent-soft text-accent-ink",
    lilac: "bg-lilac-soft text-[#6d54c9]",
    sky: "bg-sky2-soft text-[#2f79b0]",
  };
  return <span className={cn("inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-xs font-semibold", tones[tone], className)}>{children}</span>;
}

export function Skeleton({ className }) {
  return <div className={cn("skeleton h-4 w-full", className)} />;
}
