"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition, type ReactNode } from "react";
import {
  AlertCircle,
  Bot,
  Brain,
  CheckCheck,
  Clock3,
  Eye,
  FileText,
  GitBranch,
  ListChecks,
  Network,
  PencilLine,
  Route,
  Search,
  Send,
  ShieldCheck,
  Siren,
  RefreshCw,
  Sparkles,
  UserRound,
  Wrench,
  XCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  EmptyState,
  SourcePill,
  StatusPill,
} from "@/components/product/product-ui";
import {
  asArray,
  asRecord,
  nestedArray,
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";
import { cn } from "@/lib/utils";
import {
  compactClock,
  durationLabel,
  elapsedSecondsSince,
  parseIsoMs,
  secondsBetween,
  turnOwnerOf,
} from "@/lib/time";

type RailTab =
  | "context"
  | "memory"
  | "knowledge"
  | "policy"
  | "qa"
  | "audit"
  | "trace";
type RailTabConfig = {
  id: RailTab;
  label: string;
  count?: number;
  icon: LucideIcon;
};
type DeliveryState = {
  label: string;
  className: string;
  icon: LucideIcon;
};

function initials(name: string) {
  const parts = name.split(" ").filter(Boolean);
  return (parts[0]?.[0] ?? "S") + (parts[1]?.[0] ?? "O");
}

function confidenceNumber(row: LooseRecord) {
  const raw = textOf(row, ["confidence", "aiConfidence"], "0");
  const parsed = Number.parseFloat(raw.replace("%", ""));
  if (Number.isFinite(parsed)) return Math.max(0, Math.min(100, parsed));
  const classifier = asRecord(row.classifier);
  const classifierConfidence = Number(classifier.confidence);
  return Number.isFinite(classifierConfidence)
    ? Math.round(classifierConfidence * 100)
    : 0;
}

function selectedAgent(row: LooseRecord) {
  const assigned = textOf(row, ["assignedTo"], "");
  if (assigned.includes("Sales Agent") || assigned.includes("Support Agent")) {
    return assigned;
  }
  const intent = textOf(row, ["intent", "driver"], "").toLowerCase();
  return intent.includes("sales") || intent.includes("pricing")
    ? "Sales Agent"
    : "Support Agent";
}

function selectedSkill(row: LooseRecord) {
  const driver = textOf(row, ["driver", "intent", "reason"], "").toLowerCase();
  if (driver.includes("refund") || driver.includes("return")) return "Refund Resolver";
  if (driver.includes("sales") || driver.includes("sizing") || driver.includes("pricing")) {
    return "Sales Sizing Assistant";
  }
  if (driver.includes("angry") || driver.includes("escal")) return "Angry Customer De-escalation";
  if (driver.includes("account")) return "Account Verification";
  return "Order Status Lookup";
}

function graphVersion(row: LooseRecord) {
  return textOf(row, ["graph", "graphVersion"], "Default Support Graph v0.1.4");
}

function riskLevel(row: LooseRecord) {
  const priority = textOf(row, ["priority", "risk", "riskLevel"], "Medium");
  if (priority.toLowerCase().includes("urgent")) return "High";
  return priority;
}

function workflowState(row: LooseRecord) {
  const status = textOf(row, ["queueStatus", "hitlStatus", "status"], "Pending approval");
  const sendStatus = textOf(row, ["sendStatus"], "").toLowerCase();
  const confidence = confidenceNumber(row);

  if (status.toLowerCase().includes("missing")) return "Missing knowledge";
  if (status.toLowerCase().includes("reject")) return "Rejected";
  if (status.toLowerCase().includes("escal")) return "Escalated";
  if (
    sendStatus === "sent" ||
    (sendStatus.includes("sent") && !sendStatus.includes("not"))
  ) {
    return "Sent";
  }
  if (confidence >= 88 && !status.toLowerCase().includes("approval")) {
    return "Auto-send eligible";
  }
  return "Pending approval";
}

function messageBody(message: LooseRecord) {
  return textOf(message, ["body", "content", "text", "message"], "");
}

function fieldValue(row: LooseRecord, keys: string[], fallback = "Unknown") {
  const value = textOf(row, keys, fallback);
  return value || fallback;
}

function readableDate(value: string) {
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return value;
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Short absolute time for a message, used as a tooltip on the turn-duration label. */
function absoluteTimeLabel(message: LooseRecord): string {
  const preset = textOf(message, ["time"], "");
  if (preset) return preset;
  const iso = textOf(message, ["createdAt"], "");
  const parsed = new Date(iso);
  if (Number.isFinite(parsed.getTime())) {
    return parsed.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }
  return iso;
}

/**
 * Chess-clock turn timer. Counts up from the last message's createdAt, labeled with
 * whose turn it is to reply. Renders a stable "--:--" on the server and ticks on the
 * client after mount to avoid a hydration mismatch.
 */
function TurnClock({
  messages,
  className,
}: {
  messages: LooseRecord[];
  className?: string;
}) {
  const last = messages[messages.length - 1];
  const lastIso = last ? textOf(last, ["createdAt"], "") : "";
  const lastRole = last ? textOf(last, ["role", "senderType", "sender"], "") : "";
  const owner = last ? turnOwnerOf(lastRole) : null;

  const [nowMs, setNowMs] = useState<number | null>(null);
  useEffect(() => {
    if (!lastIso) return;
    // Drive the clock from the interval callback only. Calling setState
    // synchronously in the effect body is flagged by react-hooks/set-state-in-effect
    // and causes cascading renders; the interval tick is the legitimate "subscribe
    // to external time" path. nowMs starts null -> "--:--" until the first tick.
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [lastIso]);

  if (!owner) return null;
  const seconds = nowMs === null ? null : elapsedSecondsSince(lastIso, nowMs);
  const isOurTurn = owner === "Our turn";

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold tabular-nums",
        isOurTurn
          ? "border-[rgba(0,212,170,0.42)] bg-[rgba(0,212,170,0.12)] text-[var(--accent-text)]"
          : "border-border bg-surface-2 text-muted-foreground",
        className,
      )}
      title={
        lastIso
          ? `Last reply at ${absoluteTimeLabel(last ?? {})}`
          : "Waiting for the first message"
      }
    >
      <Clock3 aria-hidden="true" className="size-3.5" />
      <span className="uppercase tracking-[0.04em]">{owner}</span>
      <span aria-live="polite">{seconds === null ? "--:--" : compactClock(seconds)}</span>
    </div>
  );
}

/**
 * Compact, ticking "Xm ago" age for a timestamp. Renders the full readable date on the
 * server (stable) and switches to a live relative label after mount, with the full date
 * kept as a tooltip. Avoids hydration mismatch by gating the relative label on mount.
 */
function LiveAge({ iso, fallback = "Unknown" }: { iso: string; fallback?: string }) {
  const [nowMs, setNowMs] = useState<number | null>(null);
  useEffect(() => {
    if (parseIsoMs(iso) === null) return;
    // setState only via the interval callback (see TurnClock note). nowMs starts
    // null -> the stable full date is rendered until the first tick, which avoids a
    // hydration mismatch and the react-hooks/set-state-in-effect violation.
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [iso]);

  const ms = parseIsoMs(iso);
  if (ms === null) return <span>{fallback}</span>;
  const full = readableDate(iso);
  if (nowMs === null) return <span title={full}>{full}</span>;
  const seconds = Math.max(0, Math.round((nowMs - ms) / 1000));
  return (
    <span title={full} className="tabular-nums">
      {durationLabel(seconds)} ago
    </span>
  );
}

function optionalBoolean(record: LooseRecord, keys: string[]): boolean | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "boolean") return value;
    if (typeof value === "string") {
      const normalized = value.trim().toLowerCase();
      if (["true", "yes", "1", "required", "enabled"].includes(normalized)) {
        return true;
      }
      if (["false", "no", "0", "not required", "disabled"].includes(normalized)) {
        return false;
      }
    }
  }

  return null;
}

function stringList(record: LooseRecord, keys: string[]): string[] {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) {
      return value.map(String).filter((item) => item.trim().length > 0);
    }
    if (typeof value === "string" && value.trim()) {
      return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    }
  }

  return [];
}

function policyStatus(row: LooseRecord): string {
  const decision = asRecord(row.policyDecision ?? row.policy_decision);
  const allowed =
    optionalBoolean(row, ["allowed", "allowedValue"]) ??
    optionalBoolean(decision, ["allowed"]);

  if (allowed !== null) return allowed ? "Allowed" : "Blocked";
  return textOf(row, ["status", "planStatus"], "Policy recorded");
}

function approvalLabel(row: LooseRecord): string {
  const decision = asRecord(row.policyDecision ?? row.policy_decision);
  const required =
    optionalBoolean(row, ["requiresApproval", "requires_approval"]) ??
    optionalBoolean(decision, ["requiresApproval", "requires_approval"]);

  if (required === null) return "Unknown";
  return required ? "Required" : "Not required";
}

function runModeLabel(row: LooseRecord): string {
  const decision = asRecord(row.policyDecision ?? row.policy_decision);
  const dryRun =
    optionalBoolean(row, ["dryRun", "dry_run"]) ??
    optionalBoolean(decision, ["dryRun", "dry_run"]);

  if (dryRun !== null) return dryRun ? "Dry-run" : "Live";
  return textOf(row, ["liveMode", "mode"], "Policy decides");
}

function reasonsFor(row: LooseRecord): string[] {
  const decision = asRecord(row.policyDecision ?? row.policy_decision);
  const reasons = [
    ...stringList(row, ["policyReasons", "policy_reasons", "reasons"]),
    ...stringList(decision, ["policyReasons", "policy_reasons", "reasons"]),
    textOf(row, ["blockedReason", "blocked_reason"], ""),
    textOf(decision, ["blockedReason", "blocked_reason"], ""),
  ].filter(Boolean);

  return [...new Set(reasons)];
}

function correlateToolEvidence(
  plans: LooseRecord[],
  results: LooseRecord[],
): LooseRecord[] {
  const resultByPlanId = new Map(
    results.map((result) => [textOf(result, ["planId", "plan_id"], ""), result]),
  );
  const rows = plans.map((plan) => {
    const planId = textOf(plan, ["id", "planId", "plan_id"], "");
    const result = resultByPlanId.get(planId) ?? {};
    const resultId = textOf(result, ["id", "resultId", "result_id"], "");
    return {
      id: `${planId || "plan"}-${resultId || "pending"}`,
      planId,
      resultId,
      provider: textOf(plan, ["provider"], textOf(result, ["provider"], "Agent Studio")),
      toolName: textOf(plan, ["toolName", "tool_name", "name"], textOf(result, ["toolName", "tool_name", "name"], "Provider action")),
      action: textOf(plan, ["action"], textOf(result, ["detail"], "")),
      planStatus: policyStatus(plan),
      resultStatus: textOf(result, ["status", "result"], resultId ? "Logged" : "No result"),
      detail: textOf(result, ["detail", "description"], textOf(plan, ["action"], "Tool plan recorded.")),
      riskLevel: textOf(plan, ["riskLevel", "risk_level", "risk"], textOf(result, ["riskLevel", "risk_level", "risk"], "Unknown")),
      requiresApproval:
        optionalBoolean(plan, ["requiresApproval", "requires_approval"]) ??
        optionalBoolean(result, ["requiresApproval", "requires_approval"]),
      dryRun:
        optionalBoolean(plan, ["dryRun", "dry_run"]) ??
        optionalBoolean(result, ["dryRun", "dry_run"]),
      liveMode: textOf(plan, ["liveMode"], textOf(result, ["liveMode"], "")),
      policyDecision: plan.policyDecision ?? plan.policy_decision ?? result.policyDecision ?? result.policy_decision,
      policyReasons: [
        ...reasonsFor(plan),
        ...reasonsFor(result),
      ],
      blockedReason:
        textOf(plan, ["blockedReason", "blocked_reason"], "") ||
        textOf(result, ["blockedReason", "blocked_reason"], ""),
    };
  });
  const correlatedResultIds = new Set(rows.map((row) => textOf(row, ["resultId"], "")));
  const orphanResults = results
    .filter((result) => !correlatedResultIds.has(textOf(result, ["id"], "")))
    .map((result) => ({
      id: textOf(result, ["id"], "tool-result"),
      planId: textOf(result, ["planId", "plan_id"], ""),
      resultId: textOf(result, ["id"], ""),
      provider: textOf(result, ["provider"], "Agent Studio"),
      toolName: textOf(result, ["toolName", "tool_name", "name"], "Provider action"),
      action: textOf(result, ["action"], ""),
      planStatus: policyStatus(result),
      resultStatus: textOf(result, ["status", "result"], "Logged"),
      detail: textOf(result, ["detail", "description"], "Tool result recorded."),
      riskLevel: textOf(result, ["riskLevel", "risk_level", "risk"], "Unknown"),
      requiresApproval: optionalBoolean(result, ["requiresApproval", "requires_approval"]),
      dryRun: optionalBoolean(result, ["dryRun", "dry_run"]),
      liveMode: textOf(result, ["liveMode"], ""),
      policyDecision: result.policyDecision ?? result.policy_decision,
      policyReasons: reasonsFor(result),
      blockedReason: textOf(result, ["blockedReason", "blocked_reason"], ""),
    }));

  return [...rows, ...orphanResults];
}

function deliveryState(
  message: LooseRecord,
  conversation: LooseRecord,
  isOutbound: boolean,
): DeliveryState | null {
  if (!isOutbound) return null;
  const payload = asRecord(message.payload);
  const raw =
    textOf(message, ["deliveryStatus", "delivery_status"], "") ||
    textOf(payload, [
      "delivery_status",
      "deliveryStatus",
      "message_status",
      "messageStatus",
      "status",
      "read_status",
      "readStatus",
    ], "") ||
    textOf(conversation, ["sendStatus", "send_status"], "");
  const normalized = raw.toLowerCase().replaceAll(" ", "_");

  if (normalized.includes("seen") || normalized.includes("read")) {
    return {
      label: "Seen",
      icon: Eye,
      className: "border-[var(--sui-green-border)] bg-[var(--sui-green-soft)] text-[var(--accent-text)]",
    };
  }
  if (normalized.includes("delivered")) {
    return {
      label: "Delivered",
      icon: CheckCheck,
      className: "border-[var(--sui-green-border)] bg-[var(--sui-green-soft)] text-[var(--accent-text)]",
    };
  }
  if (normalized.includes("sent")) {
    return {
      label: "Sent",
      icon: CheckCheck,
      className: "border-[var(--info-border)] bg-[var(--info-soft)] text-info",
    };
  }
  if (normalized.includes("dry")) {
    return {
      label: "Dry run",
      icon: Clock3,
      className: "border-[var(--info-border)] bg-[var(--info-soft)] text-info",
    };
  }
  if (normalized.includes("fail") || normalized.includes("error")) {
    return {
      label: "Send failed",
      icon: AlertCircle,
      className: "border-[var(--danger-border)] bg-[var(--danger-soft)] text-danger",
    };
  }
  return {
    label: "Pending",
    icon: Clock3,
    className: "border-border bg-surface-2 text-muted-foreground",
  };
}

function EvidenceCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("min-w-0 overflow-hidden rounded-md border border-border bg-surface-2 p-3", className)}>
      {children}
    </div>
  );
}

export function ConversationReview({
  conversations,
  primaryConversation,
}: {
  conversations: unknown;
  primaryConversation: unknown;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const list = useMemo(() => asArray(conversations).map(asRecord), [conversations]);
  const primary = useMemo(() => {
    const candidate = asRecord(primaryConversation);
    return Object.keys(candidate).length > 0 ? candidate : list[0] ?? {};
  }, [list, primaryConversation]);
  const primaryId = textOf(primary, ["id"], "");
  const hasConversation = Boolean(primaryId);
  const primaryDraft = textOf(primary, ["draftReply", "suggestedReply"], "");
  const [draftByConversation, setDraftByConversation] = useState<Record<string, string>>({});
  const [actionByConversation, setActionByConversation] = useState<Record<string, string>>({});
  const [stateByConversation, setStateByConversation] = useState<Record<string, string>>({});
  const [activeRailTab, setActiveRailTab] = useState<RailTab>("context");
  const [isStreaming, setIsStreaming] = useState(false);
  const [localTrailByConversation, setLocalTrailByConversation] = useState<
    Record<string, LooseRecord[]>
  >({});

  const draftReply = draftByConversation[primaryId] ?? primaryDraft;
  const actionMessage = actionByConversation[primaryId] ?? "";
  const messages = nestedArray(primary, ["messages", "thread", "conversation"]).map(asRecord);
  const trail = [
    ...nestedArray(primary, ["decisionTrail", "aiDecisionTrail", "events"]).map(asRecord),
    ...(localTrailByConversation[primaryId] ?? []),
  ];
  const knowledge = nestedArray(primary, ["knowledgeContext", "retrievedKnowledge"]).map(asRecord);
  const memory = nestedArray(primary, ["memoryContext", "memory_context"]).map(asRecord);
  const toolPlans = nestedArray(primary, ["toolPlans", "tool_plans"]).map(asRecord);
  const toolResults = nestedArray(primary, [
    "toolResults",
    "tool_results",
    "deliveryResults",
  ]).map(asRecord);
  const providedToolEvidence = nestedArray(primary, [
    "toolEvidence",
    "tool_evidence",
  ]).map(asRecord);
  const toolEvidence = providedToolEvidence.length > 0
    ? providedToolEvidence
    : correlateToolEvidence(toolPlans, toolResults);
  const policyDecisions = nestedArray(primary, [
    "policyDecisions",
    "toolPolicyDecisions",
    "tool_policy_decisions",
    "policyChecks",
  ]).map(asRecord);
  const policyChecks =
    policyDecisions.length > 0
      ? policyDecisions
      : toolEvidence.map((item) =>
          asRecord({
            ...item,
            status: policyStatus(item),
            policyReasons: reasonsFor(item),
          }),
        );
  const qaFindings = nestedArray(primary, [
    "qaFindings",
    "qa_findings",
    "qaCompliance",
  ]).map(asRecord);
  const confidence = confidenceNumber(primary);
  const currentWorkflowState =
    stateByConversation[primaryId] ?? workflowState(primary);
  const currentAgent = selectedAgent(primary);
  const currentSkill = selectedSkill(primary);
  const currentGraph = graphVersion(primary);
  const currentDriver = textOf(primary, ["driver", "intent", "reason"], "Unknown driver");
  const currentRisk = riskLevel(primary);
  const customerName = textOf(primary, ["customerName", "contact", "name"], "Conversation");
  const sourceId = textOf(primary, ["sourceId"], "");
  const chatwootStatus = textOf(primary, ["chatwootStatus"], "").toLowerCase();
  const sendStatus = textOf(primary, ["sendStatus"], "").toLowerCase();
  const resolveDisabledReason = !hasConversation
    ? "No conversation selected."
    : chatwootStatus === "resolved"
      ? "Conversation is already resolved."
      : !sourceId
        ? "Resolve needs a Chatwoot source ID."
        : sendStatus.includes("dry")
          ? "Resolve is disabled while Chatwoot dry-run is active."
          : "";
  const traceId = textOf(
    primary,
    ["traceId", "langSmithTraceId"],
    primaryId ? `preview-${primaryId}` : "Preview trace",
  );
  const mcpServersUsed = toolEvidence.some((result) =>
    textOf(result, ["toolName", "tool_name", "name"], "").toLowerCase().includes("mcp"),
  )
    ? ["MCP tool layer"]
    : [];
  const railTabs: RailTabConfig[] = [
    { id: "context", label: "Context", icon: Route },
    { id: "memory", label: "Memory", count: memory.length, icon: Brain },
    { id: "knowledge", label: "Knowledge", count: knowledge.length, icon: FileText },
    { id: "policy", label: "Policy", count: policyChecks.length, icon: ShieldCheck },
    { id: "qa", label: "QA", count: qaFindings.length, icon: ListChecks },
    { id: "audit", label: "Audit", count: trail.length, icon: Clock3 },
    { id: "trace", label: "Trace", count: toolEvidence.length, icon: Network },
  ];
  const activeRail = railTabs.find((tab) => tab.id === activeRailTab) ?? railTabs[0];
  const ActiveRailIcon = activeRail.icon;

  function setDraftReply(value: string): void {
    if (!primaryId) return;
    setDraftByConversation((current) => ({ ...current, [primaryId]: value }));
  }

  function setActionMessage(value: string): void {
    if (!primaryId) return;
    setActionByConversation((current) => ({ ...current, [primaryId]: value }));
  }

  function recordLocalWorkflowAction(state: string, detail: string): void {
    if (!primaryId) return;
    setStateByConversation((current) => ({ ...current, [primaryId]: state }));
    setActionMessage(detail);
    setLocalTrailByConversation((current) => ({
      ...current,
      [primaryId]: [
        ...(current[primaryId] ?? []),
        {
          step: state === "Escalated" ? "Escalation created" : "Missing knowledge marked",
          status: state,
          rationale: detail,
          actor: "Supervisor",
          createdAt: "Local session",
        },
      ],
    }));
  }

  async function regenerateDraft() {
    if (!primaryId || isStreaming) return;
    setIsStreaming(true);
    setDraftReply("");

    try {
      const response = await fetch(
        `/api/conversations/${encodeURIComponent(primaryId)}/draft/stream`,
      );
      if (!response.ok || !response.body) {
        setDraftReply("Error: Failed to connect to streaming endpoint.");
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = decoder.decode(value, { stream: true });
        const lines = text.split("\n");
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const token = line.slice(6);
            if (token === "[DONE]") break;
            if (token.startsWith("[ERROR]")) {
              accumulated += ` ${token}`;
              break;
            }
            accumulated += token;
            setDraftReply(accumulated);
          }
        }
      }
    } catch {
      setDraftReply("Error: Streaming connection failed.");
    } finally {
      setIsStreaming(false);
    }
  }

  async function submitDecision(approved: boolean): Promise<void> {
    if (!primaryId) {
      setActionMessage("No conversation selected.");
      return;
    }

    setActionMessage(approved ? "Approving reply..." : "Rejecting reply...");

    try {
      const response = await fetch(
        `/api/conversations/${encodeURIComponent(primaryId)}/approve-send`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved,
            edited_reply: approved ? draftReply : null,
          }),
        },
      );

      const payload = (await response.json()) as unknown;
      const row = asRecord(payload);

      if (!response.ok) {
        setActionMessage(textOf(row, ["detail"], "Agent Studio action failed."));
        return;
      }

      if (!approved) {
        setStateByConversation((current) => ({ ...current, [primaryId]: "Rejected" }));
        setActionMessage("Rejected. Reply remains blocked from customer delivery.");
      } else {
        const sendStatus = textOf(row, ["send_status", "sendStatus"], "updated")
          .toLowerCase()
          .replaceAll(" ", "_");
        if (sendStatus === "failed") {
          setStateByConversation((current) => ({ ...current, [primaryId]: "Pending approval" }));
          setActionMessage("Approved, but provider send failed. Review delivery result.");
        } else if (sendStatus === "dry_run") {
          setStateByConversation((current) => ({ ...current, [primaryId]: "Sent" }));
          setActionMessage("Approved. Chatwoot send stayed in dry-run.");
        } else if (sendStatus === "sent") {
          setStateByConversation((current) => ({ ...current, [primaryId]: "Sent" }));
          setActionMessage("Approved. Reply sent through Chatwoot.");
        } else {
          setStateByConversation((current) => ({ ...current, [primaryId]: "Sent" }));
          setActionMessage("Approved. Send status updated.");
        }
      }

      startTransition(() => router.refresh());
    } catch {
      setActionMessage("Could not reach the approval endpoint.");
    }
  }

  async function submitResolve(): Promise<void> {
    if (!primaryId) {
      setActionMessage("No conversation selected.");
      return;
    }
    if (resolveDisabledReason) {
      setActionMessage(resolveDisabledReason);
      return;
    }

    setActionMessage("Resolving Chatwoot conversation...");

    try {
      const response = await fetch(
        `/api/conversations/${encodeURIComponent(primaryId)}/resolve`,
        {
          method: "POST",
        },
      );
      const payload = (await response.json()) as unknown;
      const row = asRecord(payload);

      if (!response.ok) {
        setActionMessage(textOf(row, ["detail"], "Resolve action failed."));
        return;
      }

      const context = asRecord(row.chatwoot_context);
      const resolved = textOf(context, ["status"], "").toLowerCase() === "resolved";
      const results = nestedArray(row, ["tool_results", "toolResults"]).map(asRecord);
      const failed = results.some(
        (result) =>
          textOf(result, ["tool_name", "toolName"], "") ===
            "chatwoot.conversations.resolve" &&
          textOf(result, ["status"], "").toLowerCase().includes("failed"),
      );

      if (resolved) {
        setStateByConversation((current) => ({ ...current, [primaryId]: "Resolved" }));
        setActionMessage("Resolved in Chatwoot.");
      } else if (failed) {
        setActionMessage("Resolve failed. Review delivery result.");
      } else {
        setActionMessage("Resolve action recorded.");
      }
      startTransition(() => router.refresh());
    } catch {
      setActionMessage("Could not reach the resolve endpoint.");
    }
  }

  return (
    <div className="grid min-w-0 max-w-full gap-3 overflow-x-hidden xl:h-[calc(100vh-5.5rem)] xl:min-h-[620px] xl:grid-cols-[320px_minmax(0,1fr)] 2xl:grid-cols-[320px_minmax(0,1fr)_340px]">
      <aside className="flex min-h-[520px] min-w-0 flex-col overflow-hidden rounded-md border border-border bg-card xl:h-full">
        <div className="border-b border-border p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                Inbox
              </div>
              <h2 className="mt-1 truncate text-base font-bold text-foreground">
                Review Queue
              </h2>
            </div>
            <StatusPill tone="warning">{list.length}</StatusPill>
          </div>
          <div className="mt-3 flex h-9 items-center gap-2 rounded-md border border-border bg-background px-3 text-xs text-muted-foreground">
            <Search aria-hidden="true" className="size-3.5" />
            <span className="truncate">Search conversations, customers, drivers...</span>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {list.length === 0 ? (
            <div className="p-3">
              <EmptyState
                title="No conversations"
                description="Connect Chatwoot through Agent Studio to populate this queue."
              />
            </div>
          ) : null}
          <div className="grid divide-y divide-border">
            {list.map((conversation, index) => {
              const conversationId = textOf(
                conversation,
                ["id", "conversationId", "threadId"],
                "",
              );
              const name = textOf(conversation, ["customerName", "contact", "name"], "Customer");
              const isSelected = conversationId === primaryId;
              const status = textOf(conversation, ["queueStatus", "status"], "Review");
              const href = conversationId
                ? `/conversations?conversationId=${encodeURIComponent(conversationId)}`
                : "/conversations";

              return (
                <Link
                  aria-current={isSelected ? "page" : undefined}
                  className={cn(
                    "relative grid grid-cols-[36px_minmax(0,1fr)_auto] gap-3 px-3 py-3 transition-colors hover:bg-muted",
                    isSelected && "bg-[rgba(0,212,170,0.1)]",
                  )}
                  href={href}
                  key={conversationId || index}
                >
                  <span
                    className={cn(
                      "absolute left-0 top-3 bottom-3 w-0.5 rounded-full bg-transparent",
                      isSelected && "bg-[var(--accent)]",
                    )}
                  />
                  <div className="grid size-9 place-items-center rounded-full bg-surface-2 text-xs font-bold text-foreground">
                    {initials(name)}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <div className="truncate text-sm font-semibold text-foreground">
                        {name}
                      </div>
                      <span className="size-1.5 shrink-0 rounded-full bg-[var(--accent)]" />
                    </div>
                    <div className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                      {textOf(conversation, ["lastMessage", "summary", "intent"], "")}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <SourcePill>{textOf(conversation, ["source", "sourceChannel"], "Chatwoot")}</SourcePill>
                      <SourcePill>{textOf(conversation, ["intent", "driver"], "Driver")}</SourcePill>
                    </div>
                  </div>
                  <div className="grid content-start justify-items-end gap-2">
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {textOf(conversation, ["age", "waitTime"], "")}
                    </div>
                    <StatusPill className="h-5 px-1.5 text-[10px]" status={status}>
                      {status}
                    </StatusPill>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </aside>

      <section className="flex min-h-[620px] min-w-0 flex-col overflow-hidden rounded-md border border-border bg-card xl:h-full">
        <header className="border-b border-border bg-card p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-lg font-bold text-foreground">
                  {hasConversation ? customerName : "No conversation selected"}
                </h2>
                <StatusPill status={currentWorkflowState}>
                  {currentWorkflowState}
                </StatusPill>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span>{currentDriver}</span>
                <span>·</span>
                <span>{textOf(primary, ["source", "sourceChannel"], "Chatwoot")}</span>
                <span>·</span>
                <span>{fieldValue(primary, ["inboxName"], "Inbox")}</span>
              </div>
            </div>
            <StatusPill status={currentRisk}>{currentRisk}</StatusPill>
          </div>

          <div className="mt-3 grid gap-2 rounded-md border border-border bg-surface-2 p-2 text-xs sm:grid-cols-5">
            {[
              { label: "Agent", value: currentAgent, icon: Bot },
              { label: "Skill", value: currentSkill, icon: Sparkles },
              { label: "Graph", value: currentGraph, icon: GitBranch },
              { label: "Trust", value: `${confidence}%`, icon: ShieldCheck },
              { label: "Risk", value: currentRisk, icon: AlertCircle },
            ].map(({ label, value, icon: Icon }) => (
              <div className="flex min-w-0 items-center gap-2" key={label}>
                <span className="grid size-7 shrink-0 place-items-center rounded-sm border border-border bg-card text-muted-foreground">
                  <Icon aria-hidden="true" size={14} />
                </span>
                <div className="min-w-0">
                  <div className="font-mono text-[9px] uppercase text-muted-foreground">
                    {label}
                  </div>
                  <div className="truncate font-semibold text-foreground">{value}</div>
                </div>
              </div>
            ))}
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto bg-background/45 p-3">
          <div className="mx-auto grid max-w-4xl gap-3">
            {messages.length === 0 ? (
              <EmptyState
                title="No thread loaded"
                description="A Chatwoot thread will appear here after Agent Studio receives a message."
              />
            ) : null}
            {messages.map((message, index) => {
              const role = textOf(message, ["role", "senderType", "sender"], "Customer");
              const sender = textOf(message, ["sender", "senderName", "role"], "Customer");
              const normalizedRole = role.toLowerCase();
              const isCustomer =
                normalizedRole.includes("customer") ||
                sender.toLowerCase() === customerName.toLowerCase();
              const isSystem = normalizedRole.includes("system") || normalizedRole.includes("tool");
              const isOutbound = !isCustomer && !isSystem;
              const delivery = deliveryState(message, primary, isOutbound);
              const DeliveryIcon = delivery?.icon;
              // Chess-style per-turn timing: how long this side took to reply after the
              // previous message. The first message has no prior turn, so it shows its
              // absolute time. The absolute time is always kept as a tooltip.
              const absolute = absoluteTimeLabel(message);
              const prevIso = index > 0 ? textOf(messages[index - 1], ["createdAt"], "") : "";
              const thisIso = textOf(message, ["createdAt"], "");
              const turnSeconds = index > 0 ? secondsBetween(prevIso, thisIso) : null;
              const timeContent =
                index > 0 && turnSeconds !== null && turnSeconds > 0
                  ? `replied in ${durationLabel(turnSeconds)}`
                  : absolute;

              if (isSystem) {
                return (
                  <div
                    className="mx-auto max-w-[76%] rounded-md border border-border bg-surface-2 px-3 py-2 text-center text-xs leading-5 text-muted-foreground"
                    key={textOf(message, ["id"], String(index))}
                  >
                    {messageBody(message)}
                  </div>
                );
              }

              return (
                <div
                  className={cn(
                    "flex items-end gap-2",
                    isOutbound ? "justify-end" : "justify-start",
                  )}
                  key={textOf(message, ["id"], String(index))}
                >
                  {!isOutbound ? (
                    <div className="grid size-8 shrink-0 place-items-center rounded-full bg-surface-2 text-[11px] font-bold text-foreground">
                      {initials(sender)}
                    </div>
                  ) : null}
                  <div
                    className={cn(
                      "max-w-[78%] rounded-md border px-3 py-2 shadow-sm",
                      isOutbound
                        ? "border-[rgba(0,212,170,0.38)] bg-[rgba(0,212,170,0.14)]"
                        : "border-border bg-card",
                    )}
                  >
                    <div className="mb-1 flex items-center justify-between gap-3 text-[11px] text-muted-foreground">
                      <span className="font-semibold text-foreground">{sender}</span>
                      <span title={absolute}>{timeContent}</span>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-6 text-foreground">
                      {messageBody(message)}
                    </p>
                    {delivery && DeliveryIcon ? (
                      <div className="mt-2 flex justify-end">
                        <span
                          className={cn(
                            "inline-flex h-5 items-center gap-1 rounded-full border px-2 text-[10px] font-semibold uppercase tracking-[0.04em]",
                            delivery.className,
                          )}
                        >
                          <DeliveryIcon aria-hidden="true" className="size-3" />
                          {delivery.label}
                        </span>
                      </div>
                    ) : null}
                  </div>
                  {isOutbound ? (
                    <div className="grid size-8 shrink-0 place-items-center rounded-full border border-[rgba(0,212,170,0.38)] bg-[rgba(0,212,170,0.12)] text-[var(--accent-text)]">
                      <Bot aria-hidden="true" size={15} />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>

        <div className="sticky bottom-0 z-10 border-t border-border bg-card/98 p-3 shadow-[0_-12px_32px_rgba(0,0,0,0.18)] backdrop-blur">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Sparkles aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
              AI draft reply
              {hasConversation && draftReply && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="ml-2 h-6 gap-1 px-2 text-xs"
                  disabled={isStreaming || isPending}
                  onClick={() => void regenerateDraft()}
                >
                  <RefreshCw className={cn("size-3", isStreaming && "animate-spin")} />
                  {isStreaming ? "Streaming..." : "Regenerate"}
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              {hasConversation && messages.length > 0 ? (
                <TurnClock messages={messages} />
              ) : null}
              <StatusPill tone={confidence >= 88 ? "good" : "warning"}>
                {confidence}% trust
              </StatusPill>
            </div>
          </div>
          <Textarea
            aria-label="AI draft reply"
            className="min-h-24 resize-y bg-background text-sm leading-6"
            disabled={!hasConversation || isPending || isStreaming}
            onChange={(event) => setDraftReply(event.target.value)}
            placeholder="No draft yet. Agent Studio will generate a supervised draft after a conversation arrives."
            value={draftReply}
          />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={!hasConversation || isPending}
                onClick={() => void submitDecision(false)}
                size="sm"
                type="button"
                variant="destructive"
              >
                <XCircle aria-hidden="true" />
                Reject
              </Button>
              <Button
                disabled={!hasConversation || isPending}
                onClick={() =>
                  recordLocalWorkflowAction(
                    "Escalated",
                    "Escalation created for supervisor takeover in this review session.",
                  )
                }
                size="sm"
                type="button"
                variant="outline"
              >
                <Siren aria-hidden="true" />
                Escalate
              </Button>
              <Button
                disabled={!hasConversation || isPending}
                onClick={() =>
                  recordLocalWorkflowAction(
                    "Missing knowledge",
                    "Missing knowledge topic flagged for Knowledge review in this review session.",
                  )
                }
                size="sm"
                type="button"
                variant="outline"
              >
                <FileText aria-hidden="true" />
                Mark Missing Knowledge
              </Button>
              <Button
                disabled={!hasConversation || isPending}
                onClick={() =>
                  recordLocalWorkflowAction(
                    "Human takeover",
                    "Supervisor took ownership of the conversation in this review session.",
                  )
                }
                size="sm"
                type="button"
                variant="outline"
              >
                <UserRound aria-hidden="true" />
                Take Over
              </Button>
              <Button
                disabled={!hasConversation || isPending}
                onClick={() => setActionMessage("Draft is editable in-place before approval.")}
                size="sm"
                type="button"
                variant="outline"
              >
                <PencilLine aria-hidden="true" />
                Edit Draft
              </Button>
              <Button
                disabled={!hasConversation || isPending || Boolean(resolveDisabledReason)}
                onClick={() => void submitResolve()}
                size="sm"
                title={resolveDisabledReason || "Resolve conversation in Chatwoot"}
                type="button"
                variant="outline"
              >
                <CheckCheck aria-hidden="true" />
                Resolve
              </Button>
            </div>
            <Button
              disabled={!hasConversation || isPending}
              onClick={() => void submitDecision(true)}
              size="sm"
              type="button"
            >
              <Send aria-hidden="true" />
              Approve & Send
            </Button>
          </div>
          {actionMessage ? (
            <Alert className="mt-3">
              <AlertDescription className="text-xs">{actionMessage}</AlertDescription>
            </Alert>
          ) : null}
        </div>
      </section>

      <aside className="min-w-0 max-w-full overflow-hidden rounded-md border border-border bg-card xl:col-span-2 2xl:col-span-1 2xl:flex 2xl:h-full 2xl:flex-col">
        <div className="border-b border-border p-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                Evidence
              </div>
              <h2 className="mt-1 text-base font-bold text-foreground">Run Context</h2>
            </div>
            <StatusPill tone="info">{knowledge.length} sources</StatusPill>
          </div>
        </div>

        <div className="flex min-w-0 flex-col 2xl:min-h-0 2xl:flex-1">
          <div className="flex min-w-0 gap-1 overflow-hidden border-b border-border p-2">
            {railTabs.map((tab) => (
              <button
                className={cn(
                  "relative grid size-9 shrink-0 place-items-center rounded-sm border border-transparent text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  activeRailTab === tab.id &&
                    "border-[rgba(0,212,170,0.38)] bg-[rgba(0,212,170,0.13)] text-[var(--accent-text)]",
                )}
                aria-label={tab.label}
                key={tab.id}
                onClick={() => setActiveRailTab(tab.id)}
                title={tab.label}
                type="button"
              >
                <tab.icon aria-hidden="true" className="size-4" />
                {typeof tab.count === "number" ? (
                  <span className="absolute right-0 top-0 grid min-w-4 place-items-center rounded-full border border-border bg-card px-1 font-mono text-[9px] text-muted-foreground">
                    {tab.count}
                  </span>
                ) : null}
              </button>
            ))}
          </div>

          <div className="min-w-0 flex-1 2xl:min-h-0">
            <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2.5">
              <div className="flex min-w-0 items-center gap-2">
                <span className="grid size-8 shrink-0 place-items-center rounded-sm border border-[rgba(0,212,170,0.28)] bg-[rgba(0,212,170,0.1)] text-[var(--accent-text)]">
                  <ActiveRailIcon aria-hidden="true" className="size-4" />
                </span>
                <div className="min-w-0">
                  <div className="truncate text-sm font-bold text-foreground">
                    {activeRail.label}
                  </div>
                  <div className="font-mono text-[10px] uppercase text-muted-foreground">
                    Evidence section
                  </div>
                </div>
              </div>
              {typeof activeRail.count === "number" ? (
                <StatusPill tone="neutral">{activeRail.count}</StatusPill>
              ) : null}
            </div>

        <div className="grid min-w-0 gap-3 overflow-hidden p-3">
          {activeRailTab === "context" ? (
            <>
              <EvidenceCard>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Route aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                    AI run
                  </div>
                  <StatusPill status={currentRisk}>{currentRisk}</StatusPill>
                </div>
                <div className="grid gap-2 text-sm">
                  {[
                    ["Driver", currentDriver],
                    ["Agent", currentAgent],
                    ["Skill", currentSkill],
                    ["Graph", currentGraph],
                    ["Approval", textOf(primary, ["hitlStatus", "approvalStatus"], "Needs review")],
                    ["Channel", textOf(primary, ["source", "sourceChannel"], "Chatwoot")],
                  ].map(([label, value]) => (
                    <div
                      className="grid grid-cols-[78px_minmax(0,1fr)] gap-3 border-b border-border pb-2 last:border-b-0 last:pb-0"
                      key={label}
                    >
                      <div className="font-mono text-[10px] uppercase text-muted-foreground">
                        {label}
                      </div>
                      <div className="min-w-0 truncate font-semibold text-foreground">{value}</div>
                    </div>
                  ))}
                </div>
              </EvidenceCard>
              <EvidenceCard>
                <div className="mb-3 flex items-center gap-2 font-semibold text-foreground">
                  <UserRound aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                  Customer context
                </div>
                <div className="grid gap-2 text-sm">
                  {([
                    ["Name", customerName],
                    ["Inbox", fieldValue(primary, ["inboxName"], "Chatwoot inbox")],
                    ["Can reply", fieldValue(primary, ["canReply"], "Unknown")],
                    ["Unread", fieldValue(primary, ["unreadCount"], "0")],
                    [
                      "Last activity",
                      <LiveAge
                        key="last-activity"
                        iso={fieldValue(primary, ["lastActivityAt", "updatedAt"], "")}
                      />,
                    ],
                  ] as Array<[string, ReactNode]>).map(([label, value]) => (
                    <div className="flex justify-between gap-3" key={label}>
                      <span className="text-muted-foreground">{label}</span>
                      <span className="min-w-0 truncate font-semibold text-foreground">{value}</span>
                    </div>
                  ))}
                </div>
              </EvidenceCard>
            </>
          ) : null}

          {activeRailTab === "memory" ? (
            <>
              {memory.length === 0 ? (
                <EvidenceCard>
                  <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Brain aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                    No memory context
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Conversation memory appears after prior messages, approved replies, or resolution state exist.
                  </p>
                </EvidenceCard>
              ) : null}
              {memory.slice(0, 4).map((item, index) => (
                <EvidenceCard key={textOf(item, ["id"], String(index))}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 truncate font-semibold text-foreground">
                      {textOf(item, ["memoryType", "memory_type"], "Memory")}
                    </div>
                    <SourcePill>{textOf(item, ["source"], "Thread")}</SourcePill>
                  </div>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                    {textOf(item, ["content", "summary", "detail"], "")}
                  </p>
                </EvidenceCard>
              ))}
            </>
          ) : null}

          {activeRailTab === "knowledge" ? (
            <>
              {knowledge.length === 0 ? (
                <div className="text-sm leading-6 text-muted-foreground">
                  No retrieved KB, SOP, QA, or compliance references yet.
                </div>
              ) : null}
              {knowledge.slice(0, 3).map((source, index) => (
                <EvidenceCard key={textOf(source, ["id", "title"], String(index))}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 truncate font-semibold text-foreground">
                      {textOf(source, ["title", "name"], "Source")}
                    </div>
                    <SourcePill>{textOf(source, ["category", "type"], "KB")}</SourcePill>
                  </div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
                    {textOf(source, ["excerpt", "summary", "detail"], "")}
                  </p>
                  <div className="mt-2 truncate font-mono text-[11px] text-muted-foreground">
                    {textOf(source, ["source", "source_path", "path"], "")}
                  </div>
                </EvidenceCard>
              ))}
              {knowledge.length > 3 ? (
                <div className="rounded-md border border-dashed border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                  {knowledge.length - 3} more sources are available in the full run payload.
                </div>
              ) : null}
            </>
          ) : null}

          {activeRailTab === "policy" ? (
            <>
              {policyChecks.length === 0 ? (
                <EvidenceCard>
                  <div className="flex items-center gap-2 font-semibold text-foreground">
                    <ShieldCheck aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                    No tool policy decisions
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Tool plans will show allowed or blocked decisions after Agent Studio evaluates policy.
                  </p>
                </EvidenceCard>
              ) : null}
              {policyChecks.map((check, index) => {
                const status = policyStatus(check);
                const reasons = reasonsFor(check);
                return (
                  <EvidenceCard key={textOf(check, ["id", "name"], String(index))}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0 font-semibold text-foreground">
                        {textOf(check, ["toolName", "tool_name", "name", "label"], "Tool policy")}
                      </div>
                      <StatusPill status={status}>{status}</StatusPill>
                    </div>
                    <div className="mt-2 grid gap-2 text-xs">
                      <div className="grid grid-cols-3 gap-2">
                        <div className="rounded-sm border border-border bg-background p-2">
                          <div className="font-mono text-[10px] uppercase text-muted-foreground">Risk</div>
                          <div className="mt-1 font-semibold text-foreground">{textOf(check, ["riskLevel", "risk_level", "risk"], "Unknown")}</div>
                        </div>
                        <div className="rounded-sm border border-border bg-background p-2">
                          <div className="font-mono text-[10px] uppercase text-muted-foreground">Approval</div>
                          <div className="mt-1 font-semibold text-foreground">{approvalLabel(check)}</div>
                        </div>
                        <div className="rounded-sm border border-border bg-background p-2">
                          <div className="font-mono text-[10px] uppercase text-muted-foreground">Mode</div>
                          <div className="mt-1 font-semibold text-foreground">{runModeLabel(check)}</div>
                        </div>
                      </div>
                      <p className="line-clamp-3 leading-5 text-muted-foreground">
                        {reasons.length > 0
                          ? reasons.join(" ")
                          : textOf(check, ["description", "notes", "detail"], "Tool policy decision recorded for this run.")}
                      </p>
                    </div>
                  </EvidenceCard>
                );
              })}
            </>
          ) : null}

          {activeRailTab === "qa" ? (
            <>
              {qaFindings.length === 0 ? (
                <EvidenceCard>
                  <div className="flex items-center gap-2 font-semibold text-foreground">
                    <ListChecks aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                    No QA findings
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    QA findings remain separate from tool policy and will appear after draft evaluation.
                  </p>
                </EvidenceCard>
              ) : null}
              {qaFindings.map((finding, index) => {
                const status = textOf(finding, ["status", "rating", "result"], "Needs Review");
                return (
                  <EvidenceCard key={textOf(finding, ["id", "name", "label"], String(index))}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-foreground">
                        {textOf(finding, ["name", "label", "criterion"], "QA finding")}
                      </div>
                      <StatusPill status={status}>{status}</StatusPill>
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                      {textOf(finding, ["description", "notes", "detail"], "QA finding recorded for this run.")}
                    </p>
                  </EvidenceCard>
                );
              })}
            </>
          ) : null}

          {activeRailTab === "audit" ? (
            <>
              {trail.length === 0 ? (
                <div className="text-sm leading-6 text-muted-foreground">
                  No graph events yet.
                </div>
              ) : null}
              {trail.slice(0, 4).map((event, index) => {
                const status = textOf(event, ["status", "result"], "Logged");
                return (
                  <EvidenceCard key={`${textOf(event, ["step", "label", "name"], "event")}-${index}`}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-2 font-semibold text-foreground">
                        <Clock3 aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                        <span className="min-w-0 truncate">
                          {textOf(event, ["step", "label", "name"], "Event")}
                        </span>
                      </div>
                      <StatusPill status={status}>{status}</StatusPill>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
                      {textOf(event, ["rationale", "detail", "description"], "")}
                    </p>
                  </EvidenceCard>
                );
              })}
              {trail.length > 4 ? (
                <div className="rounded-md border border-dashed border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                  {trail.length - 4} more audit events are recorded for this run.
                </div>
              ) : null}
            </>
          ) : null}

          {activeRailTab === "trace" ? (
            <>
              <EvidenceCard>
                <div className="mb-3 flex items-center gap-2 font-semibold text-foreground">
                  <Network aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                  Trace
                </div>
                <div className="line-clamp-2 break-all rounded-sm border border-border bg-background p-2 font-mono text-xs text-muted-foreground">
                  {traceId}
                </div>
              </EvidenceCard>
              <EvidenceCard>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 font-semibold text-foreground">
                    <Wrench aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                    Tool plan / result
                  </div>
                  <StatusPill tone={toolEvidence.length > 0 ? "info" : "neutral"}>
                    {toolEvidence.length} rows
                  </StatusPill>
                </div>
                <div className="grid gap-2">
                  {toolEvidence.length === 0 ? (
                    <div className="text-sm leading-6 text-muted-foreground">
                      No tool plan or result has been recorded for this conversation.
                    </div>
                  ) : null}
                  {toolEvidence.slice(0, 3).map((result, index) => (
                    <div
                      className="min-w-0 rounded-sm border border-border bg-background p-2"
                      key={textOf(result, ["id"], String(index))}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 truncate font-semibold text-foreground">
                          {textOf(result, ["toolName", "tool_name", "name"], "Provider action")}
                        </div>
                        <StatusPill status={textOf(result, ["resultStatus", "status", "result"], "Logged")}>
                          {textOf(result, ["resultStatus", "status", "result"], "Logged")}
                        </StatusPill>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2 font-mono text-[10px] uppercase text-muted-foreground">
                        <div className="min-w-0 truncate">Plan {textOf(result, ["planId", "plan_id"], "n/a")}</div>
                        <div className="min-w-0 truncate">Result {textOf(result, ["resultId", "result_id"], "pending")}</div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <SourcePill>{policyStatus(result)}</SourcePill>
                        <SourcePill>{approvalLabel(result)}</SourcePill>
                        <SourcePill>{runModeLabel(result)}</SourcePill>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                        {textOf(result, ["detail", "description"], "No detail recorded.")}
                      </p>
                      {reasonsFor(result).length > 0 ? (
                        <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-muted-foreground">
                          {reasonsFor(result).join(" ")}
                        </p>
                      ) : null}
                    </div>
                  ))}
                  {toolEvidence.length > 3 ? (
                    <div className="rounded-md border border-dashed border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                      {toolEvidence.length - 3} more tool plan/result rows recorded.
                    </div>
                  ) : null}
                </div>
              </EvidenceCard>
              <EvidenceCard>
                <div className="mb-2 flex items-center gap-2 font-semibold text-foreground">
                  <ListChecks aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                  MCP capabilities
                </div>
                <p className="line-clamp-3 text-sm leading-6 text-muted-foreground">
                  {mcpServersUsed.length > 0
                    ? mcpServersUsed.join(", ")
                    : "None used in this run. MCP servers remain server-side and policy-gated."}
                </p>
              </EvidenceCard>
            </>
          ) : null}
        </div>
          </div>
        </div>
      </aside>
    </div>
  );
}
