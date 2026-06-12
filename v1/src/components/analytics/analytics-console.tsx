import { AlertTriangle, BarChart3, CheckCircle2, Clock3, Send, ShieldCheck, Wrench, XCircle } from "lucide-react";
import { MetricCard, Panel, StatusPill } from "@/components/product/product-ui";
import { asArray, asRecord, nestedArray, numberOf, textOf } from "@/components/ui/data-access";

export function AnalyticsConsole({ data }: { data: unknown }) {
  const dashboard = asRecord(data);
  const metrics = asRecord(dashboard.metrics);
  const conversations = asArray(dashboard.conversations).map(asRecord);
  const attention = nestedArray(dashboard, ["attentionSummary", "attentionItems"]).map(asRecord);
  const scorecardSource = textOf(dashboard, ["scorecardSource", "integrationSource"], "preview");
  const scorecardStatus = textOf(dashboard, ["scorecardStatus"], scorecardSource);

  const reportMetrics = [
    ["Messages received", numberOf(metrics, ["totalConversations", "messagesReceived"]), BarChart3],
    ["AI drafted", numberOf(metrics, ["aiDrafted", "aiDraftedResponses"]), CheckCircle2],
    ["Auto-sent", numberOf(metrics, ["autoSent", "autoSentResponses"]), Send],
    ["Pending approvals", numberOf(metrics, ["needsApproval", "approvalRequired"]), AlertTriangle],
    ["Rejected", numberOf(metrics, ["rejected"]), XCircle],
    ["Escalated", numberOf(metrics, ["escalated"]), ShieldCheck],
    ["Tool blocks", numberOf(metrics, ["toolCallsBlocked", "blockedTools"]), ShieldCheck],
    ["Dry-runs", numberOf(metrics, ["toolDryRuns", "dryRuns"]), Clock3],
    ["Tool failures", numberOf(metrics, ["toolFailures", "sendFailures"]), Wrench],
    ["Provider failures", numberOf(metrics, ["providerFailures", "providerFailureCount"]), AlertTriangle],
  ] as const;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        {reportMetrics.map(([label, value, Icon]) => (
          <MetricCard detail={`Scorecard: ${scorecardStatus}`} icon={Icon} key={label} label={label} value={value} />
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel action={<StatusPill tone="info">{scorecardSource}</StatusPill>} title="Supervisor Load" eyebrow="Exception mix">
          <div className="divide-y divide-border">
            {attention.map((row, index) => (
              <div className="grid gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_80px_140px]" key={index}>
                <div className="font-semibold text-foreground">
                  {textOf(row, ["type", "category", "reason"], "Signal")}
                </div>
                <div className="text-sm text-muted-foreground">{textOf(row, ["count", "total"], "0")}</div>
                <StatusPill status={textOf(row, ["severity", "status"], "Review")}>
                  {textOf(row, ["severity", "status"], "Review")}
                </StatusPill>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Recommended Action" eyebrow="Knowledge gaps">
          <div className="space-y-4 p-4">
            <div className="rounded-lg border border-border bg-surface-2 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Top issue
              </div>
              <div className="mt-2 font-semibold text-foreground">
                {textOf(metrics, ["topIssue"], "No missing knowledge trend detected")}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Next action
              </div>
              <p className="mt-2 text-sm leading-6 text-foreground">
                {textOf(metrics, ["recommendedAction"], "Keep monitoring approval and QA signals.")}
              </p>
            </div>
          </div>
        </Panel>
      </section>

      <Panel action={<StatusPill tone="neutral">{conversations.length} rows</StatusPill>} title="Conversation Outcomes" eyebrow="Audit-ready samples">
        <div className="divide-y divide-border">
          {conversations.map((row, index) => (
            <div className="grid gap-3 px-4 py-3 xl:grid-cols-[minmax(0,1fr)_120px_140px_140px]" key={textOf(row, ["id"], String(index))}>
              <div>
                <div className="font-semibold text-foreground">{textOf(row, ["customerName", "contact", "name"], "Customer")}</div>
                <div className="text-xs text-muted-foreground">{textOf(row, ["driver", "intent"], "Unknown")}</div>
              </div>
              <div className="text-sm text-muted-foreground">{textOf(row, ["confidence", "aiConfidence"], "n/a")}</div>
              <div className="text-sm text-muted-foreground">{textOf(row, ["hitlStatus", "approvalStatus"], "n/a")}</div>
              <StatusPill status={textOf(row, ["queueStatus", "status"], "Review")}>
                {textOf(row, ["queueStatus", "status"], "Review")}
              </StatusPill>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
