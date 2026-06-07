import { FileText, History, ShieldCheck, Wrench } from "lucide-react";
import { MetricCard, Panel, SourcePill, StatusPill } from "@/components/product/product-ui";
import { asArray, asRecord, textOf } from "@/components/ui/data-access";

export function AuditLogConsole({ events }: { events: unknown }) {
  const rows = asArray(events).map(asRecord);

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Drafts, approvals, sends" icon={History} label="Audit events" value={rows.length} />
        <MetricCard detail="Knowledge retrievals" icon={FileText} label="Source events" value={rows.filter((row) => textOf(row, ["event"], "").toLowerCase().includes("knowledge")).length} />
        <MetricCard detail="Tool and provider results" icon={Wrench} label="Tool calls" value={rows.filter((row) => textOf(row, ["event"], "").toLowerCase().includes("tool")).length} />
        <MetricCard detail="Approval gates" icon={ShieldCheck} label="Approval events" value={rows.filter((row) => textOf(row, ["event"], "").toLowerCase().includes("approval")).length} />
      </section>

      <Panel action={<StatusPill tone="neutral">{rows.length} events</StatusPill>} title="Audit Log" eyebrow="Timeline">
        <div className="divide-y divide-border">
          {rows.map((row) => (
            <div
              className="grid gap-4 px-4 py-4 xl:grid-cols-[220px_minmax(0,1fr)_180px]"
              key={textOf(row, ["id"], `${textOf(row, ["event"], "event")}-${textOf(row, ["createdAt"], "")}`)}
            >
              <div className="grid content-start gap-2">
                <StatusPill status={textOf(row, ["status"], "Logged")}>
                  {textOf(row, ["status"], "Logged")}
                </StatusPill>
                <div className="font-mono text-[11px] text-muted-foreground">
                  {textOf(row, ["createdAt"], "n/a")}
                </div>
              </div>
              <div>
                <div className="font-semibold text-foreground">{textOf(row, ["event"], "Audit event")}</div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{textOf(row, ["detail"], "No detail recorded.")}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <SourcePill>{textOf(row, ["customerName"], "Platform")}</SourcePill>
                  <SourcePill>{textOf(row, ["conversationId"], "system")}</SourcePill>
                </div>
              </div>
              <div className="rounded-lg border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                <div className="text-[11px] uppercase tracking-[0.08em]">Actor</div>
                <div className="mt-1 font-semibold text-foreground">{textOf(row, ["actor"], "SagadOS")}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
