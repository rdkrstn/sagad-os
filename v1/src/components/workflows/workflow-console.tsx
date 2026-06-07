import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  GitBranch,
  Network,
  Route,
  ShieldCheck,
  Workflow,
  Wrench,
} from "lucide-react";
import { AgentStudioRelationshipStrip } from "@/components/agent-studio/agent-studio-console";
import {
  CodeBlock,
  MetricCard,
  Panel,
  SourcePill,
  StatusPill,
  TerminalBlock,
} from "@/components/product/product-ui";

const workflows = [
  {
    name: "Support Resolution Workflow",
    driver: "Order status / refund policy",
    lane: "Support",
    status: "Healthy",
    agent: "Support Agent",
    skill: "Refund Resolver + Order Status Lookup",
    graph: "Default Support Graph v0.1.4",
    toolsMcp: ["crm.lookup_contact", "knowledge.search", "chatwoot.draft_reply"],
    approval: "Sale-item, refund, failed tool, low trust",
    auditTrace: "Audit log + LangSmith trace",
    threshold: "0.88 auto-send",
    detail: "Handles order status, account support, refunds, and tool recovery.",
  },
  {
    name: "Lead Qualification Workflow",
    driver: "Sales sizing / pricing question",
    lane: "Sales",
    status: "Healthy",
    agent: "Sales Agent",
    skill: "Sales Sizing Assistant",
    graph: "Sales Qualification Graph",
    toolsMcp: ["crm.lookup_contact", "knowledge.search", "chatwoot.draft_reply"],
    approval: "Discount request, policy exception",
    auditTrace: "Audit log + trace metadata",
    threshold: "0.90 auto-send",
    detail: "Handles qualification, sizing, pricing, and next-step suggestions.",
  },
  {
    name: "Refund Exception Workflow",
    driver: "Refund or cancellation",
    lane: "Policy",
    status: "Needs review",
    agent: "Support Agent",
    skill: "Refund Resolver",
    graph: "Default Support Graph v0.1.4",
    toolsMcp: ["crm.lookup_contact", "knowledge.search", "chatwoot.draft_reply"],
    approval: "Always required for unclear sale-item cases",
    auditTrace: "Supervisor decision + trace",
    threshold: "Approval required",
    detail: "Holds unclear sale-item, warranty, and exception cases for supervisors.",
  },
  {
    name: "Escalation Workflow",
    driver: "Angry customer / manager request",
    lane: "Human takeover",
    status: "Watch",
    agent: "Escalation Agent",
    skill: "Angry Customer De-escalation",
    graph: "Default Support Graph v0.1.4",
    toolsMcp: ["knowledge.search", "chatwoot.draft_reply", "chatwoot.send_message"],
    approval: "Always gated",
    auditTrace: "Human takeover audit event",
    threshold: "Always gated",
    detail: "Routes angry customers, failed tools, and manager requests to people.",
  },
];

function InlineList({ values }: { values: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {values.map((value) => (
        <SourcePill key={value}>{value}</SourcePill>
      ))}
    </div>
  );
}

export function WorkflowConsole() {
  return (
    <div className="space-y-4">
      <AgentStudioRelationshipStrip active="workflow" />
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Driver-to-agent routes" icon={Workflow} label="Workflows" value={workflows.length} />
        <MetricCard detail="Sales, support, escalation" icon={Bot} label="Agents mapped" value="3" />
        <MetricCard detail="Reusable playbooks selected" icon={BrainCircuit} label="Skills mapped" value="4" />
        <MetricCard detail="Writes held by policy" icon={ShieldCheck} label="Approval gates" value="On" />
      </section>

      <Panel action={<StatusPill tone="good">Router ready</StatusPill>} title="Workflow Relationship Map" eyebrow="Driver -> audit/trace">
        <div className="divide-y divide-border">
          {workflows.map((workflow) => (
            <div
              className="grid gap-4 px-4 py-4"
              key={workflow.name}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="font-semibold text-foreground">{workflow.name}</div>
                    <StatusPill status={workflow.status}>{workflow.status}</StatusPill>
                  </div>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{workflow.detail}</p>
                </div>
                <StatusPill tone="info">{workflow.lane}</StatusPill>
              </div>

              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                <div className="border border-border bg-surface-2 p-3 text-xs">
                  <div className="mb-2 flex items-center gap-2 font-mono uppercase text-muted-foreground">
                    <Route aria-hidden="true" size={14} />
                    Contact Driver
                  </div>
                  <div className="font-semibold text-foreground">{workflow.driver}</div>
                </div>
                <div className="border border-border bg-surface-2 p-3 text-xs">
                  <div className="mb-2 flex items-center gap-2 font-mono uppercase text-muted-foreground">
                    <Bot aria-hidden="true" size={14} />
                    Agent
                  </div>
                  <div className="font-semibold text-foreground">{workflow.agent}</div>
                </div>
                <div className="border border-border bg-surface-2 p-3 text-xs">
                  <div className="mb-2 flex items-center gap-2 font-mono uppercase text-muted-foreground">
                    <BrainCircuit aria-hidden="true" size={14} />
                    Skill
                  </div>
                  <div className="font-semibold text-foreground">{workflow.skill}</div>
                </div>
                <div className="border border-border bg-surface-2 p-3 text-xs">
                  <div className="mb-2 flex items-center gap-2 font-mono uppercase text-muted-foreground">
                    <GitBranch aria-hidden="true" size={14} />
                    Graph
                  </div>
                  <div className="font-semibold text-foreground">{workflow.graph}</div>
                </div>
                <div className="border border-border bg-surface-2 p-3 text-xs xl:col-span-2">
                  <div className="mb-2 flex items-center gap-2 font-mono uppercase text-muted-foreground">
                    <Wrench aria-hidden="true" size={14} />
                    Tools / MCP
                  </div>
                  <InlineList values={workflow.toolsMcp} />
                </div>
                <div className="border border-border bg-surface-2 p-3 text-xs">
                  <div className="mb-2 flex items-center gap-2 font-mono uppercase text-muted-foreground">
                    <ShieldCheck aria-hidden="true" size={14} />
                    Approval
                  </div>
                  <div className="font-semibold text-foreground">{workflow.approval}</div>
                </div>
                <div className="border border-border bg-surface-2 p-3 text-xs">
                  <div className="mb-2 flex items-center gap-2 font-mono uppercase text-muted-foreground">
                    <Network aria-hidden="true" size={14} />
                    Audit / Trace
                  </div>
                  <div className="font-semibold text-foreground">{workflow.auditTrace}</div>
                </div>
              </div>

              <div className="grid gap-3 text-xs md:grid-cols-2">
                <div className="rounded-md border border-border bg-background p-3 text-muted-foreground">
                  <div className="font-mono uppercase">Workflow lane</div>
                  <div className="mt-1 font-semibold text-foreground">{workflow.lane}</div>
                </div>
                <div className="rounded-md border border-border bg-background p-3 text-muted-foreground">
                  <div className="font-mono uppercase">Threshold</div>
                  <div className="mt-1 font-semibold text-foreground">{workflow.threshold}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <TerminalBlock
          lines={[
            { label: "$ ", text: "sagados route --message inbound" },
            { label: "OK ", text: "driver detected: refund_or_cancellation" },
            { label: "OK ", text: "workflow selected: Support Resolution Workflow" },
            { label: "OK ", text: "agent selected: Support Agent / Refund Resolver" },
            { label: "HITL ", text: "approval requested before send" },
          ]}
        />
        <CodeBlock
          code={`{
  "driver": "refund_or_cancellation",
  "workflow": "Support Resolution Workflow",
  "agent": "Support Agent",
  "skill": "Refund Resolver",
  "graph": "Default Support Graph v0.1.4",
  "tools": ["crm.lookup_contact", "knowledge.search"],
  "approval": "required",
  "trace": "preview-chatwoot_1780838552005"
}`}
        />
      </section>

      <div className="rounded-lg border border-border bg-card p-4 text-sm leading-6 text-muted-foreground">
        <CheckCircle2 aria-hidden="true" className="mr-2 inline size-4 text-[var(--accent-text)]" />
        Workflows are operating routes. Graphs are orchestration definitions inside those routes.
        Provider credentials, model calls, CRM writes, Chatwoot sends, and MCP access stay behind Agent Studio.
      </div>
    </div>
  );
}
