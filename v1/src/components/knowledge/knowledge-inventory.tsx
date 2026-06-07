"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  Archive,
  CheckCircle2,
  Database,
  Eye,
  FileCheck2,
  FileClock,
  FolderSync,
  LibraryBig,
  RefreshCw,
  Search,
  UploadCloud,
} from "lucide-react";

type ActionTone = "success" | "error" | "info";

interface ActionMessage {
  tone: ActionTone;
  text: string;
}

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

function isReviewRow(row: LooseRecord): boolean {
  const value = textOf(row, ["approvalStatus", "status"], "").toLowerCase();
  return value.includes("review") || value === "needs_review";
}

function rowId(row: LooseRecord): string {
  return textOf(row, ["id"], "");
}

function formatDate(value: string): string {
  if (!value) {
    return "Not yet";
  }
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsed);
}

function messageClass(tone: ActionTone): string {
  if (tone === "success") {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (tone === "error") {
    return "border-red-200 bg-red-50 text-red-800";
  }
  return "border-blue-200 bg-blue-50 text-blue-800";
}

async function responsePayload(response: Response): Promise<LooseRecord> {
  const payload = (await response.json().catch(() => ({}))) as unknown;
  return asRecord(payload);
}

function detailFromPayload(payload: LooseRecord, fallback: string): string {
  return textOf(payload, ["detail", "message", "summary"], fallback);
}

function metadataPairs(row: LooseRecord): Array<[string, string]> {
  const metadata = asRecord(row.metadata);
  return Object.entries(metadata)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 10)
    .map(([key, value]) => [
      key.replaceAll("_", " "),
      typeof value === "object" ? JSON.stringify(value) : String(value),
    ]);
}

function jobErrors(row: LooseRecord): LooseRecord[] {
  return asArray(row.errors).map(asRecord);
}

function selectedSourceId(sources: LooseRecord[]): string | null {
  const source = sources.find((row) => !Boolean(row.planned) && rowId(row));
  return source ? rowId(source) : null;
}

export function KnowledgeInventory({ overview }: { overview: unknown }) {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const root = asRecord(overview);
  const documents = rowsFromOverview(root, "documents");
  const jobs = rowsFromOverview(root, "jobs");
  const sources = rowsFromOverview(root, "sources");
  const missingKnowledge = rowsFromOverview(root, "missingKnowledge");
  const liveSource = textOf(root, ["source"], "mock");
  const actionsDisabled = liveSource !== "agent-studio";
  const reviewDocuments = documents.filter(isReviewRow);
  const approvedCount = documents.filter((row) =>
    textOf(row, ["approvalStatus", "status"], "").toLowerCase().includes("approved"),
  ).length;
  const archivedCount = documents.filter((row) =>
    textOf(row, ["approvalStatus", "status"], "").toLowerCase().includes("archived"),
  ).length;
  const failedJobs = jobs.filter((row) => numberOf(row, ["failed"]) > 0).length;

  const [sourceName, setSourceName] = useState("Manual Upload");
  const [category, setCategory] = useState("kb");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<LooseRecord[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState(
    rowId(documents[0] ?? {}),
  );
  const [actionMessage, setActionMessage] = useState<ActionMessage | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const selectedDocument =
    documents.find((document) => rowId(document) === selectedDocumentId) ??
    documents[0] ??
    null;

  async function runAction(
    label: string,
    action: () => Promise<Response>,
    successText: string,
    refresh = true,
  ): Promise<void> {
    setPendingAction(label);
    setActionMessage(null);
    try {
      const response = await action();
      const payload = await responsePayload(response);
      if (!response.ok) {
        throw new Error(detailFromPayload(payload, `${label} failed.`));
      }
      setActionMessage({ tone: "success", text: successText });
      if (refresh) {
        router.refresh();
      }
    } catch (error) {
      setActionMessage({
        tone: "error",
        text: error instanceof Error ? error.message : `${label} failed.`,
      });
    } finally {
      setPendingAction(null);
    }
  }

  async function uploadFiles(): Promise<void> {
    const files = fileInputRef.current?.files;
    if (!files || files.length === 0) {
      setActionMessage({ tone: "error", text: "Choose at least one file first." });
      return;
    }

    const body = new FormData();
    body.set("source_name", sourceName);
    body.set("source_type", "manual_upload");
    body.set("category", category);
    Array.from(files).forEach((file) => body.append("files", file));

    await runAction(
      "Upload content",
      () =>
        fetch("/api/knowledge/ingestion-jobs", {
          method: "POST",
          body,
        }),
      "Upload received. Documents are waiting for review.",
    );

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  async function postAction(path: string, label: string, successText: string): Promise<void> {
    await runAction(
      label,
      () =>
        fetch(path, {
          method: "POST",
        }),
      successText,
    );
  }

  async function runSearchTest(): Promise<void> {
    if (!searchQuery.trim()) {
      setActionMessage({ tone: "error", text: "Enter a search query first." });
      return;
    }

    setPendingAction("Search test");
    setActionMessage(null);
    try {
      const response = await fetch("/api/knowledge/search-test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          intent: "general_support",
          risk_level: "medium",
          limit: 4,
        }),
      });
      const payload = await responsePayload(response);
      if (!response.ok) {
        throw new Error(detailFromPayload(payload, "Search test failed."));
      }
      setSearchHits(asArray(payload.hits).map(asRecord));
      setActionMessage({ tone: "success", text: "Search test completed." });
    } catch (error) {
      setSearchHits([]);
      setActionMessage({
        tone: "error",
        text: error instanceof Error ? error.message : "Search test failed.",
      });
    } finally {
      setPendingAction(null);
    }
  }

  const firstSourceId = selectedSourceId(sources);

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
              value: reviewDocuments.length,
              detail: "Not available to agents yet",
              icon: FileClock,
            },
            {
              label: "Approved",
              value: approvedCount,
              detail: "Retrieval eligible chunks",
              icon: FileCheck2,
            },
            {
              label: "Archived",
              value: archivedCount,
              detail: "Hidden from retrieval",
              icon: Archive,
            },
          ]}
        />

        {actionMessage ? (
          <div className={`rounded-lg border px-4 py-3 text-sm ${messageClass(actionMessage.tone)}`}>
            {actionMessage.text}
          </div>
        ) : null}

        {actionsDisabled ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Knowledge actions are disabled because the console is using preview data. Set
            {" "}
            <code className="rounded bg-amber-100 px-1 py-0.5">SAGAD_API_BASE_URL</code>
            {" "}
            to connect Agent Studio for uploads, approval, sync, and search testing.
          </div>
        ) : null}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
          <SectionPanel title="Add Content" eyebrow="Local ingestion">
            <div className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_180px_180px_auto] md:items-end">
              <label className="grid gap-1 text-sm">
                <span className="font-medium text-foreground">Files</span>
                <input
                  ref={fileInputRef}
                  className="h-9 rounded-lg border bg-background px-3 text-sm"
                  disabled={actionsDisabled}
                  multiple
                  type="file"
                  accept=".md,.markdown,.txt,.json,.vtt,.srt,.pdf,.docx,.xlsx,.csv"
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span className="font-medium text-foreground">Source name</span>
                <input
                  className="h-9 rounded-lg border bg-background px-3 text-sm"
                  disabled={actionsDisabled}
                  onChange={(event) => setSourceName(event.target.value)}
                  value={sourceName}
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span className="font-medium text-foreground">Category</span>
                <select
                  className="h-9 rounded-lg border bg-background px-3 text-sm"
                  disabled={actionsDisabled}
                  onChange={(event) => setCategory(event.target.value)}
                  value={category}
                >
                  <option value="kb">KB</option>
                  <option value="sops">SOP</option>
                  <option value="qa">QA</option>
                  <option value="compliance">Compliance</option>
                  <option value="approved_templates">Template</option>
                </select>
              </label>
              <Button
                disabled={actionsDisabled || pendingAction === "Upload content"}
                onClick={uploadFiles}
                type="button"
              >
                <UploadCloud className="size-4" />
                Add content
              </Button>
            </div>
          </SectionPanel>

          <SectionPanel title="Test Search" eyebrow="Approved answer source">
            <div className="space-y-3 p-4">
              <div className="flex gap-2">
                <input
                  className="h-9 min-w-0 flex-1 rounded-lg border bg-background px-3 text-sm"
                  disabled={actionsDisabled}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Ask: What is our refund policy for sale items?"
                  value={searchQuery}
                />
                <Button
                  disabled={actionsDisabled || pendingAction === "Search test"}
                  onClick={runSearchTest}
                  type="button"
                  variant="outline"
                >
                  <Search className="size-4" />
                  Test
                </Button>
              </div>
              <div className="space-y-2">
                {searchHits.length > 0 ? (
                  searchHits.map((hit) => (
                    <div className="rounded-lg border bg-background p-3 text-sm" key={rowId(hit)}>
                      <div className="font-medium text-foreground">{textOf(hit, ["title"])}</div>
                      <div className="mt-1 text-muted-foreground">{textOf(hit, ["excerpt"])}</div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Search tests only return approved documents. Drafts stay hidden from agent retrieval.
                  </p>
                )}
              </div>
            </div>
          </SectionPanel>
        </div>

        <Tabs defaultValue="sources" className="space-y-4">
          <TabsList>
            <TabsTrigger value="sources">Sources</TabsTrigger>
            <TabsTrigger value="documents">Documents</TabsTrigger>
            <TabsTrigger value="review">Review Queue</TabsTrigger>
            <TabsTrigger value="jobs">Ingestion Jobs</TabsTrigger>
            <TabsTrigger value="missing">Missing Knowledge</TabsTrigger>
          </TabsList>

          <TabsContent value="sources" className="mt-0">
            <SectionPanel
              title="Content Sources"
              eyebrow="Ingestion"
              action={
                <Button
                  disabled={actionsDisabled || !firstSourceId || pendingAction === "Re-index source"}
                  onClick={() =>
                    firstSourceId
                      ? postAction(
                          `/api/knowledge/sources/${encodeURIComponent(firstSourceId)}/sync`,
                          "Re-index source",
                          "Local source re-index finished.",
                        )
                      : undefined
                  }
                  type="button"
                  variant="outline"
                >
                  <RefreshCw className="size-4" />
                  Re-index source
                </Button>
              }
            >
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
                    key: "updated",
                    label: "Last sync",
                    render: (row) => formatDate(textOf(row, ["lastSyncedAt", "updatedAt"], "")),
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
                  {
                    key: "actions",
                    label: "",
                    render: (row) =>
                      Boolean(row.planned) ? (
                        <span className="text-xs text-muted-foreground">Planned</span>
                      ) : (
                        <Button
                          disabled={actionsDisabled || pendingAction === "Re-index source"}
                          onClick={() =>
                            postAction(
                              `/api/knowledge/sources/${encodeURIComponent(rowId(row))}/sync`,
                              "Re-index source",
                              "Local source re-index finished.",
                            )
                          }
                          size="sm"
                          type="button"
                          variant="outline"
                        >
                          <RefreshCw className="size-3.5" />
                          Re-index
                        </Button>
                      ),
                  },
                ]}
                emptyLabel="No content sources are configured."
                rows={sources}
              />
            </SectionPanel>
          </TabsContent>

          <TabsContent value="documents" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
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
                      render: (row) => formatDate(textOf(row, ["updatedAt", "lastUpdated"], "")),
                    },
                    {
                      key: "lastEmbeddedAt",
                      label: "Last embedded",
                      render: (row) => formatDate(textOf(row, ["lastEmbeddedAt", "updatedAt"], "")),
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
                    {
                      key: "actions",
                      label: "",
                      render: (row) => (
                        <Button
                          onClick={() => setSelectedDocumentId(rowId(row))}
                          size="sm"
                          type="button"
                          variant={rowId(row) === rowId(selectedDocument ?? {}) ? "default" : "outline"}
                        >
                          <Eye className="size-3.5" />
                          View
                        </Button>
                      ),
                    },
                  ]}
                  emptyLabel="No knowledge documents are available yet."
                  rows={documents}
                />
              </SectionPanel>

              <DocumentDetail
                actionsDisabled={actionsDisabled}
                document={selectedDocument}
                pendingAction={pendingAction}
                postAction={postAction}
              />
            </div>
          </TabsContent>

          <TabsContent value="review" className="mt-0">
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <SectionPanel title="Needs Review" eyebrow="Governance">
                <DataTable
                  columns={[
                    {
                      key: "title",
                      label: "Document",
                      render: (row) => (
                        <div>
                          <div className="font-medium text-foreground">
                            {textOf(row, ["title", "name"])}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {textOf(row, ["sourcePath", "source"], "Manual")}
                          </div>
                        </div>
                      ),
                    },
                    {
                      key: "category",
                      label: "Category",
                      render: (row) => textOf(row, ["category", "type"], "KB"),
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
                    {
                      key: "actions",
                      label: "Actions",
                      render: (row) => (
                        <div className="flex flex-wrap gap-2">
                          <Button
                            disabled={actionsDisabled || pendingAction === "Approve"}
                            onClick={() =>
                              postAction(
                                `/api/knowledge/documents/${encodeURIComponent(rowId(row))}/approve`,
                                "Approve",
                                "Document approved and indexed for retrieval.",
                              )
                            }
                            size="sm"
                            type="button"
                          >
                            <CheckCircle2 className="size-3.5" />
                            Approve
                          </Button>
                          <Button
                            disabled={actionsDisabled || pendingAction === "Archive"}
                            onClick={() =>
                              postAction(
                                `/api/knowledge/documents/${encodeURIComponent(rowId(row))}/archive`,
                                "Archive",
                                "Document archived and removed from retrieval.",
                              )
                            }
                            size="sm"
                            type="button"
                            variant="outline"
                          >
                            <Archive className="size-3.5" />
                            Archive
                          </Button>
                          <Button
                            disabled={actionsDisabled || pendingAction === "Re-index"}
                            onClick={() =>
                              postAction(
                                `/api/knowledge/documents/${encodeURIComponent(rowId(row))}/resync`,
                                "Re-index",
                                "Document re-index finished.",
                              )
                            }
                            size="sm"
                            type="button"
                            variant="outline"
                          >
                            <RefreshCw className="size-3.5" />
                            Re-index
                          </Button>
                        </div>
                      ),
                    },
                  ]}
                  emptyLabel="No documents are waiting for review."
                  rows={reviewDocuments}
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
                    <p>The retrieval index is not the source of truth. Reviewable source records are.</p>
                  </div>
                  <div className="flex gap-3 rounded-lg border bg-background p-3">
                    <AlertTriangle className="mt-0.5 size-4 text-amber-600" />
                    <p>SOP, compliance, refund, billing, and verification content stay approval-gated.</p>
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
                    key: "errors",
                    label: "Errors",
                    render: (row) => {
                      const errors = jobErrors(row);
                      return errors.length > 0 ? (
                        <div className="space-y-1">
                          {errors.slice(0, 2).map((error) => (
                            <div key={rowId(error)} className="text-red-700">
                              {textOf(error, ["error_code"])}: {textOf(error, ["message"])}
                            </div>
                          ))}
                        </div>
                      ) : (
                        "None"
                      );
                    },
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
              Local ingestion is the first shipped path. Google Drive, websites, Notion,
              Confluence, and Guru connect later through Agent Studio source adapters.
              Browser code never parses files, runs OCR, calls model providers, or touches
              the retrieval database.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}

function DocumentDetail({
  actionsDisabled,
  document,
  pendingAction,
  postAction,
}: {
  actionsDisabled: boolean;
  document: LooseRecord | null;
  pendingAction: string | null;
  postAction: (path: string, label: string, successText: string) => Promise<void>;
}) {
  if (!document) {
    return (
      <SectionPanel title="Document Detail" eyebrow="Selected record">
        <div className="p-4 text-sm text-muted-foreground">
          Select a document to inspect extracted text, OCR metadata, chunks, and review state.
        </div>
      </SectionPanel>
    );
  }

  const id = rowId(document);
  const content = textOf(document, ["content", "summary"], "");
  const metadata = metadataPairs(document);

  return (
    <SectionPanel title="Document Detail" eyebrow="Selected record">
      <div className="space-y-4 p-4">
        <div>
          <div className="text-base font-semibold text-foreground">
            {textOf(document, ["title", "name"])}
          </div>
          <div className="mt-1 text-sm text-muted-foreground">
            {textOf(document, ["sourcePath", "source"], "Manual source")}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-lg border bg-background p-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              Status
            </div>
            <div className="mt-1">
              <StatusChip tone={statusTone(document)}>
                {textOf(document, ["status", "approvalStatus"], "Needs Review")}
              </StatusChip>
            </div>
          </div>
          <div className="rounded-lg border bg-background p-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              Chunks
            </div>
            <div className="mt-1 font-medium text-foreground">
              {numberOf(document, ["chunks", "chunkCount"])}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={actionsDisabled || pendingAction === "Approve"}
            onClick={() =>
              postAction(
                `/api/knowledge/documents/${encodeURIComponent(id)}/approve`,
                "Approve",
                "Document approved and indexed for retrieval.",
              )
            }
            size="sm"
            type="button"
          >
            <CheckCircle2 className="size-3.5" />
            Approve
          </Button>
          <Button
            disabled={actionsDisabled || pendingAction === "Re-index"}
            onClick={() =>
              postAction(
                `/api/knowledge/documents/${encodeURIComponent(id)}/resync`,
                "Re-index",
                "Document re-index finished.",
              )
            }
            size="sm"
            type="button"
            variant="outline"
          >
            <RefreshCw className="size-3.5" />
            Re-index
          </Button>
          <Button
            disabled={actionsDisabled || pendingAction === "Archive"}
            onClick={() =>
              postAction(
                `/api/knowledge/documents/${encodeURIComponent(id)}/archive`,
                "Archive",
                "Document archived and removed from retrieval.",
              )
            }
            size="sm"
            type="button"
            variant="destructive"
          >
            <Archive className="size-3.5" />
            Archive
          </Button>
        </div>

        <div>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            Extracted text
          </div>
          <pre className="max-h-72 overflow-auto rounded-lg border bg-background p-3 text-xs leading-5 text-foreground whitespace-pre-wrap">
            {content || "No extracted text is available yet."}
          </pre>
        </div>

        <div>
          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            Extraction metadata
          </div>
          {metadata.length > 0 ? (
            <div className="divide-y rounded-lg border bg-background">
              {metadata.map(([key, value]) => (
                <div className="grid grid-cols-[130px_minmax(0,1fr)] gap-3 px-3 py-2 text-xs" key={key}>
                  <div className="font-medium text-muted-foreground">{key}</div>
                  <div className="break-words text-foreground">{value}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border bg-background p-3 text-sm text-muted-foreground">
              No extraction metadata was recorded.
            </div>
          )}
        </div>
      </div>
    </SectionPanel>
  );
}
