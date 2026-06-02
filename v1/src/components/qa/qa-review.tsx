import {
  ClipboardCheck,
  ClipboardList,
  FileWarning,
  MessageSquarePlus,
  ShieldAlert,
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

function average(rows: LooseRecord[], keys: string[]): number {
  const values = rows
    .map((row) => numberOf(row, keys, Number.NaN))
    .filter(Number.isFinite);

  return values.length > 0
    ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
    : 0;
}

function rubricName(row: LooseRecord): string {
  return textOf(row, ["rubric", "title", "name"]);
}

export function QaReview({ references }: { references: unknown }) {
  const rows = asArray(references).map(asRecord);
  const avgScore = average(rows, ["score", "adherence", "passRate"]);
  const flags = rows.reduce(
    (sum, row) => sum + numberOf(row, ["flags", "policyFlags"]),
    0,
  );
  const mappedSops = rows.filter(
    (row) => textOf(row, ["sop", "reference", "policy"], "Unmapped") !== "Unmapped",
  ).length;
  const sopCoverage = rows.length ? clampPercent((mappedSops / rows.length) * 100) : 0;
  const reviewQueue = rows.filter((row) =>
    textOf(row, ["status", "health"], "Review").toLowerCase().includes("review"),
  ).length;

  return (
    <>
      <PageHeader
        description="Rubric adherence, coaching notes, policy flags, and SOP coverage for reviewed conversations."
        title="QA/SOP Review"
      />

      <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Average adherence",
            value: avgScore > 0 ? `${avgScore}%` : "n/a",
            detail: "Rubric score",
            icon: ClipboardCheck,
          },
          {
            label: "Policy flags",
            value: flags,
            detail: "Open QA findings",
            icon: ShieldAlert,
          },
          {
            label: "SOP coverage",
            value: `${sopCoverage}%`,
            detail: `${mappedSops} mapped references`,
            icon: ClipboardList,
          },
          {
            label: "Review queue",
            value: reviewQueue,
            detail: "Awaiting supervisor action",
            icon: FileWarning,
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

      <Tabs className="gap-4" defaultValue="rubrics">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            <TabsTrigger value="rubrics">Rubrics</TabsTrigger>
            <TabsTrigger value="coaching">Coaching</TabsTrigger>
          </TabsList>
          <Button size="sm" variant="outline">
            <MessageSquarePlus aria-hidden="true" />
            Add note
          </Button>
        </div>

        <TabsContent value="rubrics">
          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <SectionPanel title="Rubric Adherence" eyebrow="QA">
              <DataTable
                columns={[
                  {
                    key: "rubric",
                    label: "Rubric",
                    render: (row: LooseRecord) => (
                      <span className="font-medium text-foreground">{rubricName(row)}</span>
                    ),
                  },
                  {
                    key: "score",
                    label: "Score",
                    render: (row: LooseRecord) => {
                      const score = clampPercent(
                        numberOf(row, ["score", "adherence", "passRate"]),
                      );

                      return (
                        <div className="min-w-28">
                          <div className="mb-1 text-right text-xs tabular-nums">
                            {score > 0 ? `${score}%` : "n/a"}
                          </div>
                          <Progress value={score} />
                        </div>
                      );
                    },
                  },
                  {
                    key: "flags",
                    label: "Flags",
                    className: "text-right tabular-nums",
                    render: (row: LooseRecord) =>
                      numberOf(row, ["flags", "policyFlags"]).toString(),
                  },
                  {
                    key: "status",
                    label: "Status",
                    render: (row: LooseRecord) => {
                      const status = textOf(row, ["status", "health"], "Review");
                      return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
                    },
                  },
                ]}
                rows={rows}
              />
            </SectionPanel>

            <SectionPanel title="SOP Coverage" eyebrow="Controls">
              <div className="space-y-4 p-4 pt-0">
                <div>
                  <div className="mb-2 flex items-center justify-between text-sm">
                    <span className="font-medium text-foreground">Mapped references</span>
                    <span className="tabular-nums text-muted-foreground">{sopCoverage}%</span>
                  </div>
                  <Progress value={sopCoverage} />
                </div>
                {rows.slice(0, 5).map((row, index) => (
                  <div className="rounded-lg border bg-background p-3" key={index}>
                    <div className="text-sm font-medium text-foreground">
                      {rubricName(row)}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      SOP: {textOf(row, ["sop", "reference", "policy"], "Unmapped")}
                    </div>
                  </div>
                ))}
              </div>
            </SectionPanel>
          </div>
        </TabsContent>

        <TabsContent value="coaching">
          <SectionPanel title="Coaching Notes" eyebrow="Supervisor follow-up">
            <div className="divide-y">
              {rows.map((row, index) => {
                const status = textOf(row, ["status", "health"], "Review");

                return (
                  <div className="p-4" key={index}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-foreground">
                          {textOf(row, ["owner", "agent", "team"], "Team")}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          SOP: {textOf(row, ["sop", "reference", "policy"], "Unmapped")}
                        </div>
                      </div>
                      <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-muted-foreground">
                      {textOf(row, ["coachingNote", "note", "recommendation"], "No note yet.")}
                    </p>
                  </div>
                );
              })}
            </div>
          </SectionPanel>
        </TabsContent>
      </Tabs>
    </>
  );
}
