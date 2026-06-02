import {
  AlertTriangle,
  ArrowUpRight,
  Gauge,
  MessageCircle,
  Route,
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

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function percentOf(value: number, total: number): number {
  return total > 0 ? clampPercent((value / total) * 100) : 0;
}

function driverName(row: LooseRecord): string {
  return textOf(row, ["driver", "intent", "name"]);
}

function riskLabel(row: LooseRecord): string {
  return textOf(row, ["risk", "riskLevel"], "Normal");
}

export function DriverAnalytics({ drivers }: { drivers: unknown }) {
  const rows = asArray(drivers).map(asRecord);
  const total = rows.reduce(
    (sum, row) => sum + numberOf(row, ["count", "volume", "contacts"]),
    0,
  );
  const highRisk = rows.filter((row) =>
    ["risk", "high", "urgent", "escalat"].some((term) =>
      riskLabel(row).toLowerCase().includes(term),
    ),
  ).length;
  const avgEscalation = rows.length
    ? Math.round(
        rows.reduce(
          (sum, row) => sum + numberOf(row, ["escalationPercent", "escalationRate"]),
          0,
        ) / rows.length,
      )
    : 0;
  const topDriver = rows.reduce<LooseRecord | undefined>((current, row) => {
    if (!current) {
      return row;
    }

    return numberOf(row, ["count", "volume", "contacts"]) >
      numberOf(current, ["count", "volume", "contacts"])
      ? row
      : current;
  }, undefined);
  const topShare = topDriver
    ? percentOf(numberOf(topDriver, ["count", "volume", "contacts"]), total)
    : 0;

  return (
    <>
      <PageHeader
        description="Workstream demand, channel mix, connected systems, and cost signals by contact driver."
        title="Contact Drivers"
      />

      <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Total contacts",
            value: total,
            detail: `${rows.length} tracked drivers`,
            icon: MessageCircle,
          },
          {
            label: "Top driver",
            value: topDriver ? `${topShare}%` : "n/a",
            detail: topDriver ? driverName(topDriver) : "No driver data",
            icon: Route,
          },
          {
            label: "High-risk drivers",
            value: highRisk,
            detail: "Need supervisor review",
            icon: AlertTriangle,
          },
          {
            label: "Avg escalation",
            value: `${avgEscalation}%`,
            detail: "Across driver mix",
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

      <Tabs className="gap-4" defaultValue="distribution">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            <TabsTrigger value="distribution">Distribution</TabsTrigger>
            <TabsTrigger value="signals">Signals</TabsTrigger>
          </TabsList>
          <Button size="sm" variant="outline">
            <ArrowUpRight aria-hidden="true" />
            Open triage
          </Button>
        </div>

        <TabsContent value="distribution">
          <SectionPanel title="Driver Distribution" eyebrow="Demand">
            <DataTable
              columns={[
                {
                  key: "driver",
                  label: "Driver",
                  render: (row: LooseRecord) => (
                      <span className="font-medium text-foreground">{driverName(row)}</span>
                  ),
                },
                {
                  key: "workstream",
                  label: "Workstream",
                  render: (row: LooseRecord) =>
                    textOf(row, ["workstream", "team"], "Operations"),
                },
                {
                  key: "platform",
                  label: "Platform",
                  render: (row: LooseRecord) => (
                    <StatusChip>{textOf(row, ["platform", "channel"], "Sagad OS")}</StatusChip>
                  ),
                },
                {
                  key: "integration",
                  label: "Integration",
                  render: (row: LooseRecord) =>
                    textOf(row, ["integration", "provider"], "Adapter"),
                },
                {
                  key: "volume",
                  label: "Volume",
                  className: "text-right tabular-nums",
                  render: (row: LooseRecord) =>
                    numberOf(row, ["count", "volume", "contacts"]).toString(),
                },
                {
                  key: "aht",
                  label: "AHT",
                  render: (row: LooseRecord) => textOf(row, ["aht", "avgHandleTime"], "n/a"),
                },
                {
                  key: "csat",
                  label: "CSAT",
                  render: (row: LooseRecord) => textOf(row, ["csat"], "n/a"),
                },
                {
                  key: "qaScore",
                  label: "QA",
                  render: (row: LooseRecord) => textOf(row, ["qaScore", "qualityScore"], "n/a"),
                },
                {
                  key: "fcr",
                  label: "FCR",
                  render: (row: LooseRecord) => textOf(row, ["fcr"], "n/a"),
                },
                {
                  key: "costInteraction",
                  label: "$ / Interaction",
                  render: (row: LooseRecord) =>
                    textOf(row, ["costInteraction", "costPerInteraction"], "$0.00"),
                },
              ]}
              rows={rows}
            />
          </SectionPanel>
        </TabsContent>

        <TabsContent value="signals">
          <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
            <SectionPanel title="Escalation Patterns" eyebrow="Signals">
              <div className="divide-y">
                {rows.map((row, index) => {
                  const escalation = clampPercent(
                    numberOf(row, ["escalationPercent", "escalationRate"]),
                  );
                  const status = riskLabel(row);

                  return (
                    <div className="p-4" key={index}>
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-sm font-medium text-foreground">
                          {driverName(row)}
                        </div>
                        <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                      </div>
                      <div className="mt-3">
                        <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                          <span>Escalation pressure</span>
                          <span className="tabular-nums">{escalation}%</span>
                        </div>
                        <Progress value={escalation} />
                      </div>
                      <p className="mt-2 text-xs leading-5 text-muted-foreground">
                        {textOf(row, ["pattern", "note", "summary"], "No pattern note yet.")}
                      </p>
                    </div>
                  );
                })}
              </div>
            </SectionPanel>

            <SectionPanel title="Demand Concentration" eyebrow="Mix">
              <div className="space-y-4 p-4 pt-0">
                {rows.slice(0, 5).map((row, index) => {
                  const volume = numberOf(row, ["count", "volume", "contacts"]);
                  const share = percentOf(volume, total);

                  return (
                    <div key={index}>
                      <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                        <span className="truncate font-medium text-foreground">
                          {driverName(row)}
                        </span>
                        <span className="tabular-nums text-muted-foreground">{share}%</span>
                      </div>
                      <Progress value={share} />
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
