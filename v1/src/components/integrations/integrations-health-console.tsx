import { Activity, PlugZap, ServerCog, ShieldCheck } from "lucide-react";
import { MetricCard, Panel, SourcePill, StatusPill } from "@/components/product/product-ui";
import { asArray, asRecord, textOf } from "@/components/ui/data-access";

const plannedIntegrations = [
  {
    name: "LiteLLM",
    kind: "Model gateway",
    status: "Ready",
    owner: "Agent Studio",
    detail: "Provider routing and credentials remain server-side.",
  },
  {
    name: "LangSmith",
    kind: "Observability",
    status: "Optional",
    owner: "Agent Studio",
    detail: "Graph, tool, approval, and failure traces when env vars are configured.",
  },
  {
    name: "Uptime Kuma",
    kind: "Monitoring",
    status: "Planned",
    owner: "Infrastructure",
    detail: "External uptime dashboard placeholder for self-hosted deployments.",
  },
  {
    name: "MCP / FastMCP",
    kind: "Future tool facade",
    status: "Planned",
    owner: "Agent Studio",
    detail: "Future provider-neutral tool layer behind approval and audit policy.",
  },
];

export function IntegrationsHealthConsole({ connections }: { connections: unknown }) {
  const liveRows = asArray(connections).map(asRecord);
  const rows = [
    ...liveRows.map((row) => ({
      name: textOf(row, ["name", "provider"], "Integration"),
      kind: textOf(row, ["kind"], "Adapter"),
      status: textOf(row, ["status"], "Unconfigured"),
      owner: "Agent Studio",
      detail: textOf(row, ["detail"], "Configured through server-side Agent Studio adapter."),
    })),
    ...plannedIntegrations,
  ];
  const connected = rows.filter((row) =>
    ["ready", "healthy", "optional"].some((status) =>
      row.status.toLowerCase().includes(status),
    ),
  ).length;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Operator-facing adapter rows" icon={PlugZap} label="Integrations" value={rows.length} />
        <MetricCard detail="Ready or optional services" icon={Activity} label="Ready" value={connected} />
        <MetricCard detail="Server-side credentials only" icon={ShieldCheck} label="Browser secrets" value="0" />
        <MetricCard detail="Planned platform services" icon={ServerCog} label="Roadmap" value={plannedIntegrations.length} />
      </section>

      <Panel action={<StatusPill tone="info">Health only</StatusPill>} title="Integrations Health" eyebrow="Operator view">
        <div className="divide-y divide-border">
          {rows.map((row) => (
            <div
              className="grid gap-4 px-4 py-4 xl:grid-cols-[minmax(0,1fr)_220px_180px]"
              key={`${row.name}-${row.kind}`}
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-semibold text-foreground">{row.name}</div>
                  <SourcePill>{row.kind}</SourcePill>
                  <StatusPill status={row.status}>{row.status}</StatusPill>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{row.detail}</p>
              </div>
              <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="text-[11px] uppercase tracking-[0.08em]">Owner</div>
                <div className="mt-1 font-semibold text-foreground">{row.owner}</div>
              </div>
              <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="text-[11px] uppercase tracking-[0.08em]">Boundary</div>
                <div className="mt-1 font-semibold text-foreground">Server-side</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="rounded-lg border border-border bg-card p-4 text-sm leading-6 text-muted-foreground">
        Credential setup, webhook samples, DTO contracts, raw JSON, and provider diagnostics belong under Settings Advanced or the legacy admin setup surface, not this operator health screen.
      </div>
    </div>
  );
}
