import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Gauge,
  MessageSquareText,
  Send,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import {
  asArray,
  asRecord,
  numberOf,
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";

export function AiOpsReports({ data }: { data: unknown }) {
  const dashboard = asRecord(data);
  const metrics = asRecord(dashboard.metrics);
  const conversations = asArray(dashboard.conversations).map(asRecord);
  const attention = asArray(
    dashboard.attentionSummary ?? dashboard.attentionItems,
  ).map(asRecord);
  const scorecardSource = textOf(dashboard, ["scorecardSource", "integrationSource"], "preview");
  const scorecardStatus = textOf(dashboard, ["scorecardStatus"], scorecardSource);
  const topIssue = textOf(
    metrics,
    ["topIssue"],
    "No missing knowledge trend detected",
  );
  const recommendedAction = textOf(
    metrics,
    ["recommendedAction"],
    "Keep monitoring approval and QA signals.",
  );

  return (
    <>
      <PageHeader
        description="Basic AI Ops reporting for automation, approvals, rejections, escalations, trust score, and missing knowledge."
        meta={`${textOf(dashboard, ["lastUpdated", "asOf"], "Demo data")} - ${scorecardStatus}`}
        title="Reports"
      />

      <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Total conversations",
            value: numberOf(metrics, ["totalConversations", "messagesReceived"]),
            detail: "Messages received today",
            icon: MessageSquareText,
          },
          {
            label: "AI drafted",
            value: numberOf(metrics, ["aiDrafted", "aiDraftedResponses"]),
            detail: "Responses prepared by agents",
            icon: BarChart3,
          },
          {
            label: "Auto-sent",
            value: numberOf(metrics, ["autoSent", "autoSentResponses"]),
            detail: "High-trust replies sent without review",
            icon: Send,
          },
          {
            label: "Needs approval",
            value: numberOf(metrics, ["needsApproval", "approvalRequired"]),
            detail: "Supervisor queue volume",
            icon: AlertTriangle,
          },
          {
            label: "Approved",
            value: numberOf(metrics, ["approved"]),
            detail: "Supervisor accepted",
            icon: CheckCircle2,
          },
          {
            label: "Rejected",
            value: numberOf(metrics, ["rejected"]),
            detail: "Blocked before customer send",
            icon: XCircle,
          },
          {
            label: "Escalated",
            value: numberOf(metrics, ["escalated"]),
            detail: "Human takeover or manager review",
            icon: ShieldCheck,
          },
          {
            label: "Avg trust score",
            value: textOf(metrics, ["averageConfidence"], "n/a"),
            detail: "Average across AI drafts",
            icon: Gauge,
          },
          {
            label: "Tool blocks",
            value: numberOf(metrics, ["toolCallsBlocked", "blockedTools"]),
            detail: "Policy-blocked tool calls",
            icon: ShieldCheck,
          },
          {
            label: "Dry-runs",
            value: numberOf(metrics, ["toolDryRuns", "dryRuns"]),
            detail: "Provider-safe executions",
            icon: Clock3,
          },
          {
            label: "Provider failures",
            value: numberOf(metrics, ["providerFailures", "providerFailureCount"]),
            detail: "Visible failure categories",
            icon: Wrench,
          },
        ].map((metric) => {
          const Icon = metric.icon;

          return (
            <Card className="shadow-xs" key={metric.label}>
              <CardHeader>
                <CardTitle className="text-sm">{metric.label}</CardTitle>
                <CardDescription>{metric.detail}</CardDescription>
              </CardHeader>
              <CardContent className="flex items-end justify-between gap-3">
                <div className="text-2xl font-semibold tabular-nums text-foreground">
                  {metric.value}
                </div>
                <span className="flex size-9 items-center justify-center rounded-md border bg-muted/50 text-muted-foreground">
                  <Icon aria-hidden="true" size={16} />
                </span>
              </CardContent>
            </Card>
          );
        })}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionPanel
          action={<Badge variant="outline">{scorecardSource}</Badge>}
          eyebrow="Exception mix"
          title="Supervisor Load"
        >
          <DataTable
            columns={[
              {
                key: "type",
                label: "Signal",
                render: (row: LooseRecord) => (
                  <span className="font-medium text-foreground">
                    {textOf(row, ["type", "category", "reason"])}
                  </span>
                ),
              },
              {
                key: "count",
                label: "Count",
                className: "text-right tabular-nums",
                render: (row: LooseRecord) =>
                  numberOf(row, ["count", "total", "items"]).toString(),
              },
              {
                key: "owner",
                label: "Owner",
                render: (row: LooseRecord) =>
                  textOf(row, ["owner", "team", "pod"], "AI Ops"),
              },
              {
                key: "severity",
                label: "Severity",
                render: (row: LooseRecord) => {
                  const status = textOf(row, ["severity", "status"], "Review");
                  return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
                },
              },
            ]}
            rows={attention}
          />
        </SectionPanel>
        <SectionPanel eyebrow="Knowledge gaps" title="Recommended Action">
          <div className="space-y-4 p-4">
            <div className="rounded-lg border bg-[#F8F6F1] p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Top issue
              </div>
              <div className="mt-2 text-base font-semibold text-foreground">
                {topIssue}
              </div>
            </div>
            <div className="rounded-lg border bg-background p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                Next action
              </div>
              <p className="mt-2 text-sm leading-6 text-foreground">
                {recommendedAction}
              </p>
            </div>
          </div>
        </SectionPanel>
      </div>

      <div className="mt-4">
        <SectionPanel
          action={<Badge variant="secondary">{conversations.length} demo threads</Badge>}
          eyebrow="Audit-ready samples"
          title="Conversation Outcomes"
        >
          <DataTable
            columns={[
              {
                key: "customer",
                label: "Customer",
                render: (row: LooseRecord) => (
                  <div>
                    <div className="font-medium text-foreground">
                      {textOf(row, ["customerName", "contact", "name"])}
                    </div>
                    <div className="text-muted-foreground">
                      {textOf(row, ["driver", "intent"], "Unknown")}
                    </div>
                  </div>
                ),
              },
              {
                key: "trust",
                label: "Trust Score",
                render: (row: LooseRecord) =>
                  textOf(row, ["confidence", "aiConfidence"], "n/a"),
              },
              {
                key: "approval",
                label: "Approval",
                render: (row: LooseRecord) =>
                  textOf(row, ["hitlStatus", "approvalStatus"], "n/a"),
              },
              {
                key: "send",
                label: "Send",
                render: (row: LooseRecord) =>
                  textOf(row, ["sendStatus"], "n/a"),
              },
              {
                key: "status",
                label: "Status",
                render: (row: LooseRecord) => {
                  const status = textOf(row, ["status", "queueStatus"], "Review");
                  return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
                },
              },
            ]}
            rows={conversations}
          />
        </SectionPanel>
      </div>
    </>
  );
}
