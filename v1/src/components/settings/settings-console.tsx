import type { LucideIcon } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
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
import { StatusChip } from "@/components/ui/status-chip";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Bot,
  Clock3,
  DatabaseZap,
  GitBranch,
  LockKeyhole,
  PlugZap,
  Save,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
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
        description: "Retry limit for adapter-backed tool calls.",
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
        description: "Hold responses when adapter results are missing.",
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

const adapters = [
  {
    name: "Chatwoot approval endpoint",
    owner: "Support Ops",
    status: "Review",
    progress: 62,
  },
  {
    name: "Twenty CRM external adapter",
    owner: "Revenue Ops",
    status: "Dry-run",
    progress: 58,
  },
  {
    name: "Generic webhook connector",
    owner: "AI Ops",
    status: "Planned",
    progress: 18,
  },
  {
    name: "LangSmith trace adapter",
    owner: "AI Ops",
    status: "Optional",
    progress: 42,
  },
  {
    name: "Future MCP tool layer",
    owner: "Platform",
    status: "Planned",
    progress: 24,
  },
  {
    name: "Prompt registry",
    owner: "AI Ops",
    status: "Pending",
    progress: 48,
  },
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
        description="Self-host preview settings for Sagad OS policy, approvals, prompts, and external adapters."
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
              detail: "Form-backed future fields",
              icon: SlidersHorizontal,
            },
            {
              label: "Adapters",
              value: adapters.length,
              detail: "External systems tracked",
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
              <TabsTrigger value="adapters">Adapters</TabsTrigger>
            </TabsList>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline">
                <Clock3 aria-hidden="true" />
                Change log
              </Button>
              <Button disabled>
                <Save aria-hidden="true" />
                Save changes
              </Button>
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
                        Adapter-backed configuration pending.
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
                    Read-only preview of the prompt surface that will be backed by
                    the prompt registry.
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
                      "Include failed tool calls and confidence notes when available.",
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

          <TabsContent value="adapters" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
              <SectionPanel title="Twenty CRM Adapter" eyebrow="External VPS">
                <div className="border-b bg-muted/30 px-4 py-3">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <DatabaseZap aria-hidden="true" className="size-4" />
                    Twenty is hosted outside Sagad OS. Browser components never see its API key.
                  </div>
                </div>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 p-4 text-xs">
                  {[
                    ["Status", "External / disabled by default"],
                    ["Mode", "GraphQL via Agent Studio"],
                    ["Dry-run", "Enabled"],
                    ["Writes", "Approval + env gated"],
                    ["Schema", "Runtime readiness check"],
                    ["Secrets", "Server-side only"],
                    ["Health", "GET /integrations/twenty/health"],
                    ["Rate policy", "Throttle in Agent Studio"],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt className="font-medium text-muted-foreground">{label}</dt>
                      <dd className="mt-1 text-foreground">{value}</dd>
                    </div>
                  ))}
                </dl>
              </SectionPanel>

              <SectionPanel title="Adapter Readiness" eyebrow="Settings backend">
                <div className="divide-y">
                  {adapters.map((adapter) => (
                    <div className="p-4" key={adapter.name}>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="font-medium text-foreground">
                            {adapter.name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Owner: {adapter.owner}
                          </div>
                        </div>
                        <StatusChip>{adapter.status}</StatusChip>
                      </div>
                      <Separator className="my-3" />
                      <div className="flex items-center gap-3">
                        <Progress value={adapter.progress} />
                        <span className="w-10 text-right text-xs tabular-nums text-muted-foreground">
                          {adapter.progress}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </SectionPanel>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </>
  );
}
