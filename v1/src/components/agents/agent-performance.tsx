import {
  BarChart3,
  Gauge,
  MessageSquareText,
  ShieldCheck,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import {
  Card,
  CardAction,
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
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const placeholderPods = [
  "Sales",
  "Support",
  "Technical",
  "Retention",
  "Fraud/Risk",
];

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function average(rows: LooseRecord[], keys: string[]): number {
  const values = rows
    .map((row) => numberOf(row, keys, Number.NaN))
    .filter(Number.isFinite);

  return values.length > 0
    ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
    : 0;
}

export function AgentPerformance({ agents }: { agents: unknown }) {
  const rows = asArray(agents).map(asRecord);
  const handled = rows.reduce(
    (sum, row) => sum + numberOf(row, ["handled", "resolved", "volume"]),
    0,
  );
  const qaAverage = average(rows, ["qaScore", "qualityScore"]);
  const escalations = rows.reduce(
    (sum, row) => sum + numberOf(row, ["escalations", "escalated", "openEscalations"]),
    0,
  );
  const staffedPods = placeholderPods.filter((pod) =>
    rows.some((row) =>
      textOf(row, ["lane", "role", "pod"], "").toLowerCase().includes(pod.toLowerCase()),
    ),
  ).length;
  const podCoverage = clampPercent((staffedPods / placeholderPods.length) * 100);
  const spotlightRows = rows.slice(0, 4);

  return (
    <>
      <PageHeader
        description="Compare agent lanes, supervisor coverage, answer quality, escalation pressure, and throughput."
        title="Agent and Supervisor Performance"
      />

      <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Active agents",
            value: rows.length,
            detail: `${staffedPods} staffed pods`,
            icon: Users,
          },
          {
            label: "Handled volume",
            value: handled,
            detail: "Resolved conversations",
            icon: MessageSquareText,
          },
          {
            label: "QA average",
            value: qaAverage > 0 ? `${qaAverage}%` : "n/a",
            detail: "Score across roster",
            icon: ShieldCheck,
          },
          {
            label: "Escalation load",
            value: escalations,
            detail: "Open or tagged escalations",
            icon: Gauge,
          },
        ].map((metric) => {
          const Icon = metric.icon;

          return (
            <Card className="shadow-xs" key={metric.label}>
              <CardHeader>
                <CardTitle className="text-sm">{metric.label}</CardTitle>
                <CardAction>
                  <span className="flex size-8 items-center justify-center rounded-md border bg-muted/50 text-muted-foreground">
                    <Icon aria-hidden="true" size={16} />
                  </span>
                </CardAction>
                <CardDescription>{metric.detail}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-semibold tabular-nums text-foreground">
                  {metric.value}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Tabs className="gap-4" defaultValue="roster">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            <TabsTrigger value="roster">Roster</TabsTrigger>
            <TabsTrigger value="coverage">Coverage</TabsTrigger>
          </TabsList>
          <Button size="sm" variant="outline">
            <BarChart3 aria-hidden="true" />
            Export view
          </Button>
        </div>

        <TabsContent value="roster">
          <SectionPanel title="Agent Roster" eyebrow="Performance">
            <DataTable
              columns={[
                {
                  key: "agent",
                  label: "Agent",
                  render: (row: LooseRecord) => (
                    <div>
                      <div className="font-medium text-foreground">
                        {textOf(row, ["name", "agentName", "id"])}
                      </div>
                      <div className="text-muted-foreground">
                        {textOf(row, ["role", "lane", "type"], "Agent")}
                      </div>
                    </div>
                  ),
                },
                {
                  key: "supervisor",
                  label: "Supervisor",
                  render: (row: LooseRecord) =>
                    textOf(row, ["supervisor", "podLead", "owner"], "Unassigned"),
                },
                {
                  key: "handled",
                  label: "Handled",
                  className: "text-right tabular-nums",
                  render: (row: LooseRecord) =>
                    numberOf(row, ["handled", "resolved", "volume"]).toString(),
                },
                {
                  key: "aht",
                  label: "AHT",
                  render: (row: LooseRecord) => textOf(row, ["aht", "avgHandleTime"], "n/a"),
                },
                {
                  key: "qa",
                  label: "QA",
                  render: (row: LooseRecord) => {
                    const score = clampPercent(numberOf(row, ["qaScore", "qualityScore"]));

                    return (
                      <div className="min-w-28">
                        <div className="mb-1 flex justify-between gap-3 text-xs tabular-nums">
                          <span>{score > 0 ? `${score}%` : "n/a"}</span>
                        </div>
                        <Progress value={score} />
                      </div>
                    );
                  },
                },
                {
                  key: "status",
                  label: "Status",
                  render: (row: LooseRecord) => {
                    const status = textOf(row, ["status", "health"], "Placeholder");
                    return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
                  },
                },
              ]}
              rows={rows}
            />
          </SectionPanel>
        </TabsContent>

        <TabsContent value="coverage">
          <div className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
            <SectionPanel title="Pod Coverage" eyebrow="Supervisor map">
              <div className="space-y-4 p-4 pt-0">
                <div>
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="font-medium text-foreground">Coverage readiness</span>
                    <span className="tabular-nums text-muted-foreground">{podCoverage}%</span>
                  </div>
                  <Progress value={podCoverage} />
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {placeholderPods.map((pod) => {
                    const count = rows.filter((row) =>
                      textOf(row, ["lane", "role", "pod"], "")
                        .toLowerCase()
                        .includes(pod.toLowerCase()),
                    ).length;

                    return (
                      <div className="rounded-lg border bg-background p-3" key={pod}>
                        <div className="text-xs font-medium text-muted-foreground">{pod}</div>
                        <div className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                          {count}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </SectionPanel>

            <SectionPanel title="Supervisor Spotlight" eyebrow="Live signals">
              <div className="divide-y">
                {spotlightRows.map((row, index) => {
                  const status = textOf(row, ["status", "health"], "Review");
                  const score = clampPercent(numberOf(row, ["qaScore", "qualityScore"]));

                  return (
                    <div className="p-4" key={index}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="font-medium text-foreground">
                            {textOf(row, ["name", "agentName", "id"])}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {textOf(row, ["supervisor", "podLead", "owner"], "Unassigned")}
                          </div>
                        </div>
                        <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                      </div>
                      <div className="mt-3">
                        <Progress value={score} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </SectionPanel>
          </div>
        </TabsContent>
      </Tabs>
    </>
  );
}
