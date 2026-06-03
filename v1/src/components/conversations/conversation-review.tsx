"use client";

import { useMemo, useState, useTransition } from "react";
import { Check, Hand, Pencil, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import {
  asArray,
  asRecord,
  nestedArray,
  textOf,
} from "@/components/ui/data-access";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Textarea } from "@/components/ui/textarea";

function ActionButton({
  icon: Icon,
  label,
  disabled = false,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <Button
      disabled={disabled}
      onClick={onClick}
      size="sm"
      type="button"
      variant="outline"
    >
      <Icon aria-hidden="true" size={14} />
      {label}
    </Button>
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
  const [draftByConversation, setDraftByConversation] = useState<Record<string, string>>(
    {},
  );
  const [actionByConversation, setActionByConversation] = useState<
    Record<string, string>
  >({});
  const draftReply = draftByConversation[primaryId] ?? primaryDraft;
  const actionMessage = actionByConversation[primaryId] ?? "";
  const messages = nestedArray(primary, ["messages", "thread", "conversation"]);
  const trail = nestedArray(primary, ["decisionTrail", "aiDecisionTrail", "events"]);
  const crm = asRecord(primary.crmContext ?? primary.customerContext);
  const crmNotes = asArray(crm.notes).map((item) =>
    typeof item === "string" ? item : textOf(asRecord(item), ["title", "body", "note"], ""),
  );
  const crmTasks = asArray(crm.tasks).map((item) =>
    typeof item === "string" ? item : textOf(asRecord(item), ["title", "name"], ""),
  );
  const crmHistory = asArray(crm.serviceHistory).map((item) =>
    typeof item === "string" ? item : textOf(asRecord(item), ["serviceType", "title"], ""),
  );
  const knowledge = nestedArray(primary, ["knowledgeContext", "retrievedKnowledge"]);
  const qaCompliance = nestedArray(primary, ["qaCompliance", "qaFindings"]);

  function setDraftReply(value: string): void {
    if (!primaryId) {
      return;
    }

    setDraftByConversation((current) => ({
      ...current,
      [primaryId]: value,
    }));
  }

  function setActionMessage(value: string): void {
    setActionByConversation((current) => ({
      ...current,
      [primaryId]: value,
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

      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string };
        setActionMessage(payload.detail ?? "Agent Studio action failed.");
        return;
      }

      setActionMessage(approved ? "Approved. Send status updated." : "Rejected.");
      startTransition(() => router.refresh());
    } catch {
      setActionMessage("Could not reach the approval endpoint.");
    }
  }

  return (
    <>
      <PageHeader
        description="Inspect the thread, AI reasoning trail, CRM context, and approval actions before a reply leaves the console."
        title="Conversation Review"
      />

      <div className="grid gap-4 xl:grid-cols-[280px_1fr_360px]">
        <SectionPanel title="Inbox" eyebrow="Conversations">
          <div className="border-b bg-muted/30 px-3 py-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                {list.length} active
              </span>
              <Badge className="h-6" variant="outline">
                HITL queue
              </Badge>
            </div>
          </div>
          <div className="divide-y">
            {list.length === 0 ? (
              <div className="p-4 text-sm leading-6 text-muted-foreground">
                No conversations yet. Connect Chatwoot to Agent Studio, then inbound
                messages will appear here for review.
              </div>
            ) : null}
            {list.map((conversation, index) => {
              const status = textOf(conversation, ["status", "queueStatus"], "Review");
              const conversationId = textOf(
                conversation,
                ["id", "conversationId", "threadId"],
                "",
              );
              const href = conversationId
                ? `/conversations?conversationId=${encodeURIComponent(conversationId)}`
                : "/conversations";
              const isSelected = conversationId === primaryId;

              return (
                <Link
                  aria-current={isSelected ? "page" : undefined}
                  className="block p-3 transition-colors hover:bg-muted/40 aria-[current=page]:bg-muted/60"
                  href={href}
                  key={conversationId || index}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate text-sm font-medium text-foreground">
                      {textOf(conversation, ["customerName", "contact", "name"])}
                    </div>
                    <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                  </div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {textOf(conversation, ["intent", "summary", "lastMessage"])}
                  </div>
                </Link>
              );
            })}
          </div>
        </SectionPanel>

        <div className="space-y-4">
          <SectionPanel
            action={
              <div className="flex flex-wrap items-center gap-2">
                <ActionButton
                  disabled={!hasConversation || isPending}
                  icon={Check}
                  label="Approve"
                  onClick={() => void submitDecision(true)}
                />
                <ActionButton disabled={!hasConversation} icon={Pencil} label="Edit" />
                <ActionButton
                  disabled={!hasConversation || isPending}
                  icon={X}
                  label="Reject"
                  onClick={() => void submitDecision(false)}
                />
                <ActionButton
                  disabled={!hasConversation}
                  icon={Hand}
                  label="Take over"
                  onClick={() => setActionMessage("Human takeover queued for supervisor.")}
                />
              </div>
            }
            title={
              hasConversation
                ? textOf(primary, ["customerName", "contact", "name"])
                : "No conversation selected"
            }
            eyebrow="Thread"
          >
            <div className="grid grid-cols-2 gap-3 border-b bg-muted/30 p-4 text-xs md:grid-cols-4">
              {[
                ["Intent", textOf(primary, ["intent", "driver"], "Unknown")],
                ["Confidence", textOf(primary, ["confidence", "aiConfidence"], "n/a")],
                ["Risk", textOf(primary, ["severity", "priority"], "Normal")],
                ["Send", textOf(primary, ["sendStatus", "hitlStatus"], "Review")],
              ].map(([label, value]) => (
                <div key={label}>
                  <div className="text-muted-foreground">{label}</div>
                  <div className="mt-1 font-medium text-foreground">{value}</div>
                </div>
              ))}
            </div>
            <ScrollArea className="h-[360px]">
              <div className="space-y-3 p-4">
                {asArray(messages).length === 0 ? (
                  <div className="rounded-md border border-dashed bg-background p-4 text-sm leading-6 text-muted-foreground">
                    No thread loaded yet. New Chatwoot conversations will populate
                    this pane after Agent Studio receives a webhook.
                  </div>
                ) : null}
                {asArray(messages).map((message, index) => {
                  const row = asRecord(message);
                  const sender = textOf(row, ["sender", "role", "from"], "Customer");
                  return (
                    <div
                      className="rounded-md border bg-muted/30 p-3"
                      key={index}
                    >
                      <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                        <span className="font-semibold text-foreground">{sender}</span>
                        <span className="text-muted-foreground">
                          {textOf(row, ["time", "timestamp", "createdAt"], "")}
                        </span>
                      </div>
                      <p className="text-sm leading-6 text-foreground">
                        {textOf(row, ["body", "content", "text", "message"], "")}
                      </p>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          </SectionPanel>

          <SectionPanel title="Draft Reply" eyebrow="AI suggestion">
            <div className="p-4">
              <Textarea
                className="min-h-32 resize-y bg-background text-sm leading-6"
                disabled={!hasConversation}
                onChange={(event) => setDraftReply(event.target.value)}
                placeholder="No draft yet. Agent Studio will generate a supervised draft after a conversation arrives."
                value={draftReply}
              />
              {actionMessage ? (
                <Alert className="mt-3 py-2">
                  <AlertDescription className="text-xs">
                    {actionMessage}
                  </AlertDescription>
                </Alert>
              ) : null}
            </div>
          </SectionPanel>
        </div>

        <div className="space-y-4">
          <SectionPanel title="AI Decision Trail" eyebrow="Reasoning log">
            <div className="divide-y">
              {asArray(trail).length === 0 ? (
                <div className="p-3 text-sm leading-6 text-muted-foreground">
                  No graph events yet.
                </div>
              ) : null}
              {asArray(trail).map((event, index) => {
                const row = asRecord(event);
                const status = textOf(row, ["status", "result"], "Logged");
                return (
                  <div className="p-3" key={index}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-foreground">
                        {textOf(row, ["step", "label", "name"])}
                      </div>
                      <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {textOf(row, ["rationale", "detail", "description"], "")}
                    </p>
                  </div>
                );
              })}
            </div>
          </SectionPanel>

          <SectionPanel title="Knowledge Context" eyebrow="KB/SOP/QA">
            <ScrollArea className="h-[320px]">
              <div className="divide-y">
                {asArray(knowledge).length === 0 ? (
                  <div className="p-3 text-sm leading-6 text-muted-foreground">
                    No retrieved KB, SOP, QA, or compliance references yet.
                  </div>
                ) : null}
                {asArray(knowledge).map((event, index) => {
                  const row = asRecord(event);
                  return (
                    <div className="p-3" key={index}>
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-foreground">
                          {textOf(row, ["title", "name"])}
                        </div>
                        <StatusChip>{textOf(row, ["category", "type"], "KB")}</StatusChip>
                      </div>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        {textOf(row, ["excerpt", "summary", "detail"], "")}
                      </p>
                      <div className="mt-1 text-[11px] text-muted-foreground">
                        {textOf(row, ["source", "source_path", "path"], "")}
                      </div>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          </SectionPanel>

          <SectionPanel title="QA/Compliance Gate" eyebrow="HITL readiness">
            <div className="divide-y">
              {asArray(qaCompliance).length === 0 ? (
                <div className="p-3 text-sm leading-6 text-muted-foreground">
                  No QA or compliance checks yet.
                </div>
              ) : null}
              {asArray(qaCompliance).map((event, index) => {
                const row = asRecord(event);
                const status = textOf(row, ["status", "result"], "Review");
                return (
                  <div className="p-3" key={index}>
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-foreground">
                        {textOf(row, ["label", "name"])}
                      </div>
                      <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      {textOf(row, ["detail", "description"], "")}
                    </p>
                  </div>
                );
              })}
            </div>
          </SectionPanel>

          <SectionPanel title="CRM Context" eyebrow="Twenty external">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 p-4 text-xs">
              {[
                ["Provider", ["provider", "crm"]],
                ["Status", ["providerStatus", "status"]],
                ["Source", ["source", "system"]],
                ["Mode", ["mode", "adapterMode"]],
                ["Lifecycle", ["lifecycle", "stage"]],
                ["Last job", ["lastJob", "lastService"]],
                ["Value", ["customerValue", "ltv"]],
                ["Risk", ["risk", "accountRisk"]],
                ["Owner", ["owner", "assignedRep"]],
                ["Area", ["area", "market"]],
              ].map(([label, keys]) => (
                <div key={label as string}>
                  <dt className="font-medium text-muted-foreground">{label as string}</dt>
                  <dd className="mt-1 text-foreground">
                    {textOf(crm, keys as string[], "n/a")}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="border-t px-4 py-3 text-xs">
              <div className="mb-2 font-medium text-muted-foreground">Recent CRM records</div>
              <div className="grid gap-2">
                {[
                  ["Notes", crmNotes],
                  ["Tasks", crmTasks],
                  ["History", crmHistory],
                ].map(([label, items]) => {
                  const values = (items as string[]).filter(Boolean);
                  return (
                    <div className="rounded-md border bg-background p-2" key={label as string}>
                      <div className="font-medium text-foreground">{label as string}</div>
                      <div className="mt-1 text-muted-foreground">
                        {values.length > 0 ? values.slice(0, 2).join(" | ") : "n/a"}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </SectionPanel>
        </div>
      </div>
    </>
  );
}
