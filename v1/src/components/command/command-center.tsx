import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  MoreHorizontal,
  RadioTower,
  RefreshCw,
  Route,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
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
  nestedArray,
  numberOf,
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MetricStrip } from "@/components/ui/metric-strip";
import { Progress } from "@/components/ui/progress";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

function percentValue(value: string) {
  const parsed = Number.parseFloat(value.replace("%", ""));
  return Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : 0;
}

export function CommandCenter({
  data,
  supervisorPods,
}: {
  data: unknown;
  supervisorPods: unknown;
}) {
  const dashboard = asRecord(data);
  const metrics = asRecord(dashboard.metrics);
  const pods =
    asArray(supervisorPods).length > 0
      ? asArray(supervisorPods)
      : nestedArray(dashboard, ["supervisorPods", "pods"]);
  const attentionItems = nestedArray(dashboard, [
    "attentionSummary",
    "attentionItems",
    "queueItems",
  ]);
  const queueHealth = nestedArray(dashboard, ["queueHealth", "activeQueues"]);
  const channelHealth = nestedArray(dashboard, ["channelHealth"]);
  const podRows = asArray(pods).map(asRecord);
  const attentionRows = asArray(attentionItems).map(asRecord);
  const queueRows = asArray(queueHealth).map(asRecord);
  const channelRows = asArray(channelHealth).map(asRecord);
  const approvalLoad = numberOf(metrics, ["approvalLoad", "pendingApprovals"]);
  const riskCount = numberOf(metrics, ["slaRisk", "slaBreaches", "atRisk"]);
  const messagesReceived = numberOf(metrics, ["messagesReceived", "totalConversations"]);
  const aiDrafted = numberOf(metrics, ["aiDrafted", "aiDraftedResponses"]);
  const autoSent = numberOf(metrics, ["autoSent", "autoSentResponses"]);
  const needsApproval = numberOf(metrics, ["needsApproval", "approvalRequired"]);
  const escalated = numberOf(metrics, ["escalated"]);
  const rejected = numberOf(metrics, ["rejected"]);
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
  const readyChannels = channelRows.filter((row) =>
    ["ready", "live", "gated", "optional"].some((status) =>
      textOf(row, ["status", "health"], "").toLowerCase().includes(status),
    ),
  ).length;

  return (
    <>
      <PageHeader
        description="Live supervision surface for queue health, AI confidence, approval load, and pod coverage."
        meta={textOf(dashboard, ["lastUpdated", "asOf"], "Adapter pending")}
        title="Command Center"
      />

      <Card className="mb-4 gap-0 overflow-hidden border-border/80 py-0 shadow-xs">
        <CardHeader className="flex flex-col gap-3 border-b px-4 py-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 text-sm">
              <RadioTower aria-hidden="true" className="size-4 text-primary" />
              Today&apos;s AI Ops
            </CardTitle>
            <CardDescription>
              Golden demo loop: messages in, AI drafts, supervisor exceptions, and audit-ready outcomes.
            </CardDescription>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
            <Badge variant={riskCount > 0 ? "destructive" : "secondary"}>
              {riskCount > 0 ? `${riskCount} SLA risks` : "SLA clear"}
            </Badge>
            <Badge variant={approvalLoad > 0 ? "outline" : "secondary"}>
              {approvalLoad} approvals
            </Badge>
            <Button size="sm" variant="outline">
              <RefreshCw aria-hidden="true" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 p-4 xl:grid-cols-[1fr_360px]">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["Messages received", messagesReceived],
              ["AI drafted", aiDrafted],
              ["Auto-sent", autoSent],
              ["Needs approval", needsApproval],
              ["Escalated", escalated],
              ["Rejected", rejected],
            ].map(([label, value]) => (
              <div className="rounded-lg border bg-background p-3" key={label}>
                <div className="text-xs font-medium text-muted-foreground">
                  {label}
                </div>
                <div className="mt-2 text-2xl font-semibold tabular-nums text-foreground">
                  {value}
                </div>
              </div>
            ))}
          </div>
          <div className="rounded-lg border bg-[#F8F6F1] p-4">
            <div className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              Top missing knowledge
            </div>
            <div className="mt-2 text-base font-semibold text-foreground">
              {topIssue}
            </div>
            <div className="mt-4 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              Recommended action
            </div>
            <p className="mt-2 text-sm leading-6 text-foreground">
              {recommendedAction}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Badge className="border-[#D8D3C8]" variant="outline">
                {readyChannels}/{Math.max(channelRows.length, 1)} systems ready
              </Badge>
              <Badge className="border-[#D8D3C8]" variant="outline">
                {podRows.length} AI Ops pod
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      <MetricStrip
        items={[
          {
            label: "Exception queue",
            value: approvalLoad,
            detail: "Needs supervisor approval or recovery",
            icon: Activity,
          },
          {
            label: "SLA risk",
            value: numberOf(metrics, ["slaRisk", "slaBreaches", "atRisk"]),
            detail: "Conversations trending late",
            icon: Clock3,
          },
          {
            label: "Avg trust score",
            value: textOf(metrics, ["averageConfidence"], "n/a"),
            detail: "Average confidence across AI drafts",
            icon: AlertTriangle,
          },
          {
            label: "Pods staffed",
            value: numberOf(metrics, ["podsStaffed", "activePods"]),
            detail: "Supervisor pods currently assigned",
            icon: Users,
          },
        ]}
      />

      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1.15fr]">
        <SectionPanel
          action={
            <Badge variant="secondary">
              {podRows.length} pods
            </Badge>
          }
          title="Supervisor Pods"
          eyebrow="Coverage"
        >
          <DataTable
            columns={[
              {
                key: "pod",
                label: "Pod",
                render: (row: LooseRecord) => (
                  <div>
                    <div className="font-medium text-foreground">
                      {textOf(row, ["name", "pod", "label"])}
                    </div>
                    <div className="text-muted-foreground">
                      {textOf(row, ["lead", "supervisor"], "No lead")}
                    </div>
                  </div>
                ),
              },
              {
                key: "load",
                label: "Load",
                render: (row: LooseRecord) =>
                  numberOf(row, ["load", "active", "open"]).toString(),
              },
              {
                key: "status",
                label: "Status",
                render: (row: LooseRecord) => {
                  const status = textOf(row, ["status", "health"], "Pending");
                  return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
                },
              },
            ]}
            rows={podRows}
          />
        </SectionPanel>

        <SectionPanel
          action={
            <Badge variant={approvalLoad > 0 ? "outline" : "secondary"}>
              {approvalLoad} open
            </Badge>
          }
          title="Attention Summary"
          eyebrow="Exceptions"
        >
          <DataTable
            columns={[
              {
                key: "type",
                label: "Type",
                render: (row: LooseRecord) => (
                  <span className="font-medium text-foreground">
                    {textOf(row, ["type", "reason", "category"])}
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
                  textOf(row, ["owner", "team", "pod"], "Ops"),
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
            rows={attentionRows}
          />
        </SectionPanel>
      </div>

      <div className="mt-4">
        <Tabs defaultValue="queues">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <TabsList>
              <TabsTrigger value="queues">
                <Route aria-hidden="true" />
                Queue health
              </TabsTrigger>
              <TabsTrigger value="readiness">
                <CheckCircle2 aria-hidden="true" />
                Readiness
              </TabsTrigger>
            </TabsList>
            <DropdownMenu>
              <DropdownMenuTrigger
                className={buttonVariants({ size: "sm", variant: "outline" })}
              >
                <MoreHorizontal aria-hidden="true" />
                Actions
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Command actions</DropdownMenuLabel>
                <DropdownMenuItem>Export queue view</DropdownMenuItem>
                <DropdownMenuItem>Open staffing plan</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Copy status summary</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          <TabsContent value="queues">
            <SectionPanel title="Active Queue Health" eyebrow="Routing">
              <DataTable
                columns={[
                  {
                    key: "queue",
                    label: "Queue",
                    render: (row: LooseRecord) => (
                      <div className="font-medium text-foreground">
                        {textOf(row, ["queue", "name", "lane"])}
                      </div>
                    ),
                  },
                  {
                    key: "backlog",
                    label: "Backlog",
                    className: "text-right tabular-nums",
                    render: (row: LooseRecord) =>
                      numberOf(row, ["backlog", "open", "count"]).toString(),
                  },
                  {
                    key: "oldest",
                    label: "Oldest",
                    render: (row: LooseRecord) =>
                      textOf(row, ["oldestAge", "oldest", "age"], "0m"),
                  },
                  {
                    key: "confidence",
                    label: "Trust Score",
                    render: (row: LooseRecord) => {
                      const confidence = textOf(row, ["confidence", "avgConfidence"], "n/a");
                      return (
                        <div className="min-w-28">
                          <div className="mb-1 text-xs font-medium tabular-nums text-foreground">
                            {confidence}
                          </div>
                          <Progress value={percentValue(confidence)} />
                        </div>
                      );
                    },
                  },
                  {
                    key: "health",
                    label: "Health",
                    render: (row: LooseRecord) => {
                      const status = textOf(row, ["health", "status"], "Pending");
                      return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
                    },
                  },
                ]}
                rows={queueRows}
              />
            </SectionPanel>
          </TabsContent>

          <TabsContent value="readiness">
            <SectionPanel title="Channel + Knowledge Health" eyebrow="Preview readiness">
              <DataTable
                columns={[
                  {
                    key: "channel",
                    label: "Surface",
                    render: (row: LooseRecord) => (
                      <div className="font-medium text-foreground">
                        {textOf(row, ["channel", "name"])}
                      </div>
                    ),
                  },
                  {
                    key: "status",
                    label: "Status",
                    render: (row: LooseRecord) => {
                      const status = textOf(row, ["status", "health"], "Pending");
                      return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
                    },
                  },
                  {
                    key: "volume",
                    label: "Items",
                    className: "text-right tabular-nums",
                    render: (row: LooseRecord) =>
                      numberOf(row, ["volume", "count"]).toString(),
                  },
                  {
                    key: "detail",
                    label: "Detail",
                    render: (row: LooseRecord) =>
                      textOf(row, ["detail", "description"], "No detail"),
                  },
                ]}
                rows={channelRows}
              />
            </SectionPanel>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
