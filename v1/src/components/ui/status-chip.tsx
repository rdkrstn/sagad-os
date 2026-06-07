import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type StatusTone = "neutral" | "good" | "warning" | "danger" | "info";

const toneClasses: Record<StatusTone, string> = {
  neutral: "border-border bg-surface-2 text-muted-foreground",
  good: "border-[rgba(0,212,170,0.42)] bg-[rgba(0,212,170,0.12)] text-[var(--accent-text)]",
  warning: "border-[var(--warning-border)] bg-[var(--warning-soft)] text-warning",
  danger: "border-[var(--danger-border)] bg-[var(--danger-soft)] text-danger",
  info: "border-[var(--info-border)] bg-[var(--info-soft)] text-info",
};

export function toneFromStatus(status: string): StatusTone {
  const normalized = status.toLowerCase();

  if (
    normalized.includes("fail") ||
    normalized.includes("risk") ||
    normalized.includes("overdue") ||
    normalized.includes("escalat") ||
    normalized.includes("reject") ||
    normalized.includes("blocked") ||
    normalized.includes("high risk") ||
    normalized.includes("urgent")
  ) {
    return "danger";
  }

  if (
    normalized.includes("low") ||
    normalized.includes("pending") ||
    normalized.includes("review") ||
    normalized.includes("approval") ||
    normalized.includes("missing") ||
    normalized.includes("watch") ||
    normalized.includes("degraded")
  ) {
    return "warning";
  }

  if (
    normalized.includes("ok") ||
    normalized.includes("healthy") ||
    normalized.includes("approved") ||
    normalized.includes("sent") ||
    normalized.includes("open") ||
    normalized.includes("resolved") ||
    normalized.includes("eligible") ||
    normalized.includes("active")
  ) {
    return "good";
  }

  if (
    normalized.includes("draft") ||
    normalized.includes("queued") ||
    normalized.includes("planned") ||
    normalized.includes("preview") ||
    normalized.includes("dry-run") ||
    normalized.includes("mock")
  ) {
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
        "h-6 rounded-full px-2 text-[11px] font-bold uppercase tracking-[0.04em]",
        toneClasses[tone],
      )}
      variant="outline"
    >
      {children}
    </Badge>
  );
}
