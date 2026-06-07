import {
  AlertTriangle,
  Bot,
  FileText,
  GitBranch,
  Inbox,
  MessageSquareText,
  Send,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import {
  CodeBlock,
  MetricCard,
  Panel,
  StatusPill,
  TerminalBlock,
} from "@/components/product/product-ui";
import {
  asArray,
  asRecord,
  nestedArray,
  numberOf,
  textOf,
} from "@/components/ui/data-access";

function statusForHealth(status: string): "good" | "warning" | "info" {
  const normalized = status.toLowerCase();
  if (
    normalized.includes("degraded") ||
    normalized.includes("watch") ||
    normalized.includes("unconfigured")
  ) {
    return "warning";
  }
  if (
    normalized.includes("dry-run") ||
    normalized.includes("preview") ||
    normalized.includes("mock") ||
    normalized.includes("optional") ||
    normalized.includes("planned")
  ) {
    return "info";
  }
  return "good";
}

function dotClassForHealth(status: string): string {
  const tone = statusForHealth(status);
  if (tone === "warning") {
    return "bg-warning";
  }
  if (tone === "info") {
    return "bg-info";
  }
  return "bg-[var(--accent)]";
}

export function CommandCenter({
  data,
  supervisorPods,
}: {
  data: unknown;
  supervisorPods: unknown;
}) {
  const dashboard = asRecord(data);
  const metrics = asRecord(dashboard.metrics);
  const channelRows = nestedArray(dashboard, ["channelHealth"]).map(asRecord);
  const queueRows = nestedArray(dashboard, ["queueHealth", "activeQueues"]).map(asRecord);
  const pods =
    asArray(supervisorPods).length > 0
      ? asArray(supervisorPods).map(asRecord)
      : nestedArray(dashboard, ["supervisorPods", "pods"]).map(asRecord);
  const conversations = asArray(dashboard.conversations).map(asRecord);
  const integrationSource = textOf(dashboard, ["integrationSource", "source"], "mock");
  const pendingApprovals = numberOf(metrics, ["needsApproval", "approvalRequired"]);
  const escalations = numberOf(metrics, ["escalated"]);
  const rejections = numberOf(metrics, ["rejected"]);

  const kpis = [
    {
      label: "Messages received",
      value: numberOf(metrics, ["messagesReceived", "totalConversations"]),
      detail: "Inbound customer messages",
      delta: "+12%",
      icon: MessageSquareText,
    },
    {
      label: "AI drafted replies",
      value: numberOf(metrics, ["aiDrafted", "aiDraftedResponses"]),
      detail: "Prepared by Sales/Support agents",
      delta: "+8%",
      icon: Bot,
    },
    {
      label: "Auto-sent replies",
      value: numberOf(metrics, ["autoSent", "autoSentResponses"]),
      detail: "High-confidence sends",
      delta: "+5%",
      icon: Send,
    },
    {
      label: "Pending approvals",
      value: pendingApprovals,
      detail: "Supervisor review queue",
      icon: Inbox,
    },
    {
      label: "Escalations",
      value: escalations,
      detail: "Human takeover or manager review",
      icon: ShieldCheck,
    },
    {
      label: "Rejections",
      value: rejections,
      detail: "Blocked before send",
      icon: XCircle,
    },
  ];

  const healthRows = [
    ["Agent Studio", integrationSource === "agent-studio" ? "Healthy" : "Mock fallback", "Graph orchestration and approval APIs"],
    ["Chatwoot adapter", channelRows[0] ? textOf(channelRows[0], ["status", "health"], "Ready") : "Ready", "Intake and approved delivery"],
    ["Twenty CRM adapter", "Dry-run", "External CRM context, server-side only"],
    ["Knowledge index", "Healthy", "Approved KB/SOP retrieval"],
    ["Queue worker", queueRows.length > 0 ? "Healthy" : "Preview", "Approval and retry processing"],
    ["Model gateway / LiteLLM", "Ready", "Provider access remains server-side"],
  ] as const;

  const recentActivity =
    conversations
      .flatMap((conversation) =>
        nestedArray(conversation, ["decisionTrail", "aiDecisionTrail"]).map((event) => ({
          conversation,
          event: asRecord(event),
        })),
      )
      .slice(-5)
      .reverse()
      .map(({ conversation, event }) => [
        textOf(event, ["step", "label"], "Audit event"),
        textOf(event, ["rationale", "detail"], textOf(conversation, ["summary"], "")),
        textOf(conversation, ["age", "waitTime"], "now"),
      ]);

  const workflowRuns = [
    ["Support Agent", `${conversations.filter((row) => textOf(row, ["assignedTo", "intent"], "").toLowerCase().includes("support")).length} runs`, "Healthy"],
    ["Sales Agent", `${conversations.filter((row) => textOf(row, ["assignedTo", "intent"], "").toLowerCase().includes("sales") || textOf(row, ["intent"], "").toLowerCase().includes("pricing")).length} runs`, "Ready"],
    ["Refund policy flow", `${conversations.filter((row) => textOf(row, ["intent", "reason"], "").toLowerCase().includes("refund")).length} held`, "Needs review"],
    ["Lead qualification flow", `${conversations.filter((row) => textOf(row, ["intent", "driver"], "").toLowerCase().includes("pricing")).length} runs`, "Healthy"],
    ["Escalation flow", `${escalations} escalated`, escalations > 0 ? "Watch" : "Ready"],
  ] as const;
  const automationTrend = [48, 56, 52, 68, 61, 74, 72, 82, 76, 88];

  return (
    <div className="space-y-4">
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {kpis.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <Panel
          action={<StatusPill tone="good">Healthy</StatusPill>}
          title="Automation Trend"
          eyebrow="Today"
          bodyClassName="p-4"
        >
          <div
            aria-label={`Automation trend by interval: ${automationTrend.join(", ")}`}
            className="relative h-56 overflow-hidden rounded-lg border border-border bg-surface-2"
            role="img"
          >
            <div className="absolute inset-x-0 top-1/4 border-t border-border" />
            <div className="absolute inset-x-0 top-1/2 border-t border-border" />
            <div className="absolute inset-x-0 top-3/4 border-t border-border" />
            <div className="absolute inset-x-5 bottom-5 top-6 flex items-end gap-3">
              {automationTrend.map((height, index) => (
                <div
                  aria-hidden="true"
                  className="min-w-5 flex-1 rounded-t-sm bg-[var(--accent)] opacity-90"
                  key={index}
                  style={{ height: `${height}%` }}
                />
              ))}
            </div>
          </div>
        </Panel>

        <Panel
          action={<StatusPill tone={integrationSource === "agent-studio" ? "good" : "info"}>{integrationSource === "agent-studio" ? "Live health" : "Preview health"}</StatusPill>}
          title="System Health"
          eyebrow="Adapters"
        >
          <div className="grid gap-2 p-4">
            {healthRows.map(([name, status, detail]) => {
              const tone = statusForHealth(status);

              return (
                <div
                  className="flex items-start gap-3 rounded-md border border-border bg-surface-2 p-3"
                  key={name}
                >
                  <span className={`mt-1 size-2 rounded-full ${dotClassForHealth(status)}`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-foreground">{name}</div>
                      <StatusPill tone={tone}>{status}</StatusPill>
                    </div>
                    <div className="mt-1 text-xs leading-5 text-muted-foreground">
                      {detail}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel
          action={<StatusPill tone="warning">{pendingApprovals} open</StatusPill>}
          title="Recent Activity"
          eyebrow="Audit feed"
        >
          <div className="divide-y divide-border">
            {recentActivity.map(([event, detail, time]) => (
              <div className="grid gap-1 px-4 py-3" key={event}>
                <div className="flex items-center justify-between gap-3">
                  <div className="font-semibold text-foreground">{event}</div>
                  <span className="font-mono text-[11px] text-muted-foreground">
                    {time}
                  </span>
                </div>
                <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          action={<StatusPill tone="info">{pods.length} pod</StatusPill>}
          title="Workflow Runs"
          eyebrow="Routing"
        >
          <div className="divide-y divide-border">
            {workflowRuns.map(([name, volume, status]) => (
              <div
                className="grid gap-2 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-center"
                key={name}
              >
                <div className="font-semibold text-foreground">{name}</div>
                <div className="text-xs text-muted-foreground">{volume}</div>
                <StatusPill status={status}>{status}</StatusPill>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <TerminalBlock
          lines={[
            { label: "$ ", text: "sagados status" },
            { text: "Environment: local preview" },
            { label: "OK ", text: "Agent Studio adapter boundary intact" },
            { label: "OK ", text: "Chatwoot sends require approval endpoint" },
            { label: "OK ", text: "Knowledge index healthy" },
            { label: "OK ", text: "Approval queue listening" },
          ]}
        />
        <CodeBlock
          code={`POST /api/conversations/:id/approve-send
{
  "approved": true,
  "edited_reply": "Supervisor-approved reply body",
  "reason": "High-risk writes stay behind approval gates"
}`}
        />
      </section>

      <section className="grid gap-3 md:grid-cols-3">
        {[
          {
            label: "Golden loop",
            detail: `${conversations.length} demo or live conversations move from intake to classification, draft, confidence, approval, and audit.`,
            icon: GitBranch,
          },
          {
            label: "Approval gate",
            detail: "Low confidence, policy ambiguity, failed tools, and escalations stay visible to supervisors.",
            icon: AlertTriangle,
          },
          {
            label: "Audit trail",
            detail: "Every draft, retrieved source, tool call, approval decision, and send outcome is inspectable.",
            icon: FileText,
          },
        ].map(({ label, detail, icon: Icon }) => (
          <div className="rounded-lg border border-border bg-card p-4" key={label}>
            <Icon aria-hidden="true" className="mb-3 size-4 text-[var(--accent-text)]" />
            <div className="font-semibold text-foreground">{label}</div>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
