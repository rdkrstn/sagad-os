import { AlertTriangle, CheckCircle2, FileQuestion, Send, ShieldCheck } from "lucide-react";
import Link from "next/link";
import {
  ConfidenceScore,
  MetricCard,
  Panel,
  SourcePill,
  StatusPill,
} from "@/components/product/product-ui";
import { Button } from "@/components/ui/button";
import {
  asArray,
  asRecord,
  textOf,
} from "@/components/ui/data-access";

function confidenceValue(row: Record<string, unknown>) {
  const parsed = Number.parseFloat(textOf(row, ["confidence", "aiConfidence"], "0").replace("%", ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function approvalState(row: Record<string, unknown>) {
  const status = textOf(row, ["queueStatus", "hitlStatus", "status"], "Pending approval").toLowerCase();
  const sendStatus = textOf(row, ["sendStatus"], "").toLowerCase();
  const summary = textOf(row, ["reason", "queueReason", "summary"], "").toLowerCase();

  if (status.includes("missing") || summary.includes("missing knowledge")) return "Missing knowledge";
  if (status.includes("reject")) return "Rejected";
  if (status.includes("escal")) return "Escalated";
  if (sendStatus === "sent" || (sendStatus.includes("sent") && !sendStatus.includes("not"))) return "Sent";
  if (confidenceValue(row) >= 88 && !status.includes("approval")) return "Auto-send eligible";
  return "Pending approval";
}

export function ApprovalQueueConsole({ conversations }: { conversations: unknown }) {
  const rows = asArray(conversations).map(asRecord);
  const states = rows.map(approvalState);
  const pending = states.filter((state) => state === "Pending approval").length;
  const escalated = states.filter((state) => state === "Escalated").length;
  const missingKnowledge = states.filter((state) => state === "Missing knowledge").length;
  const autoSendEligible = states.filter((state) => state === "Auto-send eligible").length;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard
          detail="Low confidence or policy risk"
          icon={ShieldCheck}
          label="Pending approval"
          value={pending}
        />
        <MetricCard
          detail="Human takeover or manager review"
          icon={AlertTriangle}
          label="Escalated"
          value={escalated}
        />
        <MetricCard
          detail="Blocked before customer delivery"
          icon={FileQuestion}
          label="Missing knowledge"
          value={missingKnowledge}
        />
        <MetricCard
          detail="Ready for approved send"
          icon={Send}
          label="Auto-send eligible"
          value={autoSendEligible}
        />
      </section>

      <Panel
        action={<StatusPill tone="warning">{rows.length} review items</StatusPill>}
        title="Approval Queue"
        eyebrow="Human-supervised AI"
      >
        <div className="divide-y divide-border">
          {rows.map((row, index) => {
            const name = textOf(row, ["customerName", "contact", "name"], "Customer");
            const state = approvalState(row);
            const confidence = confidenceValue(row);
            const conversationId = textOf(row, ["id"], "");

            return (
              <div
                className="grid gap-4 px-4 py-4 xl:grid-cols-[minmax(0,1fr)_220px_360px]"
                key={textOf(row, ["id"], String(index))}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="font-semibold text-foreground">{name}</div>
                    <StatusPill status={state}>{state}</StatusPill>
                    <SourcePill>{textOf(row, ["source", "sourceChannel"], "Chatwoot")}</SourcePill>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {textOf(row, ["reason", "queueReason", "summary"], "Supervisor review required.")}
                  </p>
                  <div className="mt-3 rounded-lg border border-border bg-surface-2 p-3 text-sm leading-6 text-foreground">
                    {textOf(row, ["draftReply", "suggestedReply"], "No draft generated yet.")}
                  </div>
                </div>

                <div className="grid content-start gap-3">
                  <ConfidenceScore
                    label="Trust score"
                    value={confidence}
                  />
                  <div className="grid gap-1 text-xs text-muted-foreground">
                    <div>Agent: {textOf(row, ["assignedTo"], "Support Agent")}</div>
                    <div>Send: {textOf(row, ["sendStatus"], "Not sent")}</div>
                    <div>Age: {textOf(row, ["age", "waitTime"], "n/a")}</div>
                  </div>
                </div>

                <div className="grid content-start gap-3">
                  <Button asChild>
                    <Link href={`/conversations?conversationId=${encodeURIComponent(conversationId)}`}>
                      Open Review
                    </Link>
                  </Button>
                  <div className="grid grid-cols-2 gap-2">
                    {["Approve & Send", "Reject", "Escalate", "Mark Missing Knowledge"].map((action) => (
                      <StatusPill className="justify-center" key={action} status={action}>
                        {action}
                      </StatusPill>
                    ))}
                  </div>
                  <div className="flex items-start gap-2 rounded-lg border border-border bg-surface-2 p-3 text-xs leading-5 text-muted-foreground">
                    <CheckCircle2 aria-hidden="true" className="mt-0.5 size-4 text-[var(--accent-text)]" />
                    Live writes continue through the conversation review endpoint.
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>

      <section className="grid gap-3 md:grid-cols-5">
        {[
          "Pending approval",
          "Auto-send eligible",
          "Sent",
          "Escalated",
          "Rejected",
          "Missing knowledge",
        ].map((state) => (
          <div className="rounded-lg border border-border bg-card p-3" key={state}>
            <StatusPill status={state}>{state}</StatusPill>
            <div className="mt-2 text-xs leading-5 text-muted-foreground">
              Visible state in the approval loop.
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
