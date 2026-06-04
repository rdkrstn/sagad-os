import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MetricStrip } from "@/components/ui/metric-strip";
import { Progress } from "@/components/ui/progress";
import { SectionPanel } from "@/components/ui/section-panel";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Bot,
  Code2,
  DatabaseZap,
  GitBranch,
  LockKeyhole,
  MessageSquareText,
  PlugZap,
  ServerCog,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Webhook,
} from "lucide-react";

type SettingItem = {
  label: string;
  description: string;
  value: string;
  control: "input" | "select" | "switch";
  status: "Planned" | "Review" | "Pending";
};

type SettingGroup = {
  title: string;
  eyebrow: string;
  icon: LucideIcon;
  items: SettingItem[];
};

type AdvancedAdapter = {
  name: string;
  owner: string;
  status: string;
  providerStatus: string;
  contract: string;
  endpoint: string;
  mode: string;
  description: string;
  samplePayload: string;
  progress: number;
  icon: LucideIcon;
};

type ProviderStatus = {
  provider: string;
  rawStatus: string;
  browserBoundary: string;
  debugNote: string;
};

const groups: SettingGroup[] = [
  {
    title: "Thresholds",
    eyebrow: "Runtime policy",
    icon: SlidersHorizontal,
    items: [
      {
        label: "Confidence floor",
        description: "Minimum answer confidence before supervisor review.",
        value: "0.78",
        control: "input",
        status: "Review",
      },
      {
        label: "SLA warning",
        description: "Conversation age before queue attention is required.",
        value: "15 min",
        control: "select",
        status: "Planned",
      },
      {
        label: "Max retry attempts",
        description: "Retry limit before a failed automation is held for review.",
        value: "2",
        control: "input",
        status: "Pending",
      },
    ],
  },
  {
    title: "Routing Rules",
    eyebrow: "Queue routing",
    icon: GitBranch,
    items: [
      {
        label: "Intent to pod mapping",
        description: "Map buyer, seller, leasing, and support intents to pods.",
        value: "Supervisor",
        control: "select",
        status: "Review",
      },
      {
        label: "Priority overrides",
        description: "Escalate high-risk, VIP, and stuck conversations.",
        value: "Enabled",
        control: "switch",
        status: "Planned",
      },
      {
        label: "Market coverage",
        description: "Limit automated answers to configured local markets.",
        value: "Metro Manila",
        control: "select",
        status: "Pending",
      },
    ],
  },
  {
    title: "Approval Rules",
    eyebrow: "HITL controls",
    icon: ShieldCheck,
    items: [
      {
        label: "High-risk sends",
        description: "Require approval for legal, financial, or policy claims.",
        value: "Enabled",
        control: "switch",
        status: "Review",
      },
      {
        label: "Discount requests",
        description: "Route pricing concessions to an authorized supervisor.",
        value: "Approval required",
        control: "select",
        status: "Planned",
      },
      {
        label: "Failed tool fallback",
        description: "Hold responses when required system context is missing.",
        value: "Hold for review",
        control: "select",
        status: "Pending",
      },
    ],
  },
  {
    title: "Prompt/Agent Config",
    eyebrow: "Agent behavior",
    icon: Bot,
    items: [
      {
        label: "Agent persona",
        description: "Default tone and response boundaries for Sagad agents.",
        value: "Concise ops assistant",
        control: "input",
        status: "Planned",
      },
      {
        label: "Guardrails",
        description: "Safety and disclosure rules injected into agent runs.",
        value: "Enabled",
        control: "switch",
        status: "Review",
      },
      {
        label: "Supervisor escalation prompt",
        description: "Prompt used when confidence or policy checks fail.",
        value: "Escalate with evidence summary.",
        control: "input",
        status: "Pending",
      },
    ],
  },
];

const advancedAdapters: AdvancedAdapter[] = [
  {
    name: "Chatwoot approval endpoint",
    owner: "Support Ops",
    status: "Review",
    providerStatus: "External channel",
    contract: "chatwoot.messages.send_approved",
    endpoint: "POST /api/conversations/:id/approve-send",
    mode: "HITL approved send only",
    description: "Sends a supervisor-approved reply through Agent Studio. Browser code never talks to Chatwoot directly.",
    samplePayload: JSON.stringify(
      {
        approved: true,
        supervisor_id: "dev-supervisor",
        edited_reply: "Approved reply body",
      },
      null,
      2,
    ),
    progress: 62,
    icon: MessageSquareText,
  },
  {
    name: "Twenty CRM external adapter",
    owner: "Revenue Ops",
    status: "Dry-run",
    providerStatus: "Twenty external",
    contract: "crm.lookup_contact",
    endpoint: "GET /integrations/twenty/health",
    mode: "GraphQL through Agent Studio",
    description: "Reads CRM context from the separately hosted Twenty instance. Credentials and write gates stay server-side.",
    samplePayload: JSON.stringify(
      {
        query: "Johnred Demafeliz",
        provider: "twenty",
        source: "agent-studio",
      },
      null,
      2,
    ),
    progress: 58,
    icon: DatabaseZap,
  },
  {
    name: "Generic webhook connector",
    owner: "AI Ops",
    status: "Planned",
    providerStatus: "External connector",
    contract: "webhook.outbound.trigger",
    endpoint: "Agent Studio adapter registry",
    mode: "Approval-gated webhook",
    description: "Provider-neutral handoff for client-owned systems after the approval boundary is satisfied.",
    samplePayload: JSON.stringify(
      {
        event_type: "post_approval_followup",
        conversation_id: "conv_123",
        approved: true,
      },
      null,
      2,
    ),
    progress: 18,
    icon: Webhook,
  },
  {
    name: "LangSmith trace adapter",
    owner: "AI Ops",
    status: "Optional",
    providerStatus: "External observability",
    contract: "observability.langsmith.trace",
    endpoint: "LangSmith SDK via Agent Studio",
    mode: "Environment-gated telemetry",
    description: "Attaches graph, tool, approval, and failure metadata to traces when observability variables are configured.",
    samplePayload: JSON.stringify(
      {
        thread_id: "thread_123",
        approval_status: "needs_approval",
        tool_results: [],
      },
      null,
      2,
    ),
    progress: 42,
    icon: PlugZap,
  },
  {
    name: "Future MCP tool layer",
    owner: "Platform",
    status: "Planned",
    providerStatus: "Future",
    contract: "mcp.tool_layer.dispatch",
    endpoint: "Future Agent Studio MCP facade",
    mode: "Adapter facade",
    description: "Provider-neutral tool facade for CRMs, inboxes, knowledge stores, and internal systems.",
    samplePayload: JSON.stringify(
      {
        tool: "crm.notes.create",
        provider: "twenty",
        approval_id: "approval_123",
      },
      null,
      2,
    ),
    progress: 24,
    icon: ServerCog,
  },
  {
    name: "Prompt registry",
    owner: "AI Ops",
    status: "Pending",
    providerStatus: "Local configuration",
    contract: "prompt.registry.resolve",
    endpoint: "Agent Studio prompt registry",
    mode: "Version-pinned prompt lookup",
    description: "Developer-facing prompt surface for versioning, rollback, and guardrail injection.",
    samplePayload: JSON.stringify(
      {
        prompt_key: "supervisor_escalation",
        version: "draft",
        include_guardrails: true,
      },
      null,
      2,
    ),
    progress: 48,
    icon: Bot,
  },
];

const providerStatuses: ProviderStatus[] = [
  {
    provider: "Chatwoot",
    rawStatus: "External channel / supervisor approval only",
    browserBoundary: "No direct browser provider calls",
    debugNote: "Send only through the supervisor approval endpoint.",
  },
  {
    provider: "Twenty CRM",
    rawStatus: "External VPS / dry-run",
    browserBoundary: "Credentials stay in Agent Studio",
    debugNote: "Health, writes, retries, and audit metadata are backend-owned.",
  },
  {
    provider: "LangSmith",
    rawStatus: "Optional / env gated",
    browserBoundary: "Trace metadata only",
    debugNote: "Missing env vars should degrade to no tracing, not failed ops.",
  },
  {
    provider: "Generic Webhooks",
    rawStatus: "Planned connector",
    browserBoundary: "Approval-gated outbound calls",
    debugNote: "Use for client-owned systems after contract validation exists.",
  },
];

const debugNotes = [
  "Developer-only adapter details live under Settings > Advanced.",
  "Agent Studio owns provider credentials, health checks, writes, retries, and audit metadata.",
  "Frontend browser code must never call Twenty CRM, Chatwoot, LangSmith, or webhook providers directly.",
  "External sends remain blocked until the HITL approval endpoint returns an approved result.",
  "n8n is not part of Sagad OS core orchestration.",
];

function renderControl(item: SettingItem) {
  if (item.control === "switch") {
    return (
      <Switch
        aria-label={item.label}
        checked={item.value === "Enabled"}
        disabled
      />
    );
  }

  if (item.control === "select") {
    return (
      <Select defaultValue={item.value} disabled>
        <SelectTrigger className="w-full bg-background sm:w-48">
          <SelectValue placeholder={item.value} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={item.value}>{item.value}</SelectItem>
        </SelectContent>
      </Select>
    );
  }

  return (
    <Input
      aria-label={item.label}
      className="bg-background sm:w-48"
      readOnly
      value={item.value}
    />
  );
}

export function SettingsConsole() {
  return (
    <>
      <PageHeader
        description="Operator and admin settings for Sagad OS policy, approvals, and agent behavior."
        title="Settings"
      />

      <div className="space-y-4">
        <MetricStrip
          items={[
            {
              label: "Setting groups",
              value: groups.length,
              detail: "Policy surfaces staged",
              icon: Settings2,
            },
            {
              label: "Controls",
              value: groups.reduce((total, group) => total + group.items.length, 0),
              detail: "Read-only preview fields",
              icon: SlidersHorizontal,
            },
            {
              label: "Advanced",
              value: advancedAdapters.length,
              detail: "Developer contracts isolated",
              icon: PlugZap,
            },
            {
              label: "Approval mode",
              value: "HITL",
              detail: "Sends remain supervisor gated",
              icon: LockKeyhole,
            },
          ]}
        />

        <Tabs defaultValue="controls" className="gap-4">
          <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 shadow-xs lg:flex-row lg:items-center lg:justify-between">
            <TabsList className="w-full sm:w-fit">
              <TabsTrigger value="controls">Controls</TabsTrigger>
              <TabsTrigger value="prompts">Prompts</TabsTrigger>
              <TabsTrigger value="advanced">Advanced</TabsTrigger>
            </TabsList>
            <div className="flex flex-col gap-2 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-end">
              <StatusChip tone="info">Preview mode</StatusChip>
              <span>Controls are read-only until settings persistence is wired.</span>
            </div>
          </div>

          <TabsContent value="controls" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-2">
              {groups.map((group) => {
                const Icon = group.icon;

                return (
                  <SectionPanel
                    title={group.title}
                    eyebrow={group.eyebrow}
                    key={group.title}
                  >
                    <div className="border-b bg-muted/30 px-4 py-3">
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Icon aria-hidden="true" className="size-4" />
                        Read-only preview. Changes require the settings API.
                      </div>
                    </div>
                    <div className="divide-y">
                      {group.items.map((item) => (
                        <div
                          className="grid gap-3 px-4 py-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"
                          key={item.label}
                        >
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <Label className="text-sm font-medium text-foreground">
                                {item.label}
                              </Label>
                              <StatusChip>{item.status}</StatusChip>
                            </div>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {item.description}
                            </p>
                          </div>
                          <div className="sm:justify-self-end">
                            {renderControl(item)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </SectionPanel>
                );
              })}
            </div>
          </TabsContent>

          <TabsContent value="prompts" className="mt-0">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
              <Card className="shadow-xs">
                <CardHeader>
                  <CardTitle>Supervisor Escalation Prompt</CardTitle>
                  <CardDescription>
                    Read-only operator preview of the escalation behavior that
                    will be backed by the prompt registry.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Label htmlFor="settings-prompt">Prompt draft</Label>
                  <Textarea
                    className="min-h-56 resize-none bg-muted/40 font-mono text-xs"
                    id="settings-prompt"
                    readOnly
                    value={[
                      "Summarize the customer goal, evidence used, missing facts, and recommended next action.",
                      "Do not send external messages without supervisor approval.",
                      "Include confidence notes and policy reasons when available.",
                    ].join("\n\n")}
                  />
                </CardContent>
              </Card>

              <SectionPanel title="Prompt Readiness" eyebrow="Registry state">
                <div className="space-y-3 p-4">
                  {[
                    ["Version pinning", "Planned"],
                    ["Guardrail injection", "Review"],
                    ["Rollback history", "Pending"],
                  ].map(([label, status]) => (
                    <div
                      className="flex items-center justify-between rounded-lg border bg-background px-3 py-2 text-xs"
                      key={label}
                    >
                      <span className="text-muted-foreground">{label}</span>
                      <StatusChip>{status}</StatusChip>
                    </div>
                  ))}
                </div>
              </SectionPanel>
            </div>
          </TabsContent>

          <TabsContent value="advanced" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
              <SectionPanel title="Raw Provider Status" eyebrow="Developer-only">
                <div className="border-b bg-muted/30 px-4 py-3">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <DatabaseZap aria-hidden="true" className="size-4" />
                    Provider status is for debugging adapter boundaries, not
                    day-to-day operator setup.
                  </div>
                  <div className="mt-2">
                    <StatusChip tone="info">Developer-only</StatusChip>
                  </div>
                </div>
                <div className="divide-y">
                  {providerStatuses.map((provider) => (
                    <div className="space-y-3 p-4" key={provider.provider}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium text-foreground">
                            {provider.provider}
                          </div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {provider.browserBoundary}
                          </div>
                        </div>
                        <StatusChip tone="info">
                          {provider.rawStatus}
                        </StatusChip>
                      </div>
                      <p className="text-xs leading-5 text-muted-foreground">
                        {provider.debugNote}
                      </p>
                    </div>
                  ))}
                </div>
              </SectionPanel>

              <SectionPanel title="Adapter Contracts" eyebrow="Runtime contract">
                <div className="divide-y">
                  {advancedAdapters.map((adapter) => {
                    const Icon = adapter.icon;

                    return (
                      <div className="p-4" key={adapter.name}>
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div className="flex gap-3">
                            <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md border bg-muted/50 text-muted-foreground">
                              <Icon aria-hidden="true" className="size-4" />
                            </span>
                            <div className="min-w-0">
                              <div className="font-medium text-foreground">
                                {adapter.name}
                              </div>
                              <div className="mt-1 text-xs text-muted-foreground">
                                Owner: {adapter.owner}
                              </div>
                            </div>
                          </div>
                          <StatusChip tone={toneFromStatus(adapter.status)}>
                            {adapter.status}
                          </StatusChip>
                        </div>
                        <Separator className="my-3" />
                        <dl className="grid gap-3 text-xs sm:grid-cols-3">
                          <div>
                            <dt className="font-medium text-muted-foreground">
                              Contract
                            </dt>
                            <dd className="mt-1 break-all font-mono text-foreground">
                              {adapter.contract}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-medium text-muted-foreground">
                              Endpoint
                            </dt>
                            <dd className="mt-1 break-all font-mono text-foreground">
                              {adapter.endpoint}
                            </dd>
                          </div>
                          <div>
                            <dt className="font-medium text-muted-foreground">
                              Provider status
                            </dt>
                            <dd className="mt-1 text-foreground">
                              {adapter.providerStatus}
                            </dd>
                          </div>
                        </dl>
                        <p className="mt-3 text-xs leading-5 text-muted-foreground">
                          {adapter.description}
                        </p>
                        <div className="mt-3 flex items-center gap-3">
                          <Progress value={adapter.progress} />
                          <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
                            {adapter.progress}%
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </SectionPanel>

              <SectionPanel title="Debug Copy" eyebrow="Boundary notes">
                <div className="space-y-2 p-4">
                  {debugNotes.map((note) => (
                    <div
                      className="rounded-lg border bg-background px-3 py-2 text-xs leading-5 text-muted-foreground"
                      key={note}
                    >
                      {note}
                    </div>
                  ))}
                </div>
              </SectionPanel>

              <div className="grid gap-4 lg:grid-cols-2">
                {advancedAdapters.map((adapter, index) => (
                  <Card className="shadow-xs" key={adapter.contract}>
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2 text-sm">
                        <Code2
                          aria-hidden="true"
                          className="size-4 text-muted-foreground"
                        />
                        {adapter.contract}
                      </CardTitle>
                      <CardDescription>{adapter.mode}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <Label
                        className="mb-2 block"
                        htmlFor={`advanced-payload-${index}`}
                      >
                        Sample JSON
                      </Label>
                      <Textarea
                        className="min-h-44 resize-none border-slate-800 bg-[#050B12] font-mono text-xs leading-6 text-[#E6FFF8]"
                        id={`advanced-payload-${index}`}
                        readOnly
                        value={adapter.samplePayload}
                      />
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
