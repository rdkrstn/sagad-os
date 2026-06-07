import { Activity, PlugZap, ServerCog, ShieldCheck } from "lucide-react";
import { MetricCard, Panel, SourcePill, StatusPill } from "@/components/product/product-ui";
import { asArray, asRecord, textOf } from "@/components/ui/data-access";

export function IntegrationsHealthConsole({ connections }: { connections: unknown }) {
  const rows = asArray(connections).map(asRecord);
  const connected = rows.filter((row) =>
    ["connected", "ready", "healthy"].some((status) =>
      textOf(row, ["visibilityStatus", "status"], "").toLowerCase().includes(status),
    ),
  ).length;
  const planned = rows.filter((row) =>
    textOf(row, ["visibilityStatus", "status"], "").toLowerCase().includes("planned"),
  ).length;

  return (
    <div className="space-y-3">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Channels, CRMs, knowledge, observability" icon={PlugZap} label="Adapters" value={rows.length} />
        <MetricCard detail="Confirmed ready/connected" icon={Activity} label="Connected" value={connected} />
        <MetricCard detail="Server-side credentials only" icon={ShieldCheck} label="Browser secrets" value="0" />
        <MetricCard detail="Roadmap-visible, not faked" icon={ServerCog} label="Planned" value={planned} />
      </section>

      <Panel action={<StatusPill tone="info">Health only</StatusPill>} title="Adapters Health" eyebrow="Provider boundary">
        <div className="divide-y divide-border">
          {rows.map((row) => (
            <div
              className="grid gap-3 px-3 py-3 xl:grid-cols-[minmax(0,1fr)_180px_180px_180px]"
              key={`${textOf(row, ["name", "provider"], "adapter")}-${textOf(row, ["kind", "entityKind"], "")}`}
            >
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="font-semibold text-foreground">
                    {textOf(row, ["name", "provider"], "Adapter")}
                  </div>
                  <SourcePill>{textOf(row, ["kind", "entityKind"], "Adapter")}</SourcePill>
                  <StatusPill status={textOf(row, ["visibilityStatus", "status"], "Preview")}>
                    {textOf(row, ["visibilityStatus", "status"], "Preview")}
                  </StatusPill>
                </div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {textOf(row, ["detail"], "Configured through server-side Agent Studio adapter.")}
                </p>
              </div>
              <div className="border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="font-mono text-[10px] uppercase">Mode</div>
                <div className="mt-1 font-semibold text-foreground">{textOf(row, ["mode", "api_mode"], "Preview")}</div>
              </div>
              <div className="border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="font-mono text-[10px] uppercase">Access</div>
                <div className="mt-1 font-semibold text-foreground">{textOf(row, ["access"], "Approval-gated")}</div>
              </div>
              <div className="border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="font-mono text-[10px] uppercase">Boundary</div>
                <div className="mt-1 font-semibold text-foreground">{textOf(row, ["boundary"], "Server-side")}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <div className="border border-border bg-card p-3 text-sm leading-6 text-muted-foreground">
        No browser-direct provider calls: credentials, Chatwoot sends, Twenty reads/writes, LangSmith, model gateway, and future MCP access stay behind Sagad APIs or Agent Studio.
      </div>
    </div>
  );
}
