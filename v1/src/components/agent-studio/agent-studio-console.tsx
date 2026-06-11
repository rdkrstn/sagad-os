import {
  Bot,
  BrainCircuit,
  GitBranch,
  Network,
  Route,
  ShieldCheck,
  Workflow,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  MetricCard,
  Panel,
  SourcePill,
  StatusPill,
  TerminalBlock,
} from "@/components/product/product-ui";
import { DataTable } from "@/components/ui/data-table";
import {
  asArray,
  asRecord,
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";
import { cn } from "@/lib/utils";

export type AgentStudioStageId =
  | "driver"
  | "workflow"
  | "agent"
  | "skill"
  | "graph"
  | "tools"
  | "approval"
  | "trace";

const agentStudioStages: Array<{
  id: AgentStudioStageId;
  label: string;
  detail: string;
  icon: LucideIcon;
}> = [
  {
    id: "driver",
    label: "Contact Driver",
    detail: "Why work arrived",
    icon: Route,
  },
  {
    id: "workflow",
    label: "Workflow",
    detail: "Operating route",
    icon: Workflow,
  },
  {
    id: "agent",
    label: "Agent",
    detail: "Worker assigned",
    icon: Bot,
  },
  {
    id: "skill",
    label: "Skill",
    detail: "Reusable playbook",
    icon: BrainCircuit,
  },
  {
    id: "graph",
    label: "Graph",
    detail: "Orchestration flow",
    icon: GitBranch,
  },
  {
    id: "tools",
    label: "Tools / MCP",
    detail: "Server-side actions",
    icon: Wrench,
  },
  {
    id: "approval",
    label: "Approval",
    detail: "Policy + HITL gate",
    icon: ShieldCheck,
  },
  {
    id: "trace",
    label: "Audit / Trace",
    detail: "What happened",
    icon: Network,
  },
];

export function AgentStudioRelationshipStrip({
  active,
}: {
  active: AgentStudioStageId;
}) {
  return (
    <section className="border border-border bg-card p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
            Agent Studio Map
          </div>
          <h2 className="mt-1 text-sm font-bold text-foreground">
            Contact Driver -&gt; Workflow -&gt; Agent -&gt; Skill -&gt; Graph -&gt; Tools/MCP -&gt; Approval -&gt; Audit/Trace
          </h2>
        </div>
        <StatusPill tone="info">Relationship mapped</StatusPill>
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
        {agentStudioStages.map((stage, index) => {
          const Icon = stage.icon;
          const isActive = stage.id === active;
          return (
            <div
              className={cn(
                "min-w-0 border border-border bg-surface-2 p-2 transition-colors",
                isActive &&
                  "border-[rgba(0,212,170,0.48)] bg-[rgba(0,212,170,0.12)]",
              )}
              key={stage.id}
            >
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "grid size-7 shrink-0 place-items-center rounded-sm border border-border bg-card text-muted-foreground",
                    isActive &&
                      "border-[rgba(0,212,170,0.42)] bg-[rgba(0,212,170,0.14)] text-[var(--accent-text)]",
                  )}
                >
                  <Icon aria-hidden="true" size={15} />
                </span>
                <div className="min-w-0">
                  <div className="font-mono text-[9px] uppercase text-muted-foreground">
                    {String(index + 1).padStart(2, "0")}
                  </div>
                  <div className="truncate text-xs font-bold text-foreground">
                    {stage.label}
                  </div>
                </div>
              </div>
              <div className="mt-2 truncate text-[11px] text-muted-foreground">
                {stage.detail}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function listOf(row: LooseRecord, key: string): string[] {
  const value = row[key];
  return Array.isArray(value) ? value.map(String) : [];
}

function listFrom(row: LooseRecord, keys: string[]): string[] {
  for (const key of keys) {
    const value = row[key];
    if (Array.isArray(value)) return value.map(String);
    if (typeof value === "string" && value.trim()) {
      return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    }
  }

  return [];
}

function boolText(
  row: LooseRecord,
  keys: string[],
  trueText: string,
  falseText: string,
  fallback = "Unknown",
) {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "boolean") return value ? trueText : falseText;
    if (typeof value === "string") {
      const normalized = value.toLowerCase();
      if (["true", "yes", "required", "enabled"].includes(normalized)) {
        return trueText;
      }
      if (["false", "no", "not required", "disabled"].includes(normalized)) {
        return falseText;
      }
    }
  }

  return fallback;
}

function policyReasons(row: LooseRecord): string[] {
  return listFrom(row, ["policyReasons", "policy_reasons", "reasons"]);
}

function schemaKeys(row: LooseRecord): string[] {
  const schema = asRecord(row.inputSchema ?? row.input_schema ?? row.schema);
  const properties = asRecord(schema.properties);
  const keys = Object.keys(properties).length > 0
    ? Object.keys(properties)
    : Object.keys(schema);
  return keys.slice(0, 4);
}

function InlineList({ values }: { values: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {values.length > 0 ? (
        values.map((value) => <SourcePill key={value}>{value}</SourcePill>)
      ) : (
        <span className="text-muted-foreground">None</span>
      )}
    </div>
  );
}

function toolRelationship(row: LooseRecord) {
  const toolName = textOf(row, ["tool", "name"], "").toLowerCase();
  if (toolName.includes("webhook") || toolName.includes("receive")) return "Contact Driver -> Workflow";
  if (toolName.includes("lookup") || toolName.includes("retrieve")) return "Skill -> Graph";
  if (toolName.includes("send") || toolName.includes("create") || toolName.includes("update")) {
    return "Tools/MCP -> Approval";
  }
  if (toolName.includes("trace") || toolName.includes("observability")) return "Audit / Trace";
  if (toolName.includes("mcp")) return "Tools/MCP";
  return "Agent -> Skill";
}

function CatalogIntro({
  title,
  description,
  status = "Preview",
}: {
  title: string;
  description: string;
  status?: string;
}) {
  return (
    <div className="grid gap-3 border border-border bg-card p-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
      <div>
        <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
          Agent Studio
        </div>
        <h2 className="mt-1 text-lg font-bold text-foreground">{title}</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
      <StatusPill status={status}>{status}</StatusPill>
    </div>
  );
}

export function AgentsConsole({ agents }: { agents: unknown }) {
  const rows = asArray(agents).map(asRecord);

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Agents"
        description="AI workers configured for service operations. Agents are not drivers; drivers decide which agent and skill should handle work."
      />
      <AgentStudioRelationshipStrip active="agent" />
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Sales, support, QA, escalation" icon={Bot} label="Agents" value={rows.length} />
        <MetricCard detail="Configured playbooks" icon={BrainCircuit} label="Skills allowed" value="5" />
        <MetricCard detail="Server-side actions" icon={Wrench} label="Tools allowed" value="8" />
        <MetricCard detail="Writes held by policy" icon={ShieldCheck} label="Approval policy" value="On" />
      </section>
      <Panel title="Agent Configuration" eyebrow="Workers">
        <div className="grid gap-3 p-3 xl:grid-cols-2">
          {rows.map((row) => {
            const name = textOf(row, ["name"], "Agent");
            const isSales = name.toLowerCase().includes("sales");
            const isSupervisor = name.toLowerCase().includes("harper") || textOf(row, ["role"], "").toLowerCase().includes("supervisor");
            const skills = isSupervisor
              ? ["Policy Review", "Human Takeover"]
              : isSales
                ? ["Sales Sizing Assistant", "Objection Response"]
                : ["Refund Resolver", "Order Status Lookup", "Account Verification"];
            const tools = isSupervisor
              ? ["chatwoot.send_message", "crm.create_note"]
              : ["crm.lookup_contact", "knowledge.search", "chatwoot.draft_reply"];
            const driverLanes = isSupervisor
              ? ["Angry customer escalation", "Failed tool/send", "Manager request"]
              : isSales
                ? ["Sales sizing questions", "Pricing question", "Lead qualification"]
                : ["Refund policy", "Order status", "Account verification"];
            const workflow = isSupervisor
              ? "Escalation Workflow"
              : isSales
                ? "Lead Qualification Workflow"
                : "Support Resolution Workflow";

            return (
              <div className="border border-border bg-surface-2 p-3" key={textOf(row, ["id"], name)}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold text-foreground">{name}</h3>
                    <p className="mt-1 text-sm leading-6 text-muted-foreground">
                      {isSupervisor
                        ? "Human supervisor for approval, escalation, and policy override decisions."
                        : isSales
                          ? "Qualifies sales and sizing questions using approved product and CRM context."
                          : "Resolves support, order, refund, and account questions using approved SOPs."}
                    </p>
                  </div>
                  <StatusPill status={textOf(row, ["status", "health"], "Active")}>
                    {textOf(row, ["status", "health"], "Active")}
                  </StatusPill>
                </div>
                <div className="mt-3 grid gap-3 text-xs md:grid-cols-2">
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Contact drivers</div>
                    <InlineList values={driverLanes} />
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Workflow</div>
                    <span className="font-semibold text-foreground">{workflow}</span>
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed skills</div>
                    <InlineList values={skills} />
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed tools</div>
                    <InlineList values={tools} />
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Graph</div>
                    <span className="font-semibold text-foreground">Default Support Graph v0.1.4</span>
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Risk tolerance</div>
                    <span className="font-semibold text-foreground">{isSupervisor ? "High" : "Medium"}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

export function SkillsConsole({ skills }: { skills: unknown }) {
  const rows = asArray(skills).map(asRecord);
  const toolAware = rows.filter((row) =>
    boolText(row, ["requiresTools", "requires_tools"], "yes", "no") === "yes",
  ).length;
  const modelBacked = rows.filter((row) =>
    boolText(row, ["requiresModel", "requires_model"], "yes", "no") === "yes",
  ).length;

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Skills"
        description="Internal Agent Studio capabilities used by graph nodes. Skills can require model reasoning or tool manifests, but provider execution still goes through tool policy."
      />
      <AgentStudioRelationshipStrip active="skill" />
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Registry definitions" icon={BrainCircuit} label="Skills" value={rows.length} />
        <MetricCard detail="Can request tool manifests" icon={Wrench} label="Tool-aware" value={toolAware} />
        <MetricCard detail="Use model reasoning" icon={Bot} label="Model-backed" value={modelBacked} />
        <MetricCard detail="Policy notes declared" icon={ShieldCheck} label="Policy rules" value={rows.reduce((sum, row) => sum + policyReasons(row).length, 0)} />
      </section>
      <div className="grid gap-3 xl:grid-cols-2">
        {rows.map((row) => {
          const name = textOf(row, ["name"], "Skill");
          const requiredTools = listFrom(row, ["requiredTools", "required_tools", "allowedTools", "tools"]);

          return (
            <Panel
              action={<StatusPill status={textOf(row, ["status"], "Draft")}>{textOf(row, ["status"], "Draft")}</StatusPill>}
              key={textOf(row, ["id"], name)}
              title={name}
              eyebrow={textOf(row, ["version"], "v0")}
            >
              <div className="space-y-3 p-3">
                <p className="text-sm leading-6 text-muted-foreground">{textOf(row, ["description"], "")}</p>
                <div className="grid gap-3 text-xs md:grid-cols-2">
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Category</div>
                    <span className="font-semibold text-foreground">{textOf(row, ["category"], "Workflow")}</span>
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Risk</div>
                    <span className="font-semibold text-foreground">{textOf(row, ["riskLevel", "risk"], "Low")}</span>
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed agents</div>
                    <InlineList values={listFrom(row, ["allowedAgents", "allowed_agents", "agents"])} />
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Mode</div>
                    <span className="font-semibold text-foreground">{textOf(row, ["mode"], "Skill")}</span>
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Model</div>
                    <span className="font-semibold text-foreground">
                      {boolText(row, ["requiresModel", "requires_model"], "Required", "Not required")}
                    </span>
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Tools</div>
                    <span className="font-semibold text-foreground">
                      {boolText(row, ["requiresTools", "requires_tools"], "Required", "Not required")}
                    </span>
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Required tools</div>
                    <InlineList values={requiredTools} />
                  </div>
                  <div>
                    <div className="mb-1 font-mono uppercase text-muted-foreground">Dry-run/live</div>
                    <span className="font-semibold text-foreground">{textOf(row, ["liveMode"], "No provider execution")}</span>
                  </div>
                </div>
                <div>
                  <div className="mb-1 font-mono text-xs uppercase text-muted-foreground">Policy reasons</div>
                  <InlineList values={policyReasons(row)} />
                </div>
              </div>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

export function GraphsConsole({ graphs }: { graphs: unknown }) {
  const rows = asArray(graphs).map(asRecord);

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Graphs"
        description="LangGraph orchestration flows that route AI work through classification, context, tools, draft, policy, HITL approval, send, audit, and trace."
      />
      <AgentStudioRelationshipStrip active="graph" />
      {rows.map((row) => {
        const nodes = listOf(row, "nodes");
        return (
          <Panel
            action={<StatusPill status={textOf(row, ["status"], "Draft")}>{textOf(row, ["status"], "Draft")}</StatusPill>}
            key={textOf(row, ["id"], textOf(row, ["name"], "graph"))}
            title={textOf(row, ["name"], "Graph")}
            eyebrow={textOf(row, ["version"], "v0")}
          >
            <div className="space-y-4 p-3">
              <p className="text-sm leading-6 text-muted-foreground">{textOf(row, ["description"], "")}</p>
              <div className="flex flex-wrap items-center gap-2">
                {nodes.map((node, index) => (
                  <div className="flex items-center gap-2" key={`${node}-${index}`}>
                    <span className="border border-border bg-surface-2 px-2 py-1 font-mono text-[11px] text-foreground">
                      {node}
                    </span>
                    {index < nodes.length - 1 ? <span className="text-muted-foreground">-&gt;</span> : null}
                  </div>
                ))}
              </div>
              <div className="grid gap-3 text-xs md:grid-cols-2 xl:grid-cols-4">
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Trigger</div>
                  <span className="font-semibold text-foreground">{textOf(row, ["trigger"], "inbound")}</span>
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">HITL pause points</div>
                  <InlineList values={listOf(row, "hitlPausePoints")} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Fallback</div>
                  <span className="text-foreground">{textOf(row, ["fallbackPath"], "")}</span>
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed agents</div>
                  <InlineList values={listOf(row, "allowedAgents")} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed tools</div>
                  <InlineList values={listOf(row, "allowedTools")} />
                </div>
              </div>
            </div>
          </Panel>
        );
      })}
    </div>
  );
}

export function ToolsConsole({ tools }: { tools: unknown }) {
  const rows = asArray(tools).map(asRecord);
  const approvalRequired = rows.filter((row) =>
    boolText(row, ["requiresApproval", "requires_approval"], "yes", "no") === "yes",
  ).length;
  const dryRunDefault = rows.filter((row) =>
    boolText(row, ["dryRun", "dry_run", "dryRunDefault"], "yes", "no") === "yes",
  ).length;

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Tools"
        description="Agent Studio tool manifests. The browser reads capability metadata only; execution, credentials, dry-run policy, and provider calls stay server-side."
      />
      <AgentStudioRelationshipStrip active="tools" />
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Loaded from Agent Studio or preview fallback" icon={Wrench} label="Manifests" value={rows.length} />
        <MetricCard detail="Policy must approve before execution" icon={ShieldCheck} label="Approval required" value={approvalRequired} />
        <MetricCard detail="Default provider-safe mode" icon={Route} label="Dry-run default" value={dryRunDefault} />
        <MetricCard detail="Browser never calls providers" icon={Network} label="Boundary" value="Server" />
      </section>
      <Panel title="Tool Manifests" eyebrow="Agent Studio policy" action={<StatusPill tone="warning">No browser execution</StatusPill>}>
        <DataTable
          columns={[
            {
              key: "tool",
              label: "Tool",
              render: (row) => (
                <div>
                  <div>{textOf(row, ["toolName", "tool", "name"], "tool")}</div>
                  <div className="mt-1 text-xs font-normal text-muted-foreground">
                    {textOf(row, ["description"], "")}
                  </div>
                </div>
              ),
            },
            {
              key: "provider",
              label: "Provider / skill",
              render: (row) => (
                <div className="grid gap-1">
                  <span>{textOf(row, ["provider", "system"], "Agent Studio")}</span>
                  <span className="text-muted-foreground">
                    {textOf(row, ["skillName", "skill_name"], toolRelationship(row))}
                  </span>
                </div>
              ),
            },
            {
              key: "mode",
              label: "Mode",
              render: (row) => (
                <div className="grid gap-1">
                  <StatusPill status={textOf(row, ["mode"], "Read")}>
                    {textOf(row, ["mode"], "Read")}
                  </StatusPill>
                  <span className="text-muted-foreground">
                    {textOf(row, ["liveMode"], "Policy decides dry-run/live")}
                  </span>
                </div>
              ),
            },
            {
              key: "risk",
              label: "Risk",
              render: (row) => textOf(row, ["riskLevel", "risk"], "Low"),
            },
            {
              key: "approval",
              label: "Approval",
              render: (row) =>
                boolText(row, ["requiresApproval", "requires_approval"], "Required", "Not required"),
            },
            {
              key: "policy",
              label: "Policy reasons",
              render: (row) => <InlineList values={policyReasons(row).slice(0, 2)} />,
            },
            {
              key: "schema",
              label: "Input",
              render: (row) => <InlineList values={schemaKeys(row)} />,
            },
          ]}
          rows={rows}
        />
      </Panel>
    </div>
  );
}

export function McpServersConsole({ servers }: { servers: unknown }) {
  const rows = asArray(servers).map(asRecord);
  const approvalRequired = rows.filter((row) =>
    boolText(row, ["requiresApproval", "requires_approval"], "yes", "no") === "yes",
  ).length;

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="MCP Descriptors"
        description="Descriptor-only MCP boundary exposed by Agent Studio. Descriptors advertise policy-wrapped capabilities; the browser never calls MCP servers or provider APIs directly."
      />
      <AgentStudioRelationshipStrip active="tools" />
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Policy-wrapped capability records" icon={Network} label="Descriptors" value={rows.length} />
        <MetricCard detail="Write or customer-facing tools" icon={ShieldCheck} label="Approval required" value={approvalRequired} />
        <MetricCard detail="No raw provider credentials" icon={Wrench} label="Boundary" value="Agent Studio" />
        <MetricCard detail="Descriptor metadata only" icon={GitBranch} label="Execution" value="Server" />
      </section>
      <div className="grid gap-3 xl:grid-cols-3">
        {rows.map((row) => (
          <Panel
            action={<StatusPill status={textOf(row, ["status"], "Planned")}>{textOf(row, ["status"], "Planned")}</StatusPill>}
            key={textOf(row, ["id"], textOf(row, ["name"], "mcp"))}
            title={textOf(row, ["name"], "MCP Descriptor")}
            eyebrow={textOf(row, ["transport"], "planned")}
          >
            <div className="space-y-3 p-3">
              <p className="text-sm leading-6 text-muted-foreground">{textOf(row, ["detail"], "")}</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="border border-border bg-surface-2 p-2">
                  <span className="text-muted-foreground">Mode</span>
                  <br />
                  <b>{textOf(row, ["mode"], "Read")}</b>
                </div>
                <div className="border border-border bg-surface-2 p-2">
                  <span className="text-muted-foreground">Risk</span>
                  <br />
                  <b>{textOf(row, ["riskLevel", "risk"], "Low")}</b>
                </div>
                <div className="border border-border bg-surface-2 p-2">
                  <span className="text-muted-foreground">Approval</span>
                  <br />
                  <b>{boolText(row, ["requiresApproval", "requires_approval"], "Required", "Not required")}</b>
                </div>
                <div className="border border-border bg-surface-2 p-2">
                  <span className="text-muted-foreground">Run mode</span>
                  <br />
                  <b>{textOf(row, ["liveMode"], "Policy decides")}</b>
                </div>
              </div>
              <div className="grid gap-3 text-xs">
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Descriptor boundary</div>
                  <span className="font-semibold text-foreground">{textOf(row, ["boundary"], "Agent Studio policy boundary")}</span>
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed agents</div>
                  <InlineList values={listFrom(row, ["allowedAgents", "allowed_agents"])} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed skills</div>
                  <InlineList values={listFrom(row, ["allowedSkills", "allowed_skills"])} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Input schema</div>
                  <InlineList values={schemaKeys(row)} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Policy reasons</div>
                  <InlineList values={policyReasons(row)} />
                </div>
              </div>
              <InlineList values={listFrom(row, ["tools", "name"])} />
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}

export function TracesConsole({ traces }: { traces: unknown }) {
  const rows = asArray(traces).map(asRecord);

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Traces"
        description="Sagad Audit is the operator record. LangSmith traces are developer observability for graph runs, tool calls, latency, errors, and cost."
      />
      <Panel title="Agent Run Traces" eyebrow="LangGraph / LangSmith" action={<StatusPill tone="info">{rows.length} runs</StatusPill>}>
        <DataTable
          columns={[
            { key: "run", label: "Run", render: (row) => textOf(row, ["id"], "run") },
            { key: "customer", label: "Customer", render: (row) => textOf(row, ["customerName"], "Customer") },
            { key: "agent", label: "Agent", render: (row) => textOf(row, ["agent"], "Agent") },
            { key: "skill", label: "Skill", render: (row) => textOf(row, ["skill"], "Skill") },
            { key: "graph", label: "Graph", render: (row) => textOf(row, ["graph"], "Graph") },
            { key: "status", label: "Status", render: (row) => <StatusPill status={textOf(row, ["status"], "Logged")}>{textOf(row, ["status"], "Logged")}</StatusPill> },
            { key: "latency", label: "Latency", render: (row) => textOf(row, ["latency"], "n/a") },
            { key: "tools", label: "Tools", render: (row) => <InlineList values={listOf(row, "toolsCalled")} /> },
          ]}
          rows={rows}
        />
      </Panel>
    </div>
  );
}

export function EvaluationsConsole({ evaluations }: { evaluations: unknown }) {
  const rows = asArray(evaluations).map(asRecord);

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Evaluations"
        description="Score agent work against policy, QA rubrics, knowledge coverage, tool reliability, and approval outcomes."
      />
      <div className="grid gap-3 xl:grid-cols-3">
        {rows.map((row) => (
          <Panel
            action={<StatusPill status={textOf(row, ["status"], "Preview")}>{textOf(row, ["status"], "Preview")}</StatusPill>}
            key={textOf(row, ["id"], textOf(row, ["name"], "eval"))}
            title={textOf(row, ["name"], "Evaluation")}
            eyebrow="Scorecard"
          >
            <div className="space-y-3 p-3">
              <div className="text-3xl font-bold text-foreground">{textOf(row, ["score"], "n/a")}</div>
              <p className="text-sm leading-6 text-muted-foreground">{textOf(row, ["focus"], "")}</p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="border border-border bg-surface-2 p-2">Samples<br /><b>{textOf(row, ["sampleSize"], "0")}</b></div>
                <div className="border border-border bg-surface-2 p-2">Failures<br /><b>{textOf(row, ["failures"], "0")}</b></div>
              </div>
              <p className="text-xs leading-5 text-muted-foreground">{textOf(row, ["recommendation"], "")}</p>
            </div>
          </Panel>
        ))}
      </div>
      <TerminalBlock
        lines={[
          { label: "$ ", text: "sagados eval run --preview" },
          { label: "OK ", text: "policy gates checked against review queue samples" },
          { label: "OK ", text: "tool reliability scored from audit and trace events" },
          { label: "HITL ", text: "failed or risky outputs remain supervisor-gated" },
        ]}
      />
    </div>
  );
}
