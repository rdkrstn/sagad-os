import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StatusTone = "neutral" | "good" | "warning" | "danger" | "info";

const toneClasses: Record<StatusTone, string> = {
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
  good: "border-emerald-200 bg-emerald-50 text-emerald-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",
  danger: "border-rose-200 bg-rose-50 text-rose-700",
  info: "border-sky-200 bg-sky-50 text-sky-700",
};

export function toneFromStatus(status: string): StatusTone {
  const normalized = status.toLowerCase();

  if (
    normalized.includes("fail") ||
    normalized.includes("risk") ||
    normalized.includes("overdue") ||
    normalized.includes("escalat")
  ) {
    return "danger";
  }

  if (
    normalized.includes("low") ||
    normalized.includes("pending") ||
    normalized.includes("review") ||
    normalized.includes("approval")
  ) {
    return "warning";
  }

  if (
    normalized.includes("ok") ||
    normalized.includes("healthy") ||
    normalized.includes("approved") ||
    normalized.includes("active")
  ) {
    return "good";
  }

  if (normalized.includes("draft") || normalized.includes("queued")) {
    return "info";
  }

  return "neutral";
}

export function StatusChip({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: StatusTone;
}) {
  return (
    <Badge
      className={cn(
        "h-6 rounded-md px-2 text-[11px] font-medium uppercase tracking-[0.04em]",
        toneClasses[tone],
      )}
      variant="outline"
    >
      {children}
    </Badge>
  );
}
