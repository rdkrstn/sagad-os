import { ClipboardList, History, MapPin, Users } from "lucide-react";
import {
  MetricCard,
  Panel,
  SourcePill,
  StatusPill,
} from "@/components/product/product-ui";
import { asArray, asRecord, textOf } from "@/components/ui/data-access";

export function CustomerConsole({ customers }: { customers: unknown }) {
  const rows = asArray(customers).map(asRecord);
  const highRisk = rows.filter((row) =>
    textOf(row, ["risk"], "").toLowerCase().includes("high"),
  ).length;

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard detail="Known CRM context records" icon={Users} label="Customers" value={rows.length} />
        <MetricCard detail="Open follow-up tasks" icon={ClipboardList} label="Tasks" value={rows.reduce((total, row) => total + Number(row.openTasks ?? 0), 0)} />
        <MetricCard detail="Escalation or refund risk" icon={History} label="Risk reviews" value={highRisk} />
        <MetricCard detail="Markets represented" icon={MapPin} label="Locations" value={new Set(rows.map((row) => textOf(row, ["city"], ""))).size} />
      </section>

      <Panel
        action={<StatusPill tone="info">Twenty CRM context</StatusPill>}
        title="Customer Context"
        eyebrow="CRM"
      >
        <div className="divide-y divide-border">
          {rows.map((row) => {
            const name = textOf(row, ["name", "customerName"], "Customer");
            return (
              <div
                className="grid gap-4 px-4 py-4 xl:grid-cols-[minmax(0,1fr)_280px]"
                key={textOf(row, ["id"], name)}
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="font-semibold text-foreground">{name}</div>
                    <StatusPill status={textOf(row, ["risk"], "Normal")}>
                      {textOf(row, ["risk"], "Normal")}
                    </StatusPill>
                    <SourcePill>{textOf(row, ["stage", "leadStage"], "Unknown stage")}</SourcePill>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {textOf(row, ["lastConversationSummary"], "No current conversation summary.")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {asArray<string>(row.tags).slice(0, 4).map((tag) => (
                      <SourcePill key={tag}>{tag}</SourcePill>
                    ))}
                  </div>
                </div>
                <div className="grid gap-2 rounded-lg border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
                  <div className="flex justify-between gap-3">
                    <span>City</span>
                    <span className="font-medium text-foreground">{textOf(row, ["city"], "n/a")}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span>Owner</span>
                    <span className="font-medium text-foreground">{textOf(row, ["owner"], "Ops")}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span>Last service</span>
                    <span className="text-right font-medium text-foreground">{textOf(row, ["lastService"], "n/a")}</span>
                  </div>
                  <div className="flex justify-between gap-3">
                    <span>Open tasks</span>
                    <span className="font-medium text-foreground">{textOf(row, ["openTasks"], "0")}</span>
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
