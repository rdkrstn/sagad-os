import type { ReactNode } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

export type Column<T> = {
  key: string;
  label: string;
  className?: string;
  render: (row: T) => ReactNode;
};

export function DataTable<T>({
  columns,
  rows,
  emptyLabel = "No records available.",
}: {
  columns: Column<T>[];
  rows: T[];
  emptyLabel?: string;
}) {
  return (
    <>
      <div className="divide-y divide-border md:hidden">
        {rows.length > 0 ? (
          rows.map((row, rowIndex) => (
            <div className="grid gap-3 bg-card p-3" key={rowIndex}>
              {columns.map((column) => (
                <div className="min-w-0" key={column.key}>
                  {column.label ? (
                    <div className="mb-1 text-[10px] font-semibold uppercase tracking-[0.06em] text-muted-foreground">
                      {column.label}
                    </div>
                  ) : null}
                  <div
                    className={cn(
                      "min-w-0 break-words text-xs text-foreground",
                      column.className,
                    )}
                  >
                    {column.render(row)}
                  </div>
                </div>
              ))}
            </div>
          ))
        ) : (
          <div className="px-3 py-8 text-center text-sm text-muted-foreground">
            {emptyLabel}
          </div>
        )}
      </div>

      <div className="hidden overflow-x-auto md:block">
      <Table className="min-w-full text-xs">
        <TableHeader>
          <TableRow className="sticky top-0 z-10 bg-surface-2 font-mono text-[10px] uppercase">
            {columns.map((column) => (
              <TableHead
                className={cn(
                  "h-8 whitespace-nowrap border-b border-border px-3 text-[10px] font-semibold text-muted-foreground",
                  column.className,
                )}
                key={column.key}
                scope="col"
              >
                {column.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.length > 0 ? (
            rows.map((row, rowIndex) => (
              <TableRow className="align-top transition-colors hover:bg-muted/45" key={rowIndex}>
                {columns.map((column) => (
                  <TableCell
                    className={cn(
                      "max-w-[22rem] whitespace-normal break-words border-b border-border px-3 py-2.5 text-foreground first:font-semibold",
                      column.className,
                    )}
                    key={column.key}
                  >
                    {column.render(row)}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell
                className="px-3 py-8 text-center text-sm text-muted-foreground"
                colSpan={columns.length}
              >
                {emptyLabel}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      </div>
    </>
  );
}
