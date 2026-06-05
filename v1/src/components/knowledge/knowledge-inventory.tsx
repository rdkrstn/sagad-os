import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/ui/data-table";
import { MetricStrip } from "@/components/ui/metric-strip";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  asArray,
  asRecord,
  textOf,
  type LooseRecord,
} from "@/components/ui/data-access";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileCheck2,
  FileClock,
  FolderSync,
  LibraryBig,
  UploadCloud,
} from "lucide-react";

function numberOf(row: LooseRecord, keys: string[], fallback = 0): number {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number") {
      return value;
    }
    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return fallback;
}

function rowsFromOverview(overview: unknown, key: string): LooseRecord[] {
  return asArray(asRecord(overview)[key]).map(asRecord);
}

function statusTone(row: LooseRecord): ReturnType<typeof toneFromStatus> {
  return toneFromStatus(textOf(row, ["status", "approvalStatus"], "Unknown"));
}

export function KnowledgeInventory({ overview }: { overview: unknown }) {
  const root = asRecord(overview);
  const documents = rowsFromOverview(root, "documents");
  const jobs = rowsFromOverview(root, "jobs");
  const sources = rowsFromOverview(root, "sources");
  const missingKnowledge = rowsFromOverview(root, "missingKnowledge");
  const liveSource = textOf(root, ["source"], "mock");
  const reviewCount = documents.filter((row) =>
    textOf(row, ["approvalStatus", "status"], "").toLowerCase().includes("review"),
  ).length;
  const approvedCount = documents.filter((row) =>
    textOf(row, ["approvalStatus", "status"], "").toLowerCase().includes("approved"),
  ).length;
  const failedJobs = jobs.filter((row) => numberOf(row, ["failed"]) > 0).length;

  return (
    <>
      <PageHeader
        description="Approved answer source for SOPs, policies, transcripts, spreadsheets, documents, and future connected sources."
        meta={liveSource === "agent-studio" ? "Agent Studio live" : "Preview fallback"}
        title="Knowledge"
      />

      <div className="space-y-4">
        <MetricStrip
          items={[
            {
              label: "Sources",
              value: sources.length,
              detail: "Manual now, Drive later",
              icon: FolderSync,
            },
            {
              label: "Documents",
              value: documents.length,
              detail: "Imported knowledge records",
              icon: LibraryBig,
            },
            {
              label: "Needs review",
              value: reviewCount,
              detail: "Not available to agents yet",
              icon: FileClock,
            },
            {
              label: "Approved",
              value: approvedCount,
              detail: "Retrieval eligible chunks",
              icon: FileCheck2,
            },
          ]}
        />

        <Tabs defaultValue="sources" className="space-y-4">
          <TabsList>
            <TabsTrigger value="sources">Sources</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="review">Review Queue</TabsTrigger>
            <TabsTrigger value="jobs">Ingestion Jobs</TabsTrigger>
            <TabsTrigger value="missing">Missing Knowledge</TabsTrigger>
          </TabsList>

          <TabsContent value="sources" className="mt-0">
            <SectionPanel title="Content Sources" eyebrow="Ingestion">
              <DataTable
                columns={[
                  {
                    key: "name",
                    label: "Source",
                    render: (row) => (
                      <div>
                        <div className="font-medium text-foreground">
                          {textOf(row, ["name"])}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {textOf(row, ["detail"])}
                        </div>
                      </div>
                    ),
                  },
                  {
                    key: "type",
                    label: "Type",
                    render: (row) => <Badge variant="secondary">{textOf(row, ["type"])}</Badge>,
                  },
                  {
                    key: "sync",
                    label: "Sync",
                    render: (row) => textOf(row, ["sync"], "Manual"),
                  },
                  {
                    key: "status",
                    label: "Status",
                    render: (row) => (
                      <StatusChip tone={statusTone(row)}>
                        {textOf(row, ["status"], "Unknown")}
                      </StatusChip>
                    ),
                  },
                ]}
                emptyLabel="No content sources are configured."
                rows={sources}
              />
            </SectionPanel>
          </TabsContent>

          <TabsContent value="documents" className="mt-0">
            <SectionPanel title="Knowledge Documents" eyebrow="Approved answer source">
              <DataTable
                columns={[
                  {
                    key: "title",
                    label: "Document",
                    render: (row) => (
                      <div className="min-w-[260px]">
                        <div className="font-medium text-foreground">
                          {textOf(row, ["title", "name"])}
                        </div>
                        <div className="line-clamp-2 text-sm text-muted-foreground">
                          {textOf(row, ["summary", "description", "sourcePath"], "")}
                        </div>
                      </div>
                    ),
                  },
                  {
                    key: "category",
                    label: "Category",
                    render: (row) => (
                      <Badge variant="secondary">
                        {textOf(row, ["category", "type"], "KB")}
                      </Badge>
                    ),
                  },
                  {
                    key: "version",
                    label: "Version",
                    render: (row) => `v${numberOf(row, ["version"], 1)}`,
                  },
                  {
                    key: "chunks",
                    label: "Chunks",
                    render: (row) => numberOf(row, ["chunks", "chunkCount"]),
                  },
                  {
                    key: "updated",
                    label: "Updated",
                    render: (row) => textOf(row, ["updatedAt", "lastUpdated"], "Pending"),
                  },
                  {
                    key: "status",
                    label: "Status",
                    render: (row) => (
                      <StatusChip tone={statusTone(row)}>
                        {textOf(row, ["status", "approvalStatus"], "Needs Review")}
                      </StatusChip>
                    ),
                  },
                ]}
                emptyLabel="No knowledge documents are available yet."
                rows={documents}
              />
            </SectionPanel>
          </TabsContent>

          <TabsContent value="review" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <SectionPanel title="Needs Review" eyebrow="Governance">
                <DataTable
                  columns={[
                    {
                      key: "title",
                      label: "Document",
                      render: (row) => textOf(row, ["title", "name"]),
                    },
                    {
                      key: "category",
                      label: "Category",
                      render: (row) => textOf(row, ["category", "type"], "KB"),
                    },
                    {
                      key: "source",
                      label: "Source",
                      render: (row) => textOf(row, ["sourcePath", "source"], "Manual"),
                    },
                    {
                      key: "status",
                      label: "Status",
                      render: (row) => (
                        <StatusChip tone="warning">
                          {textOf(row, ["status", "approvalStatus"], "Needs Review")}
                        </StatusChip>
                      ),
                    },
                  ]}
                  emptyLabel="No documents are waiting for review."
                  rows={documents.filter((row) =>
                    textOf(row, ["status", "approvalStatus"], "")
                      .toLowerCase()
                      .includes("review"),
                  )}
                />
              </SectionPanel>

              <SectionPanel title="Review Rule" eyebrow="Safety">
                <div className="space-y-3 p-4 text-sm text-muted-foreground">
                  <div className="flex gap-3 rounded-lg border bg-background p-3">
                    <CheckCircle2 className="mt-0.5 size-4 text-emerald-600" />
                    <p>Only approved documents become available to Sales and Support agents.</p>
                  </div>
                  <div className="flex gap-3 rounded-lg border bg-background p-3">
                    <Database className="mt-0.5 size-4 text-blue-600" />
                    <p>pgvector is the retrieval index. Reviewable source records remain the source of truth.</p>
                  </div>
                  <div className="flex gap-3 rounded-lg border bg-background p-3">
                    <AlertTriangle className="mt-0.5 size-4 text-amber-600" />
                    <p>SOP, compliance, refund, billing, and verification content should stay approval-gated.</p>
                  </div>
                </div>
              </SectionPanel>
            </div>
          </TabsContent>

          <TabsContent value="jobs" className="mt-0">
            <SectionPanel
              title="Ingestion Jobs"
              eyebrow={failedJobs > 0 ? `${failedJobs} failed` : "Processing history"}
            >
              <DataTable
                columns={[
                  {
                    key: "source",
                    label: "Source",
                    render: (row) => (
                      <div>
                        <div className="font-medium text-foreground">
                          {textOf(row, ["source"])}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {textOf(row, ["summary"])}
                        </div>
                      </div>
                    ),
                  },
                  {
                    key: "type",
                    label: "Type",
                    render: (row) => textOf(row, ["sourceType"], "Manual"),
                  },
                  {
                    key: "processed",
                    label: "Processed",
                    render: (row) =>
                      `${numberOf(row, ["processed"])}/${numberOf(row, ["total"])}`,
                  },
                  {
                    key: "failed",
                    label: "Failed",
                    render: (row) => numberOf(row, ["failed"]),
                  },
                  {
                    key: "status",
                    label: "Status",
                    render: (row) => (
                      <StatusChip tone={statusTone(row)}>
                        {textOf(row, ["status"], "Queued")}
                      </StatusChip>
                    ),
                  },
                ]}
                emptyLabel="No ingestion jobs have run yet."
                rows={jobs}
              />
            </SectionPanel>
          </TabsContent>

          <TabsContent value="missing" className="mt-0">
            <SectionPanel title="Missing Knowledge" eyebrow="Recommended action">
              <DataTable
                columns={[
                  {
                    key: "topic",
                    label: "Topic",
                    render: (row) => (
                      <div className="font-medium text-foreground">
                        {textOf(row, ["topic"])}
                      </div>
                    ),
                  },
                  {
                    key: "count",
                    label: "Mentions",
                    render: (row) => numberOf(row, ["count"]),
                  },
                  {
                    key: "severity",
                    label: "Severity",
                    render: (row) => (
                      <StatusChip tone={statusTone(row)}>
                        {textOf(row, ["severity"], "Review")}
                      </StatusChip>
                    ),
                  },
                  {
                    key: "action",
                    label: "Recommended action",
                    render: (row) => textOf(row, ["recommendedAction"]),
                  },
                ]}
                emptyLabel="No missing knowledge topics detected."
                rows={missingKnowledge}
              />
            </SectionPanel>
          </TabsContent>
        </Tabs>

        <div className="rounded-lg border bg-card p-4 text-sm text-muted-foreground">
          <div className="flex items-start gap-3">
            <UploadCloud className="mt-0.5 size-4 text-muted-foreground" />
            <p>
              Local ingestion is the first shipped path. Google Drive, websites, and external KBs
              should connect later through Agent Studio source adapters, never from browser code.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
