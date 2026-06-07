"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import {
  AlertCircle,
  Bot,
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

type RailTab = "context" | "knowledge" | "policy" | "audit" | "trace";
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
  const toolResults = nestedArray(primary, [
    "toolResults",
    "tool_results",
    "deliveryResults",
  ]).map(asRecord);
  const policyChecks = nestedArray(primary, [
    "policyChecks",
    "qaFindings",
    "qa_findings",
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
  const traceId = textOf(
    primary,
    ["traceId", "langSmithTraceId"],
    primaryId ? `preview-${primaryId}` : "Preview trace",
  );
  const mcpServersUsed = toolResults.some((result) =>
    textOf(result, ["toolName", "tool_name", "name"], "").toLowerCase().includes("mcp"),
  )
    ? ["MCP tool layer"]
    : [];
  const railTabs: RailTabConfig[] = [
    { id: "context", label: "Context", icon: Route },
    { id: "knowledge", label: "Knowledge", count: knowledge.length, icon: FileText },
    { id: "policy", label: "Policy", count: policyChecks.length, icon: ShieldCheck },
    { id: "audit", label: "Audit", count: trail.length, icon: Clock3 },
    { id: "trace", label: "Trace", count: toolResults.length, icon: Network },
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
                      <span>{textOf(message, ["time", "createdAt"], "")}</span>
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
            </div>
            <StatusPill tone={confidence >= 88 ? "good" : "warning"}>
              {confidence}% trust
            </StatusPill>
          </div>
          <Textarea
            aria-label="AI draft reply"
            className="min-h-24 resize-y bg-background text-sm leading-6"
            disabled={!hasConversation || isPending}
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
                  {[
                    ["Name", customerName],
                    ["Inbox", fieldValue(primary, ["inboxName"], "Chatwoot inbox")],
                    ["Can reply", fieldValue(primary, ["canReply"], "Unknown")],
                    ["Unread", fieldValue(primary, ["unreadCount"], "0")],
                    [
                      "Last activity",
                      readableDate(fieldValue(primary, ["lastActivityAt", "updatedAt"], "Unknown")),
                    ],
                  ].map(([label, value]) => (
                    <div className="flex justify-between gap-3" key={label}>
                      <span className="text-muted-foreground">{label}</span>
                      <span className="min-w-0 truncate font-semibold text-foreground">{value}</span>
                    </div>
                  ))}
                </div>
              </EvidenceCard>
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
                    Approval gate active
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    No policy findings were returned. Keep approval gating active for risky sends.
                  </p>
                </EvidenceCard>
              ) : null}
              {policyChecks.map((check, index) => {
                const status = textOf(check, ["status", "rating", "result"], "Needs Review");
                return (
                  <EvidenceCard key={textOf(check, ["id", "name"], String(index))}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-foreground">
                        {textOf(check, ["name", "label", "criterion"], "Policy check")}
                      </div>
                      <StatusPill status={status}>{status}</StatusPill>
                    </div>
                    <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted-foreground">
                      {textOf(check, ["description", "notes", "detail"], "Policy check recorded for this run.")}
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
                    Tool / delivery
                  </div>
                  <StatusPill tone={toolResults.length > 0 ? "info" : "neutral"}>
                    {toolResults.length} results
                  </StatusPill>
                </div>
                <div className="grid gap-2">
                  {toolResults.length === 0 ? (
                    <div className="text-sm leading-6 text-muted-foreground">
                      No provider delivery result has been recorded for this conversation.
                    </div>
                  ) : null}
                  {toolResults.slice(0, 2).map((result, index) => (
                    <div
                      className="min-w-0 rounded-sm border border-border bg-background p-2"
                      key={textOf(result, ["id"], String(index))}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 truncate font-semibold text-foreground">
                          {textOf(result, ["toolName", "tool_name", "name"], "Provider action")}
                        </div>
                        <StatusPill status={textOf(result, ["status", "result"], "Logged")}>
                          {textOf(result, ["status", "result"], "Logged")}
                        </StatusPill>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                        {textOf(result, ["detail", "description"], "No detail recorded.")}
                      </p>
                    </div>
                  ))}
                  {toolResults.length > 2 ? (
                    <div className="rounded-md border border-dashed border-border bg-background px-3 py-2 text-xs text-muted-foreground">
                      {toolResults.length - 2} more tool results recorded.
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
