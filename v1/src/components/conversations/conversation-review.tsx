"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  FileText,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Textarea } from "@/components/ui/textarea";
import {
  ApprovalActionBar,
  ConfidenceScore,
  EmptyState,
  Panel,
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
  const traceId = textOf(primary, ["traceId", "langSmithTraceId"], primaryId ? `preview-${primaryId}` : "Preview trace");
  const mcpServersUsed = toolResults.some((result) =>
    textOf(result, ["toolName", "tool_name", "name"], "").toLowerCase().includes("mcp"),
  )
    ? ["MCP tool layer"]
    : [];

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
    <div className="grid gap-4 xl:grid-cols-[400px_minmax(0,1fr)]">
      <Panel
        action={<StatusPill tone="warning">{list.length} active</StatusPill>}
        title="Conversation List"
        eyebrow="Queue"
      >
        <div className="divide-y divide-border">
          {list.length === 0 ? (
            <div className="p-4">
              <EmptyState
                title="No conversations"
                description="Connect Chatwoot through Agent Studio to populate this queue."
              />
            </div>
          ) : null}
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
                  "grid grid-cols-[40px_minmax(0,1fr)_auto] gap-3 px-4 py-3 transition-colors hover:bg-muted",
                  isSelected && "bg-[rgba(0,212,170,0.12)]",
                )}
                href={href}
                key={conversationId || index}
              >
                <div className="grid size-10 place-items-center rounded-full bg-surface-2 text-xs font-bold text-foreground">
                  {initials(name)}
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-foreground">
                    {name}
                  </div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {textOf(conversation, ["lastMessage", "summary", "intent"], "")}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <SourcePill>{textOf(conversation, ["source", "sourceChannel"], "Chatwoot")}</SourcePill>
                    <SourcePill>{selectedAgent(conversation)}</SourcePill>
                  </div>
                </div>
                <div className="grid justify-items-end gap-2">
                  <StatusPill status={status}>{status}</StatusPill>
                  <div className="font-mono text-[11px] text-muted-foreground">
                    {textOf(conversation, ["age", "waitTime"], "")}
                  </div>
                  <div className="text-[11px] font-semibold text-muted-foreground">
                    {confidenceNumber(conversation)}%
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      </Panel>

      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-4">
          <Panel
            action={
              <StatusPill status={currentWorkflowState}>
                {currentWorkflowState}
              </StatusPill>
            }
            title={
              hasConversation
                ? textOf(primary, ["customerName", "contact", "name"], "Conversation")
                : "No conversation selected"
            }
            eyebrow="Conversation Review"
          >
            <div className="grid gap-3 border-b border-border bg-muted/40 p-4 sm:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">Selected agent</div>
                <div className="mt-1 font-semibold text-foreground">{currentAgent}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Approval state</div>
                <div className="mt-1 font-semibold text-foreground">
                  {textOf(primary, ["hitlStatus", "approvalStatus"], "Needs review")}
                </div>
              </div>
              <ConfidenceScore value={confidence} />
            </div>

            <div className="grid gap-3 p-4">
              {messages.length === 0 ? (
                <EmptyState
                  title="No thread loaded"
                  description="A Chatwoot thread will appear here after Agent Studio receives a message."
                />
              ) : null}
              {messages.map((message, index) => {
                const role = textOf(message, ["role", "senderType", "sender"], "Customer");
                const isAi =
                  role.toLowerCase().includes("ai") ||
                  role.toLowerCase().includes("agent");

                return (
                  <div
                    className={cn(
                      "rounded-lg border border-border bg-surface-2 p-4",
                      isAi && "border-[rgba(0,212,170,0.42)] bg-[rgba(0,212,170,0.12)]",
                    )}
                    key={textOf(message, ["id"], String(index))}
                  >
                    <div className="mb-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                      <span className="font-semibold text-foreground">
                        {textOf(message, ["sender", "senderName", "role"], "Customer")}
                      </span>
                      <span>{textOf(message, ["time", "createdAt"], "")}</span>
                    </div>
                    <p className="text-sm leading-6 text-foreground">
                      {textOf(message, ["body", "content", "text", "message"], "")}
                    </p>
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel
            action={<StatusPill tone={confidence >= 88 ? "good" : "warning"}>{confidence}% trust</StatusPill>}
            title="AI Draft"
            eyebrow="Approval gate"
          >
            <div className="space-y-3 p-4">
              <Textarea
                aria-label="AI draft reply"
                className="min-h-36 resize-y bg-card text-sm leading-6"
                disabled={!hasConversation || isPending}
                onChange={(event) => setDraftReply(event.target.value)}
                placeholder="No draft yet. Agent Studio will generate a supervised draft after a conversation arrives."
                value={draftReply}
              />
              <ApprovalActionBar
                disabled={!hasConversation || isPending}
                onApprove={() => void submitDecision(true)}
                onEdit={() => setActionMessage("Draft is editable in-place before approval.")}
                onEscalate={() =>
                  recordLocalWorkflowAction(
                    "Escalated",
                    "Escalation created for supervisor takeover in this review session.",
                  )
                }
                onMissingKnowledge={() =>
                  recordLocalWorkflowAction(
                    "Missing knowledge",
                    "Missing knowledge topic flagged for Knowledge review in this review session.",
                  )
                }
                onTakeOver={() =>
                  recordLocalWorkflowAction(
                    "Human takeover",
                    "Supervisor took ownership of the conversation in this review session.",
                  )
                }
                onReject={() => void submitDecision(false)}
              />
              {actionMessage ? (
                <Alert>
                  <AlertDescription className="text-xs">{actionMessage}</AlertDescription>
                </Alert>
              ) : null}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel
            action={<StatusPill status={currentRisk}>{currentRisk}</StatusPill>}
            title="AI Run"
            eyebrow="Driver -> Agent -> Skill -> Graph"
          >
            <div className="grid gap-3 p-3 text-sm">
              {[
                ["Driver", currentDriver],
                ["Agent", currentAgent],
                ["Skill", currentSkill],
                ["Graph", currentGraph],
                ["Trust", `${confidence}%`],
                ["Trace", traceId],
              ].map(([label, value]) => (
                <div
                  className="grid grid-cols-[84px_minmax(0,1fr)] gap-3 border-b border-border pb-2 last:border-b-0 last:pb-0"
                  key={label}
                >
                  <div className="font-mono text-[10px] uppercase text-muted-foreground">
                    {label}
                  </div>
                  <div className="min-w-0 font-semibold text-foreground">{value}</div>
                </div>
              ))}
              <div className="rounded-sm border border-border bg-surface-2 p-2 text-xs leading-5 text-muted-foreground">
                Approval required when trust is low, policy is unclear, write/send tools are planned, or a human takeover condition is detected.
              </div>
            </div>
          </Panel>

          <Panel
            action={<StatusPill tone="info">{knowledge.length} sources</StatusPill>}
            title="Knowledge Sources"
            eyebrow="RAG / SOP"
          >
            <div className="divide-y divide-border">
              {knowledge.length === 0 ? (
                <div className="p-4 text-sm leading-6 text-muted-foreground">
                  No retrieved KB, SOP, QA, or compliance references yet.
                </div>
              ) : null}
              {knowledge.map((source, index) => (
                <div className="p-4" key={textOf(source, ["id", "title"], String(index))}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="font-semibold text-foreground">
                      {textOf(source, ["title", "name"], "Source")}
                    </div>
                    <SourcePill>{textOf(source, ["category", "type"], "KB")}</SourcePill>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">
                    {textOf(source, ["excerpt", "summary", "detail"], "")}
                  </p>
                  <div className="mt-2 font-mono text-[11px] text-muted-foreground">
                    {textOf(source, ["source", "source_path", "path"], "")}
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel
            action={<StatusPill tone={policyChecks.length > 0 ? "warning" : "neutral"}>{policyChecks.length} checks</StatusPill>}
            title="Policy Checks"
            eyebrow="QA gate"
          >
            <div className="divide-y divide-border">
              {policyChecks.length === 0 ? (
                <div className="p-3 text-sm leading-6 text-muted-foreground">
                  No policy findings were returned. Keep approval gating active for risky sends.
                </div>
              ) : null}
              {policyChecks.map((check, index) => {
                const status = textOf(check, ["status", "rating", "result"], "Needs Review");
                return (
                  <div className="p-3" key={textOf(check, ["id", "name"], String(index))}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-foreground">
                        {textOf(check, ["name", "label", "criterion"], "Policy check")}
                      </div>
                      <StatusPill status={status}>{status}</StatusPill>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {textOf(check, ["description", "notes", "detail"], "Policy check recorded for this run.")}
                    </p>
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel
            action={<StatusPill tone="neutral">{trail.length} events</StatusPill>}
            title="Audit Trail Preview"
            eyebrow="Inspectable"
          >
            <div className="divide-y divide-border">
              {trail.length === 0 ? (
                <div className="p-4 text-sm leading-6 text-muted-foreground">
                  No graph events yet.
                </div>
              ) : null}
              {trail.map((event, index) => {
                const status = textOf(event, ["status", "result"], "Logged");
                return (
                  <div className="p-4" key={index}>
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-foreground">
                        {textOf(event, ["step", "label", "name"], "Event")}
                      </div>
                      <StatusPill status={status}>{status}</StatusPill>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {textOf(event, ["rationale", "detail", "description"], "")}
                    </p>
                  </div>
                );
              })}
            </div>
          </Panel>

          <Panel
            action={<StatusPill tone={toolResults.length > 0 ? "info" : "neutral"}>{toolResults.length} results</StatusPill>}
            title="Tool / Delivery Result"
            eyebrow="Backend"
          >
            <div className="grid gap-3 p-4">
              {toolResults.length === 0 ? (
                <div className="rounded-lg border border-border bg-surface-2 p-4 text-sm leading-6 text-muted-foreground">
                  No provider delivery result has been recorded for this conversation.
                </div>
              ) : null}
              {toolResults.map((result, index) => (
                <div
                  className="rounded-lg border border-border bg-surface-2 p-3"
                  key={textOf(result, ["id"], String(index))}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-foreground">
                      {textOf(result, ["toolName", "tool_name", "name"], "Provider action")}
                    </div>
                    <StatusPill status={textOf(result, ["status", "result"], "Logged")}>
                      {textOf(result, ["status", "result"], "Logged")}
                    </StatusPill>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {textOf(result, ["detail", "description"], "No detail recorded.")}
                  </p>
                </div>
              ))}
            </div>
          </Panel>

          <Panel
            action={<StatusPill tone={mcpServersUsed.length > 0 ? "info" : "neutral"}>{mcpServersUsed.length} used</StatusPill>}
            title="MCP Capabilities"
            eyebrow="External servers"
          >
            <div className="p-3 text-sm leading-6 text-muted-foreground">
              {mcpServersUsed.length > 0
                ? mcpServersUsed.join(", ")
                : "None used in this run. MCP servers are visible in Agent Studio but disabled unless routed server-side."}
            </div>
          </Panel>

          <div className="grid gap-3 sm:grid-cols-3 2xl:grid-cols-1">
            {[
              { label: "Thread", icon: MessageSquareText },
              { label: "Draft", icon: Bot },
              { label: "Sources", icon: FileText },
              { label: "Policy", icon: ShieldCheck },
              { label: "Approval", icon: CheckCircle2 },
              { label: "Risk", icon: AlertCircle },
            ].map(({ label, icon: Icon }) => (
              <div
                className="flex items-center gap-2 rounded-lg border border-border bg-card p-3 text-xs text-muted-foreground"
                key={label}
              >
                <Icon aria-hidden="true" className="size-4 text-[var(--accent-text)]" />
                {label}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
