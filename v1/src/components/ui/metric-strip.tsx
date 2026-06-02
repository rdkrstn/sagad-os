import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export type MetricItem = {
  label: string;
  value: string | number;
  delta?: string;
  detail?: string;
  icon?: LucideIcon;
};

export function MetricStrip({ items }: { items: MetricItem[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => {
        const Icon = item.icon;

        return (
          <Card
            className="gap-0 py-0 shadow-xs"
            key={item.label}
          >
            <CardContent className="p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-muted-foreground">
                  {item.label}
                </p>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-semibold tabular-nums text-foreground">
                    {item.value}
                  </span>
                  {item.delta ? (
                    <span className="text-xs font-medium text-muted-foreground">
                      {item.delta}
                    </span>
                  ) : null}
                </div>
              </div>
              {Icon ? (
                <span className="rounded-md border bg-muted/60 p-2 text-muted-foreground">
                  <Icon aria-hidden="true" size={16} />
                </span>
              ) : null}
            </div>
            {item.detail ? (
              <p className="mt-3 truncate text-xs text-muted-foreground">
                {item.detail}
              </p>
            ) : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
