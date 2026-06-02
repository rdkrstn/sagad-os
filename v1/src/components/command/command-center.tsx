import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Filter,
  MoreHorizontal,
  RadioTower,
  RefreshCw,
  Route,
  ShieldCheck,
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
import { Input } from "@/components/ui/input";
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
              Live Ops Snapshot
            </CardTitle>
            <CardDescription>
              Light-mode control surface for queues, supervision pods, and readiness checks.
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
        <CardContent className="grid gap-3 p-4 lg:grid-cols-[1fr_auto]">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border bg-background p-3">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Users aria-hidden="true" className="size-3.5" />
                Pod coverage
              </div>
              <div className="mt-2 text-xl font-semibold tabular-nums text-foreground">
                {podRows.length}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Supervision groups online</p>
            </div>
            <div className="rounded-lg border bg-background p-3">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <Route aria-hidden="true" className="size-3.5" />
                Active queues
              </div>
              <div className="mt-2 text-xl font-semibold tabular-nums text-foreground">
                {queueRows.length}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Routing lanes under watch</p>
            </div>
            <div className="rounded-lg border bg-background p-3">
              <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <ShieldCheck aria-hidden="true" className="size-3.5" />
                Readiness checks
              </div>
              <div className="mt-2 text-xl font-semibold tabular-nums text-foreground">
                {readyChannels}/{Math.max(channelRows.length, 1)}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Channels reporting usable state</p>
            </div>
          </div>
          <div className="flex items-center gap-2 lg:min-w-80">
            <Input
              aria-label="Search command center"
              className="bg-background"
              placeholder="Search queue, pod, or channel"
              readOnly
            />
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Command center filters"
                className={buttonVariants({ size: "icon", variant: "outline" })}
              >
                <Filter aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Ops filters</DropdownMenuLabel>
                <DropdownMenuItem>Show SLA risk</DropdownMenuItem>
                <DropdownMenuItem>Show approvals</DropdownMenuItem>
                <DropdownMenuItem>Show live channels</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Reset view</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardContent>
      </Card>

      <MetricStrip
        items={[
          {
            label: "Open queue",
            value: numberOf(metrics, ["openQueue", "openItems", "queueCount"]),
            detail: "Needs review or active monitoring",
            icon: Activity,
          },
          {
            label: "SLA risk",
            value: numberOf(metrics, ["slaRisk", "slaBreaches", "atRisk"]),
            detail: "Conversations trending late",
            icon: Clock3,
          },
          {
            label: "Approval load",
            value: numberOf(metrics, ["approvalLoad", "pendingApprovals"]),
            detail: "Drafts waiting on supervisor action",
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
                    label: "AI Confidence",
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
