import { Bot, CheckCircle2, GitBranch, ShieldCheck, Workflow } from "lucide-react";
import { CodeBlock, MetricCard, Panel, StatusPill, TerminalBlock } from "@/components/product/product-ui";

const workflows = [
  {
    name: "Support Agent",
    lane: "Support",
    status: "Healthy",
    threshold: "0.88 auto-send",
    detail: "Handles order status, account support, refunds, and tool recovery.",
  },
  {
    name: "Sales Agent",
    lane: "Sales",
    status: "Healthy",
    threshold: "0.90 auto-send",
    detail: "Handles qualification, sizing, pricing, and next-step suggestions.",
  },
  {
    name: "Refund policy flow",
    lane: "Policy",
    status: "Needs review",
    threshold: "Approval required",
    detail: "Holds unclear sale-item, warranty, and exception cases for supervisors.",
  },
  {
    name: "Lead qualification flow",
    lane: "Revenue",
    status: "Ready",
    threshold: "0.86 auto-send",
    detail: "Classifies lead stage and drafts next questions with CRM context.",
  },
  {
    name: "Escalation flow",
    lane: "Human takeover",
    status: "Watch",
    threshold: "Always gated",
    detail: "Routes angry customers, failed tools, and manager requests to people.",
  },
];

export function WorkflowConsole() {
  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Agent and policy routes" icon={Workflow} label="Workflows" value={workflows.length} />
        <MetricCard detail="Server-side tool boundary" icon={ShieldCheck} label="Approval gates" value="3" />
        <MetricCard detail="Sales and support agents" icon={Bot} label="Agents" value="2" />
        <MetricCard detail="Inspectable audit events" icon={GitBranch} label="Trace points" value="9" />
      </section>

      <Panel action={<StatusPill tone="good">Router ready</StatusPill>} title="Workflow Runs" eyebrow="Agent routing">
        <div className="divide-y divide-border">
          {workflows.map((workflow) => (
            <div
              className="grid gap-4 px-4 py-4 xl:grid-cols-[minmax(0,1fr)_220px_180px]"
              key={workflow.name}
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-semibold text-foreground">{workflow.name}</div>
                  <StatusPill status={workflow.status}>{workflow.status}</StatusPill>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{workflow.detail}</p>
              </div>
              <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="text-[11px] uppercase tracking-[0.08em]">Lane</div>
                <div className="mt-1 font-semibold text-foreground">{workflow.lane}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="text-[11px] uppercase tracking-[0.08em]">Threshold</div>
                <div className="mt-1 font-semibold text-foreground">{workflow.threshold}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <section className="grid gap-4 xl:grid-cols-2">
        <TerminalBlock
          lines={[
            { label: "$ ", text: "sagados route --message inbound" },
            { label: "OK ", text: "classifier selected support_agent" },
            { label: "OK ", text: "knowledge.retrieve_context attached 3 sources" },
            { label: "HITL ", text: "confidence below threshold, approval requested" },
          ]}
        />
        <CodeBlock
          code={`{
  "state": "pending_approval",
  "agent": "Support Agent",
  "confidence": 0.64,
  "approval_gate": "sale_item_refund_exception",
  "writes": "blocked_until_supervisor_decision"
}`}
        />
      </section>

      <div className="rounded-lg border border-border bg-card p-4 text-sm leading-6 text-muted-foreground">
        <CheckCircle2 aria-hidden="true" className="mr-2 inline size-4 text-[var(--accent-text)]" />
        Browser code only displays workflow state. Provider credentials, model calls, CRM writes, Chatwoot sends, and MCP access stay behind Agent Studio.
      </div>
    </div>
  );
}
