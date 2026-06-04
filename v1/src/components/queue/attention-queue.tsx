import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Filter,
  MoreHorizontal,
  Search,
  ShieldAlert,
  Timer,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import {
  asArray,
  asRecord,
  numberOf,
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const lanes = [
  {
    label: "Approval",
    icon: CheckCircle2,
    detail: "Outbound replies waiting for review",
  },
  {
    label: "Low confidence",
    icon: ShieldAlert,
    detail: "Trust score below supervisor threshold",
  },
  {
    label: "Escalated",
    icon: AlertTriangle,
    detail: "Human judgment or customer risk needed",
  },
  {
    label: "Failed tool/send",
    icon: Wrench,
    detail: "Tool run or message delivery failed",
  },
];

function laneRows(rows: LooseRecord[], lane: string) {
  const laneKey = lane.split(" ")[0].toLowerCase();

  return rows.filter((row) =>
    textOf(row, ["lane", "status", "reason", "queueType"], "")
      .toLowerCase()
      .includes(laneKey),
  );
}

export function AttentionQueue({ conversations }: { conversations: unknown }) {
  const rows = asArray(conversations).map(asRecord);
  const highPriorityRows = rows.filter((row) =>
    ["high", "risk", "escalated"].some((value) =>
      textOf(row, ["priority", "severity", "status", "lane"], "")
        .toLowerCase()
        .includes(value),
    ),
  );
  const approvalRows = laneRows(rows, "Approval");
  const lowConfidenceRows = laneRows(rows, "Low confidence");
  const escalatedRows = laneRows(rows, "Escalated");
  const failedRows = laneRows(rows, "Failed tool/send");
  const tableColumns = [
    {
      key: "customer",
      label: "Contact",
      render: (row: LooseRecord) => (
        <div>
          <div className="font-medium text-foreground">
            {textOf(row, ["customerName", "contact", "name"])}
          </div>
          <div className="text-muted-foreground">
            {textOf(row, ["channel", "source"], "Inbox")}
          </div>
        </div>
      ),
    },
    {
      key: "reason",
      label: "Reason",
      render: (row: LooseRecord) => (
        <span className="font-medium text-foreground">
          {textOf(row, ["reason", "queueReason", "lane", "status"], "Review")}
        </span>
      ),
    },
    {
      key: "intent",
      label: "Intent",
      render: (row: LooseRecord) =>
        textOf(row, ["intent", "driver", "topic"], "Unknown"),
    },
    {
      key: "confidence",
      label: "Trust Score",
      className: "text-right tabular-nums",
      render: (row: LooseRecord) =>
        textOf(row, ["confidence", "aiConfidence"], "n/a"),
    },
    {
      key: "age",
      label: "Age",
      render: (row: LooseRecord) => (
        <span className="inline-flex items-center gap-1 text-foreground">
          <Timer aria-hidden="true" className="size-3.5 text-muted-foreground" />
          {textOf(row, ["age", "waitTime", "oldestAge"], "0m")}
        </span>
      ),
    },
    {
      key: "priority",
      label: "Priority",
      render: (row: LooseRecord) => {
        const status = textOf(row, ["priority", "severity", "status"], "Normal");
        return <StatusChip tone={toneFromStatus(status)}>{status}</StatusChip>;
      },
    },
    {
      key: "attempts",
      label: "Attempts",
      className: "text-right tabular-nums",
      render: (row: LooseRecord) =>
        numberOf(row, ["attempts", "sendAttempts", "toolAttempts"]).toString(),
    },
    {
      key: "action",
      label: "",
      className: "text-right",
      render: (row: LooseRecord) => {
        const conversationId = textOf(row, ["id", "conversationId", "threadId"], "");
        const href = conversationId
          ? `/conversations?conversationId=${encodeURIComponent(conversationId)}`
          : "/conversations";

        return (
          <Button asChild size="sm" variant="outline">
            <Link href={href}>
              Review
              <ArrowUpRight aria-hidden="true" />
            </Link>
          </Button>
        );
      },
    },
  ];

  return (
    <>
      <PageHeader
        description="Exceptions that need supervisor review before the AI can continue, send, or recover a failed action."
        title="Exceptions"
      />

      <Card className="mb-4 gap-0 border-border/80 py-0 shadow-xs">
        <CardContent className="grid gap-3 p-4 xl:grid-cols-[1fr_auto]">
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <p className="text-xs font-medium text-muted-foreground">Open exceptions</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                {rows.length}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">High priority</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                {highPriorityRows.length}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-muted-foreground">Approval queue</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                {approvalRows.length}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 xl:min-w-96">
            <div className="relative flex-1">
              <Search
                aria-hidden="true"
                className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                aria-label="Search attention queue"
                className="bg-background pl-8"
                placeholder="Search contact, reason, or intent"
                readOnly
              />
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger
                aria-label="Queue filters"
                className={buttonVariants({ size: "icon", variant: "outline" })}
              >
                <Filter aria-hidden="true" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Queue filters</DropdownMenuLabel>
                <DropdownMenuItem>High priority first</DropdownMenuItem>
                <DropdownMenuItem>Oldest first</DropdownMenuItem>
                <DropdownMenuItem>Low confidence only</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem>Clear filters</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </CardContent>
      </Card>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {lanes.map((lane) => {
          const Icon = lane.icon;
          const count = laneRows(rows, lane.label).length;

          return (
            <Card className="gap-0 py-0 shadow-xs" key={lane.label}>
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-muted-foreground">
                      {lane.label}
                    </div>
                    <div className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                      {count}
                    </div>
                  </div>
                  <span className="rounded-md border bg-muted/60 p-2 text-muted-foreground">
                    <Icon aria-hidden="true" size={16} />
                  </span>
                </div>
                <p className="mt-3 truncate text-xs text-muted-foreground">
                  {lane.detail}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Tabs defaultValue="all">
        <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <TabsList className="w-full overflow-x-auto lg:w-fit">
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="approval">Approval</TabsTrigger>
            <TabsTrigger value="confidence">Low confidence</TabsTrigger>
            <TabsTrigger value="escalated">Escalated</TabsTrigger>
            <TabsTrigger value="failed">Failed</TabsTrigger>
          </TabsList>
          <DropdownMenu>
            <DropdownMenuTrigger
              className={buttonVariants({ size: "sm", variant: "outline" })}
            >
              <MoreHorizontal aria-hidden="true" />
              Worklist actions
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Supervisor actions</DropdownMenuLabel>
              <DropdownMenuItem>Assign selected</DropdownMenuItem>
              <DropdownMenuItem>Export queue</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Copy queue summary</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <TabsContent value="all">
          <SectionPanel
            action={<Badge variant="secondary">{rows.length} items</Badge>}
            title="Exception Worklist"
            eyebrow="Supervisor queue"
          >
            <DataTable columns={tableColumns} rows={rows} />
          </SectionPanel>
        </TabsContent>
        <TabsContent value="approval">
          <SectionPanel
            action={<Badge variant="secondary">{approvalRows.length} items</Badge>}
            title="Approval Worklist"
            eyebrow="Supervisor queue"
          >
            <DataTable columns={tableColumns} rows={approvalRows} />
          </SectionPanel>
        </TabsContent>
        <TabsContent value="confidence">
          <SectionPanel
            action={<Badge variant="secondary">{lowConfidenceRows.length} items</Badge>}
            title="Low Trust Score Worklist"
            eyebrow="Supervisor queue"
          >
            <DataTable columns={tableColumns} rows={lowConfidenceRows} />
          </SectionPanel>
        </TabsContent>
        <TabsContent value="escalated">
          <SectionPanel
            action={<Badge variant="secondary">{escalatedRows.length} items</Badge>}
            title="Escalated Worklist"
            eyebrow="Supervisor queue"
          >
            <DataTable columns={tableColumns} rows={escalatedRows} />
          </SectionPanel>
        </TabsContent>
        <TabsContent value="failed">
          <SectionPanel
            action={<Badge variant="secondary">{failedRows.length} items</Badge>}
            title="Failed Tool/Send Worklist"
            eyebrow="Supervisor queue"
          >
            <DataTable columns={tableColumns} rows={failedRows} />
          </SectionPanel>
        </TabsContent>
      </Tabs>
    </>
  );
}
