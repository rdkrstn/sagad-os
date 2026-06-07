import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  GitBranch,
  ShieldCheck,
  Wrench,
} from "lucide-react";
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
  numberOf,
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";

function listOf(row: LooseRecord, key: string): string[] {
  const value = row[key];
  return Array.isArray(value) ? value.map(String) : [];
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

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Skills"
        description="Reusable playbooks that combine instructions, required context, knowledge domains, tools, output format, risk policy, approval rules, and tests."
      />
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Published and draft playbooks" icon={BrainCircuit} label="Skills" value={rows.length} />
        <MetricCard detail="Mapped from contact drivers" icon={GitBranch} label="Driver links" value={rows.reduce((sum, row) => sum + listOf(row, "drivers").length, 0)} />
        <MetricCard detail="Approval rules declared" icon={ShieldCheck} label="Policy rules" value={rows.reduce((sum, row) => sum + listOf(row, "approvalRules").length, 0)} />
        <MetricCard detail="Preview test inventory" icon={CheckCircle2} label="Test cases" value={rows.reduce((sum, row) => sum + numberOf(row, ["testCases"]), 0)} />
      </section>
      <div className="grid gap-3 xl:grid-cols-2">
        {rows.map((row) => (
          <Panel
            action={<StatusPill status={textOf(row, ["status"], "Draft")}>{textOf(row, ["status"], "Draft")}</StatusPill>}
            key={textOf(row, ["id"], textOf(row, ["name"], "skill"))}
            title={textOf(row, ["name"], "Skill")}
            eyebrow={textOf(row, ["version"], "v0")}
          >
            <div className="space-y-3 p-3">
              <p className="text-sm leading-6 text-muted-foreground">{textOf(row, ["description"], "")}</p>
              <div className="grid gap-3 text-xs md:grid-cols-2">
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Triggered by</div>
                  <InlineList values={listOf(row, "drivers")} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Used by</div>
                  <InlineList values={listOf(row, "agents")} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Allowed tools</div>
                  <InlineList values={listOf(row, "allowedTools")} />
                </div>
                <div>
                  <div className="mb-1 font-mono uppercase text-muted-foreground">Approval rules</div>
                  <InlineList values={listOf(row, "approvalRules")} />
                </div>
              </div>
            </div>
          </Panel>
        ))}
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
              <div className="grid gap-3 text-xs md:grid-cols-3">
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

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="Tools"
        description="Approved callable actions agents can use. Write, send, delete, payment, refund, legal, and customer-facing tools are approval-gated by default."
      />
      <Panel title="Tool Registry" eyebrow="Callable actions" action={<StatusPill tone="warning">Approval-gated writes</StatusPill>}>
        <DataTable
          columns={[
            {
              key: "tool",
              label: "Tool",
              render: (row) => (
                <div>
                  <div>{textOf(row, ["tool", "name"], "tool")}</div>
                  <div className="mt-1 text-xs font-normal text-muted-foreground">{textOf(row, ["description"], "")}</div>
                </div>
              ),
            },
            { key: "provider", label: "Provider", render: (row) => textOf(row, ["system", "provider"], "Agent Studio") },
            { key: "type", label: "Type", render: (row) => textOf(row, ["mode"], "Server-side read") },
            { key: "status", label: "Status", render: (row) => <StatusPill status={textOf(row, ["health", "status"], "Preview")}>{textOf(row, ["health", "status"], "Preview")}</StatusPill> },
            { key: "risk", label: "Risk", render: (row) => Boolean(row.requiresApproval) ? "High" : "Low" },
            { key: "approval", label: "Approval", render: (row) => Boolean(row.requiresApproval) ? "Required" : "Not required" },
          ]}
          rows={rows}
        />
      </Panel>
    </div>
  );
}

export function McpServersConsole({ servers }: { servers: unknown }) {
  const rows = asArray(servers).map(asRecord);

  return (
    <div className="space-y-3">
      <CatalogIntro
        title="MCP Servers"
        description="External capability servers connected to Sagad. In public preview these are visible as permissioned roadmap records, not browser-direct providers."
      />
      <div className="grid gap-3 xl:grid-cols-3">
        {rows.map((row) => (
          <Panel
            action={<StatusPill status={textOf(row, ["status"], "Planned")}>{textOf(row, ["status"], "Planned")}</StatusPill>}
            key={textOf(row, ["id"], textOf(row, ["name"], "mcp"))}
            title={textOf(row, ["name"], "MCP Server")}
            eyebrow={textOf(row, ["transport"], "planned")}
          >
            <div className="space-y-3 p-3">
              <p className="text-sm leading-6 text-muted-foreground">{textOf(row, ["detail"], "")}</p>
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="border border-border bg-surface-2 p-2"><b>{numberOf(row, ["toolsCount"])}</b><br />Tools</div>
                <div className="border border-border bg-surface-2 p-2"><b>{numberOf(row, ["resourcesCount"])}</b><br />Resources</div>
                <div className="border border-border bg-surface-2 p-2"><b>{numberOf(row, ["promptsCount"])}</b><br />Prompts</div>
              </div>
              <InlineList values={listOf(row, "tools")} />
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
