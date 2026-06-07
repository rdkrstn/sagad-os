import type { LucideIcon } from "lucide-react";
import Image from "next/image";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "good" | "warning" | "danger" | "info";

const statusToneClasses: Record<Tone, string> = {
  neutral: "border-border bg-surface-2 text-muted-foreground",
  good: "border-[var(--sui-green-border)] bg-[var(--sui-green-soft)] text-[var(--accent-text)]",
  warning: "border-[var(--warning-border)] bg-[var(--warning-soft)] text-warning",
  danger: "border-[var(--danger-border)] bg-[var(--danger-soft)] text-danger",
  info: "border-[var(--info-border)] bg-[var(--info-soft)] text-info",
};

export function toneFromProductStatus(status: string): Tone {
  const normalized = status.toLowerCase();

  if (
    normalized.includes("fail") ||
    normalized.includes("reject") ||
    normalized.includes("blocked") ||
    normalized.includes("error") ||
    normalized.includes("high risk") ||
    normalized.includes("urgent")
  ) {
    return "danger";
  }

  if (
    normalized.includes("pending") ||
    normalized.includes("review") ||
    normalized.includes("approval") ||
    normalized.includes("degraded") ||
    normalized.includes("missing") ||
    normalized.includes("watch")
  ) {
    return "warning";
  }

  if (
    normalized.includes("healthy") ||
    normalized.includes("approved") ||
    normalized.includes("ready") ||
    normalized.includes("sent") ||
    normalized.includes("open") ||
    normalized.includes("resolved") ||
    normalized.includes("eligible") ||
    normalized.includes("active") ||
    normalized.includes("connected")
  ) {
    return "good";
  }

  if (
    normalized.includes("draft") ||
    normalized.includes("queued") ||
    normalized.includes("planned") ||
    normalized.includes("dry-run") ||
    normalized.includes("preview") ||
    normalized.includes("mock") ||
    normalized.includes("trace")
  ) {
    return "info";
  }

  return "neutral";
}

export function LogoPlaceholder({
  size = 30,
  label = "LOGO",
}: {
  size?: number;
  label?: string;
}) {
  return (
    <div
      aria-label="SagadOS logo placeholder"
      className="grid shrink-0 place-items-center border border-dashed border-[var(--border-strong)] bg-surface-2 font-mono text-[8px] font-bold uppercase tracking-[0.08em] text-muted-foreground"
      role="img"
      style={{ height: size, width: size }}
    >
      <span>{label}</span>
    </div>
  );
}

export function SagadLogo({
  markOnly = false,
  theme = "dark",
  size = 30,
}: {
  markOnly?: boolean;
  theme?: "dark" | "light";
  size?: number;
}) {
  const src = markOnly
    ? theme === "dark"
      ? "/brand/sagados-b-logo.svg"
      : "/brand/sagados-w-logo.svg"
    : theme === "dark"
      ? "/brand/sagados-horizontal-monochrome-w.svg"
      : "/brand/sagados-horizontal-monochrome-b.svg";

  return (
    <Image
      alt={markOnly ? "SagadOS" : "SagadOS wordmark"}
      className={cn(
        "shrink-0 border border-border object-contain",
        markOnly ? "bg-black" : "bg-white",
      )}
      height={markOnly ? size : Math.round(size * 1.8)}
      src={src}
      width={markOnly ? size : Math.round(size * 4.6)}
    />
  );
}

export function Panel({
  title,
  eyebrow,
  action,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  eyebrow?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Card className={cn("gap-0 overflow-hidden rounded-md py-0 shadow-none", className)}>
      <CardHeader className="flex min-h-11 flex-col gap-2 border-b border-border px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
              {eyebrow}
            </div>
          ) : null}
          <CardTitle className="text-sm font-semibold tracking-tight">
            {title}
          </CardTitle>
        </div>
        {action ? <div className="w-full shrink-0 sm:w-auto">{action}</div> : null}
      </CardHeader>
      <CardContent className={cn("p-0", bodyClassName)}>{children}</CardContent>
    </Card>
  );
}

export function StatusPill({
  children,
  tone,
  status,
  className,
}: {
  children: ReactNode;
  tone?: Tone;
  status?: string;
  className?: string;
}) {
  const resolvedTone = tone ?? toneFromProductStatus(status ?? String(children));

  return (
    <Badge
      className={cn(
        "h-6 rounded-full px-2 text-[11px] font-bold uppercase tracking-[0.04em]",
        statusToneClasses[resolvedTone],
        className,
      )}
      variant="outline"
    >
      {children}
    </Badge>
  );
}

export function MetricCard({
  label,
  value,
  detail,
  delta,
  icon: Icon,
  className,
}: {
  label: string;
  value: string | number;
  detail?: string;
  delta?: string;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <div className={cn("rounded-md border border-border bg-card p-3 shadow-none", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
          <div className="mt-1 text-2xl font-bold text-foreground">
            {value}
          </div>
        </div>
        {Icon ? (
          <span className="grid size-8 shrink-0 place-items-center rounded-md border border-border bg-surface-2 text-muted-foreground">
            <Icon aria-hidden="true" size={16} />
          </span>
        ) : null}
      </div>
      <div className="mt-2 flex min-h-5 items-center justify-between gap-2 text-xs">
        {detail ? <span className="truncate text-muted-foreground">{detail}</span> : <span />}
        {delta ? (
          <span className="font-bold text-[var(--accent-text)]">{delta}</span>
        ) : null}
      </div>
    </div>
  );
}

export function ConfidenceScore({
  value,
  label = "Confidence",
  className,
}: {
  value: number;
  label?: string;
  className?: string;
}) {
  const normalized = Math.max(0, Math.min(100, value));
  const tone: Tone = normalized >= 88 ? "good" : normalized >= 72 ? "warning" : "danger";

  return (
    <div className={cn("min-w-32", className)}>
      <div className="mb-1 flex items-center justify-between gap-2 text-xs">
        <span className="font-medium text-muted-foreground">{label}</span>
        <StatusPill tone={tone}>{normalized}%</StatusPill>
      </div>
      <Progress className="h-1.5 bg-surface-2" value={normalized} />
    </div>
  );
}

export function SourcePill({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <Badge
      className={cn("h-6 rounded-full border-border bg-surface-2 px-2 text-[11px] text-muted-foreground", className)}
      variant="outline"
    >
      {children}
    </Badge>
  );
}

export function ApprovalActionBar({
  disabled,
  onApprove,
  onEdit,
  onReject,
  onEscalate,
  onMissingKnowledge,
  onTakeOver,
  className,
}: {
  disabled?: boolean;
  onApprove?: () => void;
  onEdit?: () => void;
  onReject?: () => void;
  onEscalate?: () => void;
  onMissingKnowledge?: () => void;
  onTakeOver?: () => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center justify-end gap-2", className)}>
      <Button disabled={disabled} onClick={onReject} size="sm" type="button" variant="destructive">
        Reject
      </Button>
      <Button disabled={disabled} onClick={onEscalate} size="sm" type="button" variant="outline">
        Escalate
      </Button>
      <Button disabled={disabled} onClick={onMissingKnowledge} size="sm" type="button" variant="outline">
        Mark Missing Knowledge
      </Button>
      <Button disabled={disabled} onClick={onTakeOver} size="sm" type="button" variant="outline">
        Take Over
      </Button>
      <Button disabled={disabled} onClick={onEdit} size="sm" type="button" variant="outline">
        Edit Draft
      </Button>
      <Button disabled={disabled} onClick={onApprove} size="sm" type="button">
        Approve & Send
      </Button>
    </div>
  );
}

export function TerminalBlock({
  lines,
  className,
}: {
  lines: Array<{ label?: string; text: string }>;
  className?: string;
}) {
  return (
    <pre className={cn("overflow-auto rounded-lg border border-white/15 bg-[#0a0a0a] p-4 font-mono text-xs leading-7 text-white", className)}>
      {lines.map((line, index) => (
        <span key={`${line.text}-${index}`}>
          {line.label ? (
            <span className="text-[var(--sui-green-bright)]">{line.label}</span>
          ) : null}
          {line.text}
          {"\n"}
        </span>
      ))}
    </pre>
  );
}

export function CodeBlock({ code, className }: { code: string; className?: string }) {
  return (
    <pre className={cn("overflow-auto whitespace-pre-wrap rounded-lg border border-white/15 bg-[#0a0a0a] p-4 font-mono text-xs leading-7 text-[#d7fff5]", className)}>
      {code}
    </pre>
  );
}

export function EmptyState({
  title,
  description,
  className,
}: {
  title: string;
  description: string;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border border-dashed border-border bg-surface-2 p-5 text-sm", className)}>
      <div className="font-semibold text-foreground">{title}</div>
      <p className="mt-1 leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}
