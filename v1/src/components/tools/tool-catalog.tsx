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
import { Progress } from "@/components/ui/progress";
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
  Cable,
  CheckCircle2,
  Code2,
  DatabaseZap,
  Filter,
  MessageSquareText,
  PlugZap,
  Search,
  ServerCog,
  ShieldAlert,
  Webhook,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const defaultToolRows: LooseRecord[] = [
  {
    name: "crm.lookup_contact",
    system: "Twenty CRM",
    owner: "Revenue Ops",
    providerStatus: "Twenty external",
    health: "Dry-run",
    description: "Retrieve CRM identity, lead stage, and routing metadata through Agent Studio.",
    samplePayload: '{\n  "query": "Avery Hill",\n  "provider": "twenty"\n}',
  },
  {
    name: "chatwoot.messages.send_approved",
    system: "Chatwoot",
    owner: "Support Ops",
    providerStatus: "External channel",
    health: "HITL only",
    description: "Send a supervisor-approved reply back to Chatwoot.",
    samplePayload: '{\n  "conversation_id": "42",\n  "approved": true\n}',
  },
  {
    name: "knowledge.retrieve_context",
    system: "Markdown Knowledge Packs",
    owner: "QA Ops",
    providerStatus: "Local source",
    health: "Ready",
    description: "Retrieve KB/SOP/QA/compliance context for a conversation.",
    samplePayload: '{\n  "intent": "pricing_lead",\n  "risk_level": "low"\n}',
  },
];

const providerCards: {
  name: string;
  role: string;
  status: string;
  detail: string;
  icon: LucideIcon;
}[] = [
  {
    name: "Chatwoot",
    role: "Channel adapter",
    status: "Ready",
    detail: "Inbound webhook and HITL approved-send path.",
    icon: MessageSquareText,
  },
  {
    name: "Twenty CRM",
    role: "External CRM",
    status: "External / dry-run",
    detail: "Hosted separately on your VPS; credentials stay in Agent Studio.",
    icon: DatabaseZap,
  },
  {
    name: "Markdown Knowledge Packs",
    role: "Context source",
    status: "Ready",
    detail: "KB, SOP, QA, compliance, escalation, and template records.",
    icon: CheckCircle2,
  },
  {
    name: "LangSmith",
    role: "Observability",
    status: "Optional",
    detail: "Trace metadata when environment variables are configured.",
    icon: Cable,
  },
  {
    name: "Generic Webhooks",
    role: "Connector primitive",
    status: "Planned",
    detail: "Provider-neutral inbound and outbound webhooks governed by Agent Studio.",
    icon: Webhook,
  },
  {
    name: "Future MCP",
    role: "Tool facade",
    status: "Planned",
    detail: "Provider-neutral tools behind Agent Studio policy gates.",
    icon: ServerCog,
  },
];

const readinessChecks: {
  label: string;
  icon: LucideIcon;
  status: string;
}[] = [
  { label: "MCP server manifest", icon: Cable, status: "Planned" },
  { label: "Twenty external CRM gates", icon: DatabaseZap, status: "Dry-run" },
  { label: "Approval-safe send path", icon: CheckCircle2, status: "Review" },
  { label: "Tool error envelopes", icon: ShieldAlert, status: "Pending" },
];

function matchesStatus(row: LooseRecord, terms: string[]) {
  const status = textOf(row, ["health", "status"], "Planned").toLowerCase();
  return terms.some((term) => status.includes(term));
}

export function ToolCatalog({ tools }: { tools: unknown }) {
  const rows = asArray(tools).map(asRecord);
  const displayRows = rows.length > 0 ? rows : defaultToolRows;
  const connectedCount = displayRows.filter((row) =>
    matchesStatus(row, ["active", "healthy", "ok", "connected"]),
  ).length;
  const reviewCount = displayRows.filter((row) =>
    matchesStatus(row, ["pending", "planned", "review"]),
  ).length;
  const systemCount = new Set(
    displayRows.map((row) => textOf(row, ["system", "provider", "crm"], "CRM")),
  ).size;
  const readiness =
    displayRows.length > 0
      ? Math.round((connectedCount / displayRows.length) * 100)
      : 0;

  return (
    <>
      <PageHeader
        description="Adapter catalog for external systems. Sagad OS does not replace every tool; it coordinates them through Agent Studio."
        title="Integrations"
      />

      <div className="space-y-4">
        <MetricStrip
          items={[
            {
              label: "Tools",
              value: displayRows.length,
              detail: "Adapter contracts",
              icon: Wrench,
            },
            {
              label: "Connected",
              value: connectedCount,
              detail: "Ready or healthy",
              icon: PlugZap,
            },
            {
              label: "Needs work",
              value: reviewCount,
              detail: "Planned, review, or pending",
              icon: ShieldAlert,
            },
            {
              label: "Systems",
              value: systemCount,
              detail: "Channels, CRM, KB, webhooks",
              icon: DatabaseZap,
            },
          ]}
        />

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {providerCards.map(({ name, role, status, detail, icon: Icon }) => (
            <Card className="shadow-xs" key={name}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm">{name}</CardTitle>
                    <CardDescription>{role}</CardDescription>
                  </div>
                  <span className="flex size-8 items-center justify-center rounded-md border bg-muted/50 text-muted-foreground">
                    <Icon aria-hidden="true" size={16} />
                  </span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                <p className="text-xs leading-5 text-muted-foreground">{detail}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <Tabs defaultValue="catalog" className="gap-4">
          <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs xl:flex-row xl:items-center xl:justify-between">
            <TabsList className="w-full sm:w-fit">
              <TabsTrigger value="catalog">Catalog</TabsTrigger>
              <TabsTrigger value="payloads">Payloads</TabsTrigger>
              <TabsTrigger value="readiness">Readiness</TabsTrigger>
            </TabsList>
            <div className="grid gap-2 sm:grid-cols-[minmax(180px,1fr)_160px_160px_auto] xl:min-w-[680px]">
              <div className="relative">
                <Search
                  aria-hidden="true"
                  className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground"
                />
                <Input
                  className="bg-background pl-8"
                  placeholder="Search tool, system, or owner"
                  readOnly
                />
              </div>
              <Select defaultValue="all" disabled>
                <SelectTrigger className="w-full bg-background">
                  <SelectValue placeholder="System" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All systems</SelectItem>
                  <SelectItem value="crm">Twenty CRM</SelectItem>
                  <SelectItem value="chatwoot">Chatwoot</SelectItem>
                  <SelectItem value="knowledge">Knowledge</SelectItem>
                  <SelectItem value="webhooks">Webhooks</SelectItem>
                  <SelectItem value="mcp">MCP</SelectItem>
                </SelectContent>
              </Select>
              <Select defaultValue="all" disabled>
                <SelectTrigger className="w-full bg-background">
                  <SelectValue placeholder="Health" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All health</SelectItem>
                  <SelectItem value="ready">Ready</SelectItem>
                  <SelectItem value="planned">Planned</SelectItem>
                </SelectContent>
              </Select>
              <Button variant="outline">
                <Filter aria-hidden="true" />
                Filter
              </Button>
            </div>
          </div>

          <TabsContent value="catalog" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <SectionPanel title="Integration Catalog" eyebrow="Adapter-first">
                <DataTable
                  columns={[
                    {
                      key: "tool",
                      label: "Tool",
                      render: (row: LooseRecord) => (
                        <div className="min-w-0 md:min-w-[220px]">
                          <div className="break-all font-medium text-foreground md:break-normal">
                            {textOf(row, ["name", "tool", "id"])}
                          </div>
                          <div className="line-clamp-2 break-words text-muted-foreground">
                            {textOf(row, ["description", "purpose"], "")}
                          </div>
                        </div>
                      ),
                    },
                    {
                      key: "system",
                      label: "System",
                      render: (row: LooseRecord) => (
                        <div className="space-y-1">
                          <Badge variant="secondary">
                            {textOf(row, ["system", "provider", "crm"], "CRM")}
                          </Badge>
                          <div className="text-[11px] text-muted-foreground">
                            {textOf(row, ["providerStatus", "deployment"], "External")}
                          </div>
                        </div>
                      ),
                    },
                    {
                      key: "owner",
                      label: "Owner",
                      render: (row: LooseRecord) =>
                        textOf(row, ["owner", "team"], "Ops"),
                    },
                    {
                      key: "health",
                      label: "Health",
                      render: (row: LooseRecord) => {
                        const status = textOf(row, ["health", "status"], "Planned");
                        return (
                          <StatusChip tone={toneFromStatus(status)}>
                            {status}
                          </StatusChip>
                        );
                      },
                    },
                  ]}
                  emptyLabel="No MCP or CRM tools are connected yet."
                  rows={displayRows}
                />
              </SectionPanel>

              <SectionPanel title="Adapter Readiness" eyebrow="Runtime contract">
                <div className="space-y-4 p-4">
                  <div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-foreground">
                        Connected tools
                      </span>
                      <span className="tabular-nums text-muted-foreground">
                        {readiness}%
                      </span>
                    </div>
                    <Progress className="mt-2" value={readiness} />
                  </div>
                  <div className="grid gap-2">
                    {[
                      ["Schema validation", "Pending"],
                      ["HITL approval route", "Planned"],
                      ["Retry and timeout policy", "Review"],
                    ].map(([label, status]) => (
                      <div
                        className="flex items-center justify-between rounded-lg border bg-background px-3 py-2 text-xs"
                        key={label}
                      >
                        <span className="text-muted-foreground">{label}</span>
                        <StatusChip tone={toneFromStatus(status)}>
                          {status}
                        </StatusChip>
                      </div>
                    ))}
                  </div>
                </div>
              </SectionPanel>
            </div>
          </TabsContent>

          <TabsContent value="payloads" className="mt-0">
            <div className="grid gap-4 lg:grid-cols-2">
              {displayRows.map((row, index) => (
                <Card className="shadow-xs" key={index}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <Code2
                        aria-hidden="true"
                        className="size-4 text-muted-foreground"
                      />
                      {textOf(row, ["name", "tool", "id"])}
                    </CardTitle>
                    <CardDescription>
                      {textOf(row, ["description", "purpose"], "Adapter payload")}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <Label className="mb-2 block" htmlFor={`payload-${index}`}>
                      Sample request
                    </Label>
                    <Textarea
                      className="min-h-40 resize-none bg-muted/40 font-mono text-xs"
                      id={`payload-${index}`}
                      readOnly
                      value={textOf(
                        row,
                        ["samplePayload", "payload", "example"],
                        "{}",
                      )}
                    />
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="readiness" className="mt-0">
            <SectionPanel title="Integration Checklist" eyebrow="Adapter states">
              <div className="grid gap-3 p-4 md:grid-cols-3">
                {readinessChecks.map(({ label, icon: Icon, status }) => (
                  <div
                    className="rounded-lg border bg-background p-4"
                    key={label}
                  >
                    <Icon
                      aria-hidden="true"
                      className="mb-3 size-4 text-muted-foreground"
                    />
                    <div className="font-medium text-foreground">{label}</div>
                    <div className="mt-3">
                      <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>
                    </div>
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
