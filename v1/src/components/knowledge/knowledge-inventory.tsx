import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MetricStrip } from "@/components/ui/metric-strip";
import { SectionPanel } from "@/components/ui/section-panel";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  CheckCircle2,
  Clock3,
  Database,
  FileSearch,
  Filter,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";

const defaultReferenceRows: LooseRecord[] = [
  {
    title: "Buyer qualification FAQ",
    type: "FAQ",
    owner: "Sales Ops",
    updatedAt: "Needs adapter sync",
    status: "Draft",
    summary: "Qualification criteria and objection handling for inbound buyers.",
  },
  {
    title: "Listing verification SOP",
    type: "SOP",
    owner: "Listing Ops",
    updatedAt: "Pending source",
    status: "Review",
    summary: "Required checks before a property answer can be sent.",
  },
  {
    title: "Fallback escalation playbook",
    type: "Playbook",
    owner: "Supervisor",
    updatedAt: "Pending source",
    status: "Queued",
    summary: "Escalation copy and routing rules for uncertain answers.",
  },
];

function hasStatus(row: LooseRecord, terms: string[]) {
  const status = textOf(row, ["status", "health"], "Draft").toLowerCase();
  return terms.some((term) => status.includes(term));
}

export function KnowledgeInventory({ references }: { references: unknown }) {
  const rows = asArray(references).map(asRecord);
  const displayRows = rows.length > 0 ? rows : defaultReferenceRows;
  const readyCount = displayRows.filter((row) =>
    hasStatus(row, ["active", "approved", "healthy", "ok"]),
  ).length;
  const reviewCount = displayRows.filter((row) =>
    hasStatus(row, ["pending", "review", "draft", "queued"]),
  ).length;
  const ownerCount = new Set(
    displayRows.map((row) => textOf(row, ["owner", "team"], "Ops")),
  ).size;

  return (
    <>
      <PageHeader
        description="Inventory of FAQs, process docs, verification scripts, playbooks, and SOP references available to the agents."
        title="KB/SOP Inventory"
      />

      <div className="space-y-4">
        <MetricStrip
          items={[
            {
              label: "References",
              value: displayRows.length,
              detail: "Indexed knowledge objects",
              icon: Database,
            },
            {
              label: "Ready",
              value: readyCount,
              detail: "Approved for agent grounding",
              icon: CheckCircle2,
            },
            {
              label: "Needs review",
              value: reviewCount,
              detail: "Draft, queued, or pending",
              icon: Clock3,
            },
            {
              label: "Owners",
              value: ownerCount,
              detail: "Mapped accountability lanes",
              icon: ShieldCheck,
            },
          ]}
        />

        <Tabs defaultValue="library" className="gap-4">
          <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs lg:flex-row lg:items-center lg:justify-between">
            <TabsList className="w-full sm:w-fit">
              <TabsTrigger value="library">Library</TabsTrigger>
              <TabsTrigger value="coverage">Coverage</TabsTrigger>
              <TabsTrigger value="audit">Audit</TabsTrigger>
            </TabsList>
            <div className="grid gap-2 sm:grid-cols-[minmax(180px,1fr)_160px_160px_auto] lg:min-w-[680px]">
              <div className="relative">
                <FileSearch
                  aria-hidden="true"
                  className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground"
                />
                <Input
                  className="bg-background pl-8"
                  placeholder="Search title, owner, or answer"
                  readOnly
                />
              </div>
              <Select defaultValue="all" disabled>
                <SelectTrigger className="w-full bg-background">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All types</SelectItem>
                  <SelectItem value="faq">FAQ</SelectItem>
                  <SelectItem value="sop">SOP</SelectItem>
                  <SelectItem value="playbook">Playbook</SelectItem>
                </SelectContent>
              </Select>
              <Select defaultValue="all" disabled>
                <SelectTrigger className="w-full bg-background">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All statuses</SelectItem>
                  <SelectItem value="ready">Ready</SelectItem>
                  <SelectItem value="review">Review</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline">
                <Filter aria-hidden="true" />
                Filter
              </Button>
            </div>
          </div>

          <TabsContent value="library" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <SectionPanel title="Reference Library" eyebrow="Knowledge base">
                <DataTable
                  columns={[
                    {
                      key: "title",
                      label: "Title",
                      render: (row: LooseRecord) => (
                        <div className="min-w-[220px]">
                          <div className="font-medium text-foreground">
                            {textOf(row, ["title", "name", "question"])}
                          </div>
                          <div className="line-clamp-2 text-muted-foreground">
                            {textOf(row, ["summary", "description", "answer"], "")}
                          </div>
                        </div>
                      ),
                    },
                    {
                      key: "type",
                      label: "Type",
                      render: (row: LooseRecord) => (
                        <Badge variant="secondary">
                          {textOf(row, ["type", "category"], "Reference")}
                        </Badge>
                      ),
                    },
                    {
                      key: "owner",
                      label: "Owner",
                      render: (row: LooseRecord) =>
                        textOf(row, ["owner", "team"], "Ops"),
                    },
                    {
                      key: "updated",
                      label: "Updated",
                      render: (row: LooseRecord) =>
                        textOf(row, ["updatedAt", "lastUpdated"], "Pending"),
                    },
                    {
                      key: "status",
                      label: "Status",
                      render: (row: LooseRecord) => {
                        const status = textOf(row, ["status", "health"], "Draft");
                        return (
                          <StatusChip tone={toneFromStatus(status)}>
                            {status}
                          </StatusChip>
                        );
                      },
                    },
                  ]}
                  emptyLabel="No knowledge references are connected yet."
                  rows={rows}
                />
              </SectionPanel>

              <SectionPanel title="Selected Payload" eyebrow="Adapter preview">
                <div className="space-y-4 p-4">
                  <div className="space-y-2">
                    <Label htmlFor="knowledge-payload">Grounding payload</Label>
                    <Textarea
                      className="min-h-48 resize-none bg-muted/40 font-mono text-xs"
                      id="knowledge-payload"
                      readOnly
                      value={JSON.stringify(displayRows[0] ?? {}, null, 2)}
                    />
                  </div>
                  <div className="grid gap-2 text-xs text-muted-foreground">
                    <div className="flex items-center justify-between rounded-lg border bg-background px-3 py-2">
                      <span>Embedding sync</span>
                      <StatusChip tone="warning">Pending</StatusChip>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border bg-background px-3 py-2">
                      <span>Source adapter</span>
                      <StatusChip tone={rows.length > 0 ? "good" : "neutral"}>
                        {rows.length > 0 ? "Connected" : "Mocked"}
                      </StatusChip>
                    </div>
                  </div>
                </div>
              </SectionPanel>
            </div>
          </TabsContent>

          <TabsContent value="coverage" className="mt-0">
            <div className="grid gap-4 md:grid-cols-3">
              {["FAQ", "SOP", "Playbook"].map((type) => {
                const count = displayRows.filter(
                  (row) =>
                    textOf(row, ["type", "category"], "Reference").toLowerCase() ===
                    type.toLowerCase(),
                ).length;

                return (
                  <Card className="shadow-xs" key={type}>
                    <CardHeader>
                      <CardTitle>{type}</CardTitle>
                      <CardDescription>
                        Coverage for agent retrieval and supervisor review.
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex items-center justify-between">
                      <span className="text-3xl font-semibold tabular-nums">
                        {count}
                      </span>
                      <StatusChip tone={count > 0 ? "good" : "warning"}>
                        {count > 0 ? "Mapped" : "Gap"}
                      </StatusChip>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </TabsContent>

          <TabsContent value="audit" className="mt-0">
            <SectionPanel title="Readiness Checks" eyebrow="Supervisor controls">
              <div className="grid gap-3 p-4 md:grid-cols-3">
                {[
                  "Source freshness",
                  "Answer citation coverage",
                  "Escalation fallback copy",
                ].map((check) => (
                  <div
                    className="rounded-lg border bg-background p-4"
                    key={check}
                  >
                    <RefreshCcw
                      aria-hidden="true"
                      className="mb-3 size-4 text-muted-foreground"
                    />
                    <div className="font-medium text-foreground">{check}</div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Adapter-backed validation is staged for this control.
                    </p>
                  </div>
                ))}
              </div>
            </SectionPanel>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
