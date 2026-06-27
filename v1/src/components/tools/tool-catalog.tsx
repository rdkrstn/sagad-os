"use client";

import {
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MetricStrip } from "@/components/ui/metric-strip";
import { SectionPanel } from "@/components/ui/section-panel";
import { StatusChip, toneFromStatus } from "@/components/ui/status-chip";
import { Switch } from "@/components/ui/switch";
import {
  Activity,
  CheckCircle2,
  CircleDashed,
  Copy,
  DatabaseZap,
  LockKeyhole,
  MessageSquareText,
  PlugZap,
  RefreshCcw,
  Save,
  Settings,
  ShieldCheck,
  TestTube2,
  Unplug,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { IntegrationConnectionView } from "@/lib/api/sagad-api";

type IntegrationProvider = IntegrationConnectionView["provider"];

type ProviderForm = {
  base_url: string;
  account_id: string;
  inbox_id: string;
  api_access_token: string;
  webhook_token: string;
  api_key: string;
  api_mode: string;
  enabled: boolean;
  dry_run: boolean;
  allow_writes: boolean;
};

type ActionState = {
  provider: IntegrationProvider | "global";
  status: "idle" | "saving" | "testing" | "disabling" | "success" | "error";
  message: string;
};

type FutureProviderRow = {
  provider: string;
  role: string;
  status: string;
  owner: string;
  access: string;
  nextStep: string;
};

type DiagnosticEventView = {
  id: string;
  event_type: string;
  status: "info" | "success" | "warning" | "error";
  summary: string;
  conversation_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

type PrimaryProviderMeta = {
  provider: IntegrationProvider;
  title: string;
  role: string;
  owner: string;
  description: string;
  icon: LucideIcon;
  accentClassName: string;
};
// TODO: Add a "last updated" timestamp to the connection status and surface it in the UI, so operators know how fresh the health data is and can correlate with changes or incidents in the provider systems.
const providerMeta: PrimaryProviderMeta[] = [
  {
    provider: "chatwoot",
    title: "Chatwoot",
    role: "Channel intake and approved delivery",
    owner: "Supervisor Ops",
    description:
      "Receives inbound conversations and sends only supervisor-approved replies through Agent Studio.",
    icon: MessageSquareText,
    accentClassName: "border-[var(--sui-green-border)] bg-[var(--sui-green-soft)] text-[var(--accent-text)]",
  },
  {
    provider: "twenty",
    title: "Twenty CRM",
    role: "External CRM context",
    owner: "Revenue Ops",
    description:
      "Supplies contact context from an externally hosted Twenty instance. Credentials stay server-side.",
    icon: DatabaseZap,
    accentClassName: "border-[#2F80FF]/35 bg-[#2F80FF]/10 text-[#174EA6]",
  },
];

// TODO: Add a "last updated" timestamp to the connection status and surface it in the UI, so operators know how fresh the health data is and can correlate with changes or incidents in the provider systems.
const futureProviderRows: FutureProviderRow[] = [
  {
    provider: "LangSmith",
    role: "Trace observability",
    status: "Optional",
    owner: "AI Ops",
    access: "Read-only",
    nextStep: "Show trace links when Agent Studio environment variables exist.",
  },
  {
    provider: "Markdown Knowledge Packs",
    role: "Governed context source",
    status: "Ready",
    owner: "QA Ops",
    access: "Local source",
    nextStep: "Keep KB/SOP/QA/compliance content versioned as Markdown.",
  },
  {
    provider: "Generic Webhooks",
    role: "Provider-neutral handoff",
    status: "Planned",
    owner: "Platform",
    access: "Approval-gated",
    nextStep: "Enable after retries, signing, and audit metadata are stable.",
  },
  {
    provider: "Future MCP Servers",
    role: "Tool facade",
    status: "Planned",
    owner: "Platform",
    access: "Server-side only",
    nextStep: "Expose only through Agent Studio policy gates.",
  },
];

function blankConnection(provider: IntegrationProvider): IntegrationConnectionView {
  const name =
    provider === "chatwoot" ? "Chatwoot" : provider === "ghl" ? "GoHighLevel" : "Twenty CRM";
  const kind = provider === "twenty" ? "crm" : "channel";
  const missing =
    provider === "chatwoot"
      ? ["base_url", "account_id", "api_access_token"]
      : provider === "ghl"
        ? ["base_url", "api_key", "location_id"]
        : ["base_url", "api_key"];
  return {
    provider,
    name,
    kind,
    status: "unconfigured",
    configured: false,
    enabled: false,
    external: true,
    base_url: null,
    account_id: null,
    inbox_id: null,
    api_mode: provider === "twenty" ? "graphql" : null,
    dry_run: true,
    writes_enabled: false,
    has_api_access_token: false,
    has_webhook_token: false,
    has_api_key: false,
    location_id: null,
    outbound_mode: provider === "ghl" ? "webhook" : null,
    signature_scheme: provider === "ghl" ? "hmac" : null,
    poll_enabled: provider === "ghl" ? false : null,
    poll_interval_seconds: provider === "ghl" ? 30 : null,
    has_webhook_secret: false,
    has_native_webhook_key: false,
    missing,
    detail: `${name} is not configured yet.`,
    updated_at: null,
  };
}

function initialConnections(
  connections: IntegrationConnectionView[],
): Record<IntegrationProvider, IntegrationConnectionView> {
  const fallback = {
    chatwoot: blankConnection("chatwoot"),
    twenty: blankConnection("twenty"),
    ghl: blankConnection("ghl"),
  };

  return connections.reduce((next, connection) => {
    next[connection.provider] = connection;
    return next;
  }, fallback);
}

function formFromConnection(connection: IntegrationConnectionView): ProviderForm {
  return {
    base_url: connection.base_url ?? "",
    account_id: connection.account_id ?? "",
    inbox_id: connection.inbox_id ?? "",
    api_access_token: "",
    webhook_token: "",
    api_key: "",
    api_mode: connection.api_mode ?? "graphql",
    enabled: connection.enabled,
    dry_run: connection.dry_run,
    allow_writes: connection.writes_enabled,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isIntegrationConnection(value: unknown): value is IntegrationConnectionView {
  return (
    isRecord(value) &&
    (value.provider === "chatwoot" || value.provider === "twenty" || value.provider === "ghl") &&
    typeof value.name === "string" &&
    typeof value.status === "string"
  );
}

function isDiagnosticEvent(value: unknown): value is DiagnosticEventView {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.event_type === "string" &&
    typeof value.summary === "string" &&
    typeof value.created_at === "string" &&
    (value.status === "info" ||
      value.status === "success" ||
      value.status === "warning" ||
      value.status === "error")
  );
}

function detailFromPayload(payload: unknown): string {
  if (isRecord(payload) && typeof payload.detail === "string") {
    return payload.detail;
  }
  return "Request failed. Check Agent Studio logs for the provider response.";
}

function statusLabel(connection: IntegrationConnectionView): string {
  if (!connection.enabled && connection.configured) {
    return "Disabled";
  }
  if (!connection.configured) {
    return "Unconfigured";
  }
  if (connection.dry_run) {
    return "Dry-run";
  }
  return connection.status === "ready" ? "Ready" : connection.status;
}

function readinessStep(
  label: string,
  ready: boolean,
  detail: string,
): { label: string; ready: boolean; detail: string } {
  return { label, ready, detail };
}

function connectionSteps(connection: IntegrationConnectionView) {
  if (connection.provider === "chatwoot") {
    return [
      readinessStep("Base URL", Boolean(connection.base_url), "Chatwoot public URL is set."),
      readinessStep("Account ID", Boolean(connection.account_id), "Account maps sends to the right Chatwoot workspace."),
      readinessStep("API token", connection.has_api_access_token, "Token is stored encrypted in Agent Studio."),
      readinessStep("Webhook token", connection.has_webhook_token, "Inbound webhooks are signed before drafting."),
    ];
  }

  return [
    readinessStep("Base URL", Boolean(connection.base_url), "Twenty public or internal URL is set."),
    readinessStep("API key", connection.has_api_key, "Key is stored encrypted in Agent Studio."),
    readinessStep("Read mode", connection.configured, "Contact lookup can be tested before writes."),
    readinessStep("Write policy", connection.writes_enabled, "Writes require approval, dry-run off, and write gates."),
  ];
}

async function parseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return {};
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { detail: text };
  }
}

export function ToolCatalog({
  connections,
  canManage,
  currentRole,
}: {
  connections: IntegrationConnectionView[];
  canManage: boolean;
  currentRole: string;
}) {
  const [connectionState, setConnectionState] = useState(
    initialConnections(connections),
  );
  const [forms, setForms] = useState<Record<IntegrationProvider, ProviderForm>>({
    chatwoot: formFromConnection(connectionState.chatwoot),
    twenty: formFromConnection(connectionState.twenty),
    ghl: formFromConnection(connectionState.ghl),
  });
  const [action, setAction] = useState<ActionState>({
    provider: "global",
    status: "idle",
    message: "",
  });
  const [diagnosticEvents, setDiagnosticEvents] = useState<DiagnosticEventView[]>([]);
  const [diagnosticMessage, setDiagnosticMessage] = useState(
    "Loading backend diagnostics...",
  );

  useEffect(() => {
    let cancelled = false;

    async function loadDiagnostics(): Promise<void> {
      try {
        const response = await fetch("/api/diagnostics/events?limit=20", {
          cache: "no-store",
        });
        const payload = await parseJson(response);
        if (cancelled) {
          return;
        }
        if (!response.ok) {
          setDiagnosticMessage(detailFromPayload(payload));
          return;
        }
        const events =
          isRecord(payload) && Array.isArray(payload.events)
            ? payload.events.filter(isDiagnosticEvent)
            : [];
        setDiagnosticEvents(events);
        setDiagnosticMessage(
          events.length > 0
            ? "Latest Agent Studio events."
            : "No backend diagnostic events recorded yet.",
        );
      } catch {
        if (!cancelled) {
          setDiagnosticMessage("Could not load backend diagnostics.");
        }
      }
    }

    void loadDiagnostics();
    return () => {
      cancelled = true;
    };
  }, []);

  const configuredCount = useMemo(
    () =>
      Object.values(connectionState).filter(
        (connection) => connection.configured && connection.enabled,
      ).length,
    [connectionState],
  );
  const dryRunCount = useMemo(
    () => Object.values(connectionState).filter((connection) => connection.dry_run)
      .length,
    [connectionState],
  );
  const missingCount = useMemo(
    () =>
      Object.values(connectionState).reduce(
        (total, connection) => total + connection.missing.length,
        0,
      ),
    [connectionState],
  );

  const updateForm = (
    provider: IntegrationProvider,
    key: keyof ProviderForm,
    value: string | boolean,
  ) => {
    setForms((current) => ({
      ...current,
      [provider]: {
        ...current[provider],
        [key]: value,
      },
    }));
  };

  const saveConnection = async (
    provider: IntegrationProvider,
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();
    if (!canManage) {
      setAction({
        provider,
        status: "error",
        message: "Owner or Admin role is required to edit integrations.",
      });
      return;
    }

    setAction({ provider, status: "saving", message: "Saving connection..." });
    const form = forms[provider];
    const payload =
      provider === "chatwoot"
        ? {
            base_url: form.base_url || null,
            account_id: form.account_id || null,
            inbox_id: form.inbox_id || null,
            api_access_token: form.api_access_token || null,
            webhook_token: form.webhook_token || null,
            enabled: form.enabled,
            dry_run: form.dry_run,
            allow_writes: form.allow_writes,
          }
        : {
            base_url: form.base_url || null,
            api_key: form.api_key || null,
            api_mode: form.api_mode || "graphql",
            enabled: form.enabled,
            dry_run: form.dry_run,
            allow_writes: form.allow_writes,
          };

    const response = await fetch(`/api/integrations/${provider}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const responsePayload = await parseJson(response);

    if (!response.ok || !isIntegrationConnection(responsePayload)) {
      setAction({
        provider,
        status: "error",
        message: detailFromPayload(responsePayload),
      });
      return;
    }

    setConnectionState((current) => ({
      ...current,
      [provider]: responsePayload,
    }));
    setForms((current) => ({
      ...current,
      [provider]: {
        ...formFromConnection(responsePayload),
        api_access_token: "",
        webhook_token: "",
        api_key: "",
      },
    }));
    setAction({
      provider,
      status: "success",
      message: `${responsePayload.name} connection saved.`,
    });
  };

  const testConnection = async (provider: IntegrationProvider) => {
    if (!canManage) {
      setAction({
        provider,
        status: "error",
        message: "Owner or Admin role is required to test integrations.",
      });
      return;
    }

    setAction({ provider, status: "testing", message: "Testing connection..." });
    const response = await fetch(`/api/integrations/${provider}/test`, {
      method: "POST",
    });
    const payload = await parseJson(response);

    if (!response.ok) {
      setAction({ provider, status: "error", message: detailFromPayload(payload) });
      return;
    }

    const connection = isRecord(payload) ? payload.connection : null;
    if (isIntegrationConnection(connection)) {
      setConnectionState((current) => ({ ...current, [provider]: connection }));
    }
    setAction({
      provider,
      status: "success",
      message: detailFromPayload(payload),
    });
  };

  const disableConnection = async (provider: IntegrationProvider) => {
    if (!canManage) {
      setAction({
        provider,
        status: "error",
        message: "Owner or Admin role is required to disable integrations.",
      });
      return;
    }

    setAction({ provider, status: "disabling", message: "Disabling connection..." });
    const response = await fetch(`/api/integrations/${provider}`, {
      method: "DELETE",
    });
    const payload = await parseJson(response);

    if (!response.ok || !isIntegrationConnection(payload)) {
      setAction({ provider, status: "error", message: detailFromPayload(payload) });
      return;
    }

    setConnectionState((current) => ({ ...current, [provider]: payload }));
    setForms((current) => ({ ...current, [provider]: formFromConnection(payload) }));
    setAction({
      provider,
      status: "success",
      message: `${payload.name} disabled.`,
    });
  };

  const copyWebhookPath = async () => {
    await navigator.clipboard.writeText("/webhooks/chatwoot");
    setAction({
      provider: "chatwoot",
      status: "success",
      message: "Copied Agent Studio webhook path. Use it behind the public Agent Studio proxy.",
    });
  };

  return (
    <>
      <PageHeader
        description="Configure and monitor the external systems Agent Studio owns. Operators see health and next actions; developer payloads live under Settings Advanced."
        meta="Monitor + setup"
        title="Integrations"
      />

      <div className="space-y-4">
        <MetricStrip
          items={[
            {
              label: "Primary adapters",
              value: 2,
              detail: "Chatwoot and Twenty",
              icon: PlugZap,
            },
            {
              label: "Enabled",
              value: configuredCount,
              detail: "Configured and active",
              icon: CheckCircle2,
            },
            {
              label: "Dry-run paths",
              value: dryRunCount,
              detail: "Safe by default",
              icon: LockKeyhole,
            },
            {
              label: "Missing fields",
              value: missingCount,
              detail: "Setup gaps remaining",
              icon: Activity,
            },
          ]}
        />

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <SectionPanel
            action={
              <Button asChild variant="outline">
                <Link href="/settings">
                  <Settings aria-hidden="true" />
                  Advanced
                </Link>
              </Button>
            }
            eyebrow="Admin monitor"
            title="Provider Status"
          >
            <DataTable
              columns={[
                {
                  key: "name",
                  label: "Provider",
                  render: (row: IntegrationConnectionView) => (
                    <div className="space-y-1">
                      <div className="font-medium text-foreground">
                        {row.name}
                      </div>
                      <div className="text-muted-foreground">
                        {row.provider === "chatwoot"
                          ? "Channel intake and approved delivery"
                          : "External CRM context"}
                      </div>
                    </div>
                  ),
                },
                {
                  key: "status",
                  label: "Status",
                  render: (row: IntegrationConnectionView) => (
                    <StatusChip tone={toneFromStatus(statusLabel(row))}>
                      {statusLabel(row)}
                    </StatusChip>
                  ),
                },
                {
                  key: "base",
                  label: "Base URL",
                  render: (row: IntegrationConnectionView) =>
                    row.base_url ?? "Not set",
                },
                {
                  key: "writes",
                  label: "Writes",
                  render: (row: IntegrationConnectionView) =>
                    row.writes_enabled ? "Enabled" : "Approval gated / off",
                },
                {
                  key: "detail",
                  label: "Next",
                  render: (row: IntegrationConnectionView) => row.detail,
                },
              ]}
              rows={[connectionState.chatwoot, connectionState.twenty]}
            />
          </SectionPanel>

          <SectionPanel title="Connection Policy" eyebrow="Agent Studio owned">
            <div className="space-y-4 p-4">
              <Alert className="border-border bg-white">
                <ShieldCheck aria-hidden="true" />
                <AlertTitle>Provider credentials stay server-side</AlertTitle>
                <AlertDescription>
                  The browser saves config to Sagad routes. Agent Studio owns
                  encrypted secrets, tests, retries, audit events, and write gates.
                </AlertDescription>
              </Alert>

              <div className="grid gap-2 text-xs">
                {[
                  ["Current role", currentRole],
                  ["Edit access", canManage ? "Owner/Admin" : "Read-only"],
                  ["Chatwoot sends", "Supervisor approval only"],
                  ["Twenty writes", "Dry-run until approved"],
                ].map(([label, value]) => (
                  <div
                    className="flex items-center justify-between rounded-lg border border-border bg-surface-2 px-3 py-2"
                    key={label}
                  >
                    <span className="text-muted-foreground">{label}</span>
                    <span className="font-medium text-foreground">{value}</span>
                  </div>
                ))}
              </div>

              {action.message ? (
                <Alert
                  className="border-border bg-white"
                  variant={action.status === "error" ? "destructive" : "default"}
                >
                  <AlertTitle>
                    {action.status === "error" ? "Action failed" : "Action result"}
                  </AlertTitle>
                  <AlertDescription>{action.message}</AlertDescription>
                </Alert>
              ) : null}
            </div>
          </SectionPanel>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {providerMeta.map((meta) => {
            const connection = connectionState[meta.provider];
            const form = forms[meta.provider];
            const Icon = meta.icon;

            return (
              <Card className="border-border bg-white shadow-xs" key={meta.provider}>
                <CardHeader className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <CardTitle>{meta.title}</CardTitle>
                      <CardDescription>{meta.role}</CardDescription>
                    </div>
                    <span
                      className={`flex size-10 shrink-0 items-center justify-center rounded-lg border ${meta.accentClassName}`}
                    >
                      <Icon aria-hidden="true" size={18} />
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-muted-foreground">
                    {meta.description}
                  </p>
                </CardHeader>

                <CardContent className="space-y-4">
                  <div className="grid gap-2 sm:grid-cols-3">
                    {[
                      ["Status", statusLabel(connection)],
                      ["Owner", meta.owner],
                      ["Mode", connection.dry_run ? "Dry-run" : "Live"],
                    ].map(([label, value]) => (
                      <div
                        className="rounded-lg border border-border bg-surface-2 p-3"
                        key={label}
                      >
                        <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                          {label}
                        </div>
                        <div className="mt-1 text-sm font-medium text-foreground">
                          {value}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="grid gap-2">
                    {connectionSteps(connection).map((step) => (
                      <div
                        className="flex gap-3 rounded-lg border border-border bg-white p-3"
                        key={step.label}
                      >
                        {step.ready ? (
                          <CheckCircle2
                            aria-hidden="true"
                            className="mt-0.5 size-4 shrink-0 text-[var(--accent-text)]"
                          />
                        ) : (
                          <CircleDashed
                            aria-hidden="true"
                            className="mt-0.5 size-4 shrink-0 text-[#6F746F]"
                          />
                        )}
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-foreground">
                            {step.label}
                          </div>
                          <div className="mt-1 text-xs leading-5 text-muted-foreground">
                            {step.detail}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  <form className="space-y-3" onSubmit={(event) => saveConnection(meta.provider, event)}>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <Label htmlFor={`${meta.provider}-base-url`}>Base URL</Label>
                        <Input
                          disabled={!canManage}
                          id={`${meta.provider}-base-url`}
                          onChange={(event: ChangeEvent<HTMLInputElement>) =>
                            updateForm(meta.provider, "base_url", event.target.value)
                          }
                          placeholder={
                            meta.provider === "chatwoot"
                              ? "https://chat.example.com"
                              : "https://crm.example.com"
                          }
                          value={form.base_url}
                        />
                      </div>

                      {meta.provider === "chatwoot" ? (
                        <div className="space-y-1.5">
                          <Label htmlFor="chatwoot-account-id">Account ID</Label>
                          <Input
                            disabled={!canManage}
                            id="chatwoot-account-id"
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateForm("chatwoot", "account_id", event.target.value)
                            }
                            placeholder="1"
                            value={form.account_id}
                          />
                        </div>
                      ) : (
                        <div className="space-y-1.5">
                          <Label htmlFor="twenty-api-mode">API mode</Label>
                          <Input
                            disabled={!canManage}
                            id="twenty-api-mode"
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateForm("twenty", "api_mode", event.target.value)
                            }
                            value={form.api_mode}
                          />
                        </div>
                      )}
                    </div>

                    {meta.provider === "chatwoot" ? (
                      <div className="grid gap-3 sm:grid-cols-3">
                        <div className="space-y-1.5">
                          <Label htmlFor="chatwoot-inbox-id">Inbox identifier</Label>
                          <Input
                            disabled={!canManage}
                            id="chatwoot-inbox-id"
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateForm("chatwoot", "inbox_id", event.target.value)
                            }
                            placeholder="API channel identifier, not numeric inbox_id"
                            value={form.inbox_id}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="chatwoot-api-token">API token</Label>
                          <Input
                            disabled={!canManage}
                            id="chatwoot-api-token"
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateForm("chatwoot", "api_access_token", event.target.value)
                            }
                            placeholder={
                              connection.has_api_access_token
                                ? "Stored - leave blank"
                                : "Required"
                            }
                            type="password"
                            value={form.api_access_token}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor="chatwoot-webhook-token">Webhook token</Label>
                          <Input
                            disabled={!canManage}
                            id="chatwoot-webhook-token"
                            onChange={(event: ChangeEvent<HTMLInputElement>) =>
                              updateForm("chatwoot", "webhook_token", event.target.value)
                            }
                            placeholder={
                              connection.has_webhook_token
                                ? "Stored - leave blank"
                                : "Recommended"
                            }
                            type="password"
                            value={form.webhook_token}
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        <Label htmlFor="twenty-api-key">API key</Label>
                        <Input
                          disabled={!canManage}
                          id="twenty-api-key"
                          onChange={(event: ChangeEvent<HTMLInputElement>) =>
                            updateForm("twenty", "api_key", event.target.value)
                          }
                          placeholder={
                            connection.has_api_key
                              ? "Stored - leave blank"
                              : "Required"
                          }
                          type="password"
                          value={form.api_key}
                        />
                      </div>
                    )}

                    <div className="grid gap-3 rounded-lg border border-border bg-surface-2 p-3 sm:grid-cols-3">
                      {[
                        ["Enabled", "enabled", "Adapter can be used by Agent Studio."],
                        ["Dry-run", "dry_run", "Run safely without live writes."],
                        ["Allow writes", "allow_writes", "Still requires approval gates."],
                      ].map(([label, key, helper]) => (
                        <div className="space-y-2" key={key}>
                          <div className="flex items-center justify-between gap-3">
                            <Label className="text-xs" htmlFor={`${meta.provider}-${key}`}>
                              {label}
                            </Label>
                            <Switch
                              checked={Boolean(form[key as keyof ProviderForm])}
                              disabled={!canManage}
                              id={`${meta.provider}-${key}`}
                              onCheckedChange={(checked: boolean) =>
                                updateForm(
                                  meta.provider,
                                  key as keyof ProviderForm,
                                  checked,
                                )
                              }
                              size="sm"
                            />
                          </div>
                          <div className="text-[11px] leading-4 text-muted-foreground">
                            {helper}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button
                        className="bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)]"
                        disabled={!canManage || action.status === "saving"}
                        type="submit"
                      >
                        <Save aria-hidden="true" />
                        Save
                      </Button>
                      <Button
                        disabled={!canManage || action.status === "testing"}
                        onClick={() => testConnection(meta.provider)}
                        type="button"
                        variant="outline"
                      >
                        <TestTube2 aria-hidden="true" />
                        Test
                      </Button>
                      <Button
                        disabled={!canManage || action.status === "disabling"}
                        onClick={() => disableConnection(meta.provider)}
                        type="button"
                        variant="outline"
                      >
                        <Unplug aria-hidden="true" />
                        Disable
                      </Button>
                      {meta.provider === "chatwoot" ? (
                        <Button onClick={copyWebhookPath} type="button" variant="outline">
                          <Copy aria-hidden="true" />
                          Copy webhook path
                        </Button>
                      ) : null}
                    </div>
                  </form>
                </CardContent>
              </Card>
            );
          })}
        </div>

        <SectionPanel title="Planned Providers" eyebrow="Roadmap, not fake setup">
          <DataTable
            columns={[
              {
                key: "provider",
                label: "Provider",
                render: (row: FutureProviderRow) => (
                  <div className="space-y-1">
                    <div className="font-medium text-foreground">
                      {row.provider}
                    </div>
                    <div className="text-muted-foreground">{row.role}</div>
                  </div>
                ),
              },
              {
                key: "status",
                label: "Status",
                render: (row: FutureProviderRow) => (
                  <StatusChip tone={toneFromStatus(row.status)}>
                    {row.status}
                  </StatusChip>
                ),
              },
              {
                key: "access",
                label: "Access",
                render: (row: FutureProviderRow) => (
                  <Badge className="border-border" variant="outline">
                    {row.access}
                  </Badge>
                ),
              },
              {
                key: "owner",
                label: "Owner",
                render: (row: FutureProviderRow) => row.owner,
              },
              {
                key: "next",
                label: "Activation rule",
                render: (row: FutureProviderRow) => row.nextStep,
              },
            ]}
            rows={futureProviderRows}
          />
        </SectionPanel>

        <SectionPanel title="Backend Diagnostics" eyebrow="Recent Agent Studio events">
          <DataTable
            columns={[
              {
                key: "event",
                label: "Event",
                render: (row: DiagnosticEventView) => (
                  <div className="space-y-1">
                    <div className="font-medium text-foreground">
                      {row.event_type}
                    </div>
                    <div className="text-muted-foreground">{row.summary}</div>
                  </div>
                ),
              },
              {
                key: "status",
                label: "Status",
                render: (row: DiagnosticEventView) => (
                  <StatusChip tone={toneFromStatus(row.status)}>
                    {row.status}
                  </StatusChip>
                ),
              },
              {
                key: "conversation",
                label: "Conversation",
                render: (row: DiagnosticEventView) =>
                  row.conversation_id ? (
                    <Link
                      className="font-medium text-[#174EA6] underline-offset-2 hover:underline"
                      href={`/conversations?conversationId=${encodeURIComponent(
                        row.conversation_id,
                      )}`}
                    >
                      {row.conversation_id}
                    </Link>
                  ) : (
                    "Platform"
                  ),
              },
              {
                key: "provider",
                label: "Provider detail",
                render: (row: DiagnosticEventView) => {
                  const providerResult = isRecord(row.payload.provider_result)
                    ? row.payload.provider_result
                    : row.payload;
                  const httpStatus =
                    typeof providerResult.http_status === "number"
                      ? `HTTP ${providerResult.http_status}`
                      : "";
                  const errorType =
                    typeof providerResult.error_type === "string"
                      ? providerResult.error_type
                      : "";
                  const responseExcerpt =
                    typeof providerResult.response_excerpt === "string"
                      ? providerResult.response_excerpt
                      : "";
                  return (
                    <div className="space-y-1">
                      <div>{[httpStatus, errorType].filter(Boolean).join(" / ") || "n/a"}</div>
                      {responseExcerpt ? (
                        <div className="line-clamp-2 text-[11px] leading-4 text-muted-foreground">
                          {responseExcerpt}
                        </div>
                      ) : null}
                    </div>
                  );
                },
              },
              {
                key: "time",
                label: "Time",
                render: (row: DiagnosticEventView) =>
                  new Date(row.created_at).toLocaleString(),
              },
            ]}
            emptyLabel={diagnosticMessage}
            rows={diagnosticEvents}
          />
        </SectionPanel>

        <div className="grid gap-3 md:grid-cols-3">
          {[
            {
              label: "Monitor first",
              detail: "Operators see health, owner, and next action before setup work.",
              icon: Activity,
            },
            {
              label: "No direct provider calls",
              detail: "Browser routes through Sagad APIs; Agent Studio handles credentials.",
              icon: ShieldCheck,
            },
            {
              label: "Developer details moved",
              detail: "Adapter contracts and payloads live under Settings Advanced.",
              icon: RefreshCcw,
            },
          ].map(({ label, detail, icon: Icon }) => (
            <div
              className="rounded-lg border border-border bg-card p-4"
              key={label}
            >
              <Icon aria-hidden="true" className="mb-3 size-4 text-[var(--accent-text)]" />
              <div className="text-sm font-medium text-foreground">{label}</div>
              <div className="mt-1 text-xs leading-5 text-muted-foreground">
                {detail}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
