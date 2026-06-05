import {
  Activity,
  Bot,
  Boxes,
  Building2,
  CheckCircle2,
  Code2,
  Database,
  ExternalLink,
  GitBranch,
  KeyRound,
  Network,
  Server,
  ShieldCheck,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { MetricStrip } from "@/components/ui/metric-strip";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip } from "@/components/ui/status-chip";

type AdminNavItem = {
  label: string;
  detail: string;
  icon: typeof Server;
};

type HealthRow = {
  system: string;
  owner: string;
  status: "Healthy" | "Ready" | "Optional" | "Needs setup";
  detail: string;
};

type PlatformApp = {
  name: string;
  category: string;
  status: "Enabled" | "Optional" | "Planned";
  setup: string;
};

const adminNav: AdminNavItem[] = [
  { label: "Dashboard", detail: "Instance health", icon: Activity },
  { label: "Workspaces", detail: "Tenants and accounts", icon: Building2 },
  { label: "Users", detail: "Roles and access", icon: Users },
  { label: "AI Agents", detail: "Runtime graph ownership", icon: Bot },
  { label: "Platform Apps", detail: "Adapters and gateways", icon: Boxes },
  { label: "Settings", detail: "Secrets and policies", icon: ShieldCheck },
];

const healthRows: HealthRow[] = [
  {
    system: "Sagad Console",
    owner: "Frontend",
    status: "Healthy",
    detail: "Auth.js protected operator UI.",
  },
  {
    system: "Agent Studio",
    owner: "AI Ops",
    status: "Ready",
    detail: "FastAPI runtime with LangGraph graph export.",
  },
  {
    system: "Sagad Postgres",
    owner: "Platform",
    status: "Ready",
    detail: "Auth, conversations, approvals, audit, and pgvector foundation.",
  },
  {
    system: "LiteLLM Gateway",
    owner: "AI Ops",
    status: "Optional",
    detail: "OpenAI-compatible model gateway for OpenAI and DeepSeek test credits.",
  },
];

const platformApps: PlatformApp[] = [
  {
    name: "Chatwoot Adapter",
    category: "Channel intake",
    status: "Enabled",
    setup: "Inbound webhook and supervisor-approved send path.",
  },
  {
    name: "Twenty CRM Adapter",
    category: "External CRM",
    status: "Optional",
    setup: "Read-only context first; writes stay approval-gated and dry-run by default.",
  },
  {
    name: "LangGraph App",
    category: "AI workflow",
    status: "Enabled",
    setup: "`sagad_conversation` is exposed through `agent-studio/langgraph.json`.",
  },
  {
    name: "LiteLLM Gateway",
    category: "Model routing",
    status: "Optional",
    setup: "Use one OpenAI-compatible endpoint for OpenAI and DeepSeek models.",
  },
  {
    name: "Uptime Kuma",
    category: "Monitoring",
    status: "Planned",
    setup: "Read-only infrastructure health surface.",
  },
];

function statusTone(status: HealthRow["status"] | PlatformApp["status"]) {
  if (status === "Healthy" || status === "Ready" || status === "Enabled") {
    return "good";
  }
  if (status === "Optional") {
    return "info";
  }
  if (status === "Needs setup") {
    return "warning";
  }
  return "neutral";
}

export function SuperAdminConsole() {
  return (
    <div>
      <PageHeader
        description="Instance-level control plane for self-hosted Sagad OS deployments, platform apps, model gateways, and runtime health."
        meta="SuperAdmin"
        title="SuperAdmin Console"
      />

      <div className="grid gap-4 xl:grid-cols-[240px_minmax(0,1fr)]">
        <SectionPanel className="xl:sticky xl:top-0 xl:self-start" eyebrow="Instance" title="Admin Areas">
          <div className="divide-y">
            {adminNav.map((item) => {
              const Icon = item.icon;

              return (
                <div className="flex items-start gap-3 p-3" key={item.label}>
                  <span className="rounded-md border bg-[#F8F6F1] p-2 text-[#008F7A]">
                    <Icon aria-hidden="true" size={15} />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{item.label}</div>
                    <div className="mt-0.5 text-xs text-muted-foreground">{item.detail}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </SectionPanel>

        {/* TODO: Replace static content with real data and add interactivity to the nav and status chips. */}
        <div className="space-y-4">
          <MetricStrip
            items={[
              {
                label: "Workspaces",
                value: 1,
                detail: "Johnred Workspace",
                icon: Building2,
              },
              {
                label: "Active users",
                value: 1,
                detail: "Google OAuth enabled",
                icon: Users,
              },
              {
                label: "Platform apps",
                value: 5,
                detail: "2 enabled, 2 optional, 1 planned",
                icon: Boxes,
              },
              {
                label: "Runtime health",
                value: "Live",
                detail: "Liveness separated from readiness",
                icon: CheckCircle2,
              },
            ]}
          />

          <div className="grid gap-4 xl:grid-cols-2">
            <SectionPanel eyebrow="Runtime" title="Instance Health">
              <div className="divide-y">
                {healthRows.map((row) => (
                  <div className="grid gap-3 p-4 md:grid-cols-[1fr_120px_120px]" key={row.system}>
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{row.system}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{row.detail}</div>
                    </div>
                    <div className="text-xs text-muted-foreground">{row.owner}</div>
                    <StatusChip tone={statusTone(row.status)}>{row.status}</StatusChip>
                  </div>
                ))}
              </div>
            </SectionPanel>

            <SectionPanel eyebrow="Access" title="Roles And Boundaries">
              <div className="space-y-3 p-4 text-sm">
                <div className="rounded-md border bg-[#F8F6F1] p-3">
                  <div className="flex items-center gap-2 font-medium">
                    <KeyRound aria-hidden="true" size={15} />
                    Owner / Admin
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Can configure provider credentials, model gateway settings, and write policies.
                  </p>
                </div>
                <div className="rounded-md border bg-[#F8F6F1] p-3">
                  <div className="flex items-center gap-2 font-medium">
                    <ShieldCheck aria-hidden="true" size={15} />
                    Supervisor / QA
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Can review exceptions, inspect evidence, approve drafts, and view redacted health.
                  </p>
                </div>
                <div className="rounded-md border bg-[#F8F6F1] p-3">
                  <div className="flex items-center gap-2 font-medium">
                    <Code2 aria-hidden="true" size={15} />
                    Integrator
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Can inspect adapter contracts under Settings Advanced without seeing raw secrets.
                  </p>
                </div>
              </div>
            </SectionPanel>
          </div>

          <SectionPanel eyebrow="Platform Apps" title="Connected Systems And Gateways">
            <div className="divide-y">
              {platformApps.map((app) => (
                <div className="grid gap-3 p-4 lg:grid-cols-[220px_160px_120px_1fr]" key={app.name}>
                  <div className="text-sm font-medium">{app.name}</div>
                  <div className="text-xs text-muted-foreground">{app.category}</div>
                  <StatusChip tone={statusTone(app.status)}>{app.status}</StatusChip>
                  <div className="text-xs text-muted-foreground">{app.setup}</div>
                </div>
              ))}
            </div>
          </SectionPanel>

          <div className="grid gap-4 xl:grid-cols-2">
            <SectionPanel
              action={
                <Button asChild size="sm" variant="outline">
                  <a href="http://localhost:2024" rel="noreferrer" target="_blank">
                    Open Studio <ExternalLink aria-hidden="true" size={14} />
                  </a>
                </Button>
              }
              eyebrow="LangGraph"
              title="LangGraph App"
            >
              <div className="space-y-3 p-4 text-sm">
                <div className="flex items-center gap-2">
                  <GitBranch className="text-[#008F7A]" size={16} />
                  <span className="font-medium">Graph:</span>
                  <code className="rounded border bg-[#F8F6F1] px-1.5 py-0.5 text-xs">
                    sagad_conversation
                  </code>
                </div>
                <p className="text-xs text-muted-foreground">
                  Use LangGraph Studio for workflow inspection and graph debugging. Use Sagad Console
                  for live supervisor operations.
                </p>
                <pre className="overflow-x-auto rounded-md border bg-[#08111F] p-3 text-xs text-white">
                  <code>cd agent-studio{"\n"}uv run langgraph dev --host 0.0.0.0 --port 2024</code>
                </pre>
              </div>
            </SectionPanel>

            <SectionPanel eyebrow="Model Gateway" title="LiteLLM">
              <div className="space-y-3 p-4 text-sm">
                <div className="flex items-center gap-2">
                  <Network className="text-[#008F7A]" size={16} />
                  <span className="font-medium">Gateway URL:</span>
                  <code className="rounded border bg-[#F8F6F1] px-1.5 py-0.5 text-xs">
                    http://litellm:4000/v1
                  </code>
                </div>
                <p className="text-xs text-muted-foreground">
                  Optional OpenAI-compatible gateway for OpenAI and DeepSeek credits. Agent Studio
                  should call LiteLLM server-side; browser code should not call model providers.
                </p>
                <pre className="overflow-x-auto rounded-md border bg-[#08111F] p-3 text-xs text-white">
                  <code>
                    docker compose -f compose.preview.yaml --profile litellm up -d litellm
                  </code>
                </pre>
              </div>
            </SectionPanel>
          </div>

          <SectionPanel eyebrow="Data" title="Persistence Boundary">
            <div className="grid gap-3 p-4 md:grid-cols-3">
              <div className="rounded-md border bg-[#F8F6F1] p-3">
                <Database className="mb-2 text-[#008F7A]" size={17} />
                <div className="text-sm font-medium">Sagad Postgres</div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Owns auth sessions, conversations, approvals, audit rows, integration config, and
                  pgvector retrieval state.
                </p>
              </div>
              <div className="rounded-md border bg-[#F8F6F1] p-3">
                <Server className="mb-2 text-[#008F7A]" size={17} />
                <div className="text-sm font-medium">Agent Studio</div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Owns provider credentials, health checks, retries, write gates, and runtime traces.
                </p>
              </div>
              <div className="rounded-md border bg-[#F8F6F1] p-3">
                <ShieldCheck className="mb-2 text-[#008F7A]" size={17} />
                <div className="text-sm font-medium">Console</div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Owns human review workflows and only receives redacted status or approved actions.
                </p>
              </div>
            </div>
          </SectionPanel>
        </div>
      </div>
    </div>
  );
}
