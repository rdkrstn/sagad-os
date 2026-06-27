"use client";

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  PlugZap,
  Power,
  Pencil,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { StatusPill, toneFromProductStatus } from "@/components/product/product-ui";
import { cn } from "@/lib/utils";
import type { IntegrationConnectionView } from "@/lib/api";

type Provider = IntegrationConnectionView["provider"];

type SaveState = {
  status: "idle" | "saving" | "saved" | "error";
  message: string;
};

type TestState = {
  status: "idle" | "running" | "done";
  result?: { status: string; detail: string };
};

const PROVIDER_ORDER: Provider[] = ["ghl", "chatwoot", "twenty"];

function providerOrderKey(provider: string): number {
  const index = PROVIDER_ORDER.indexOf(provider as Provider);
  return index === -1 ? 99 : index;
}

function FieldRow({
  label,
  htmlFor,
  children,
  hint,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs font-medium text-muted-foreground" htmlFor={htmlFor}>
        {label}
      </Label>
      {children}
      {hint ? <p className="text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

function SecretInput({
  id,
  value,
  onChange,
  hasExisting,
}: {
  id: string;
  value: string;
  onChange: (next: string) => void;
  hasExisting: boolean;
}) {
  return (
    <Input
      autoComplete="off"
      className="font-mono text-xs"
      id={id}
      onChange={(event) => onChange(event.target.value)}
      placeholder={hasExisting ? "•••••••• (leave blank to keep stored value)" : "Enter secret value"}
      type="password"
      value={value}
    />
  );
}

function ToggleRow({
  id,
  label,
  description,
  checked,
  onCheckedChange,
}: {
  id: string;
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-2 p-3">
      <div className="min-w-0">
        <Label className="text-sm font-medium" htmlFor={id}>
          {label}
        </Label>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch checked={checked} id={id} onCheckedChange={onCheckedChange} />
    </div>
  );
}

function AdapterConfigCard({ connection }: { connection: IntegrationConnectionView }) {
  const provider = connection.provider;
  const [open, setOpen] = useState(false);

  // Form state (non-secret fields seeded from the connection; secrets blank).
  const [baseUrl, setBaseUrl] = useState(connection.base_url ?? "");
  const [enabled, setEnabled] = useState(connection.enabled);
  const [dryRun, setDryRun] = useState(connection.dry_run);
  const [allowWrites, setAllowWrites] = useState(connection.writes_enabled);

  // chatwoot
  const [accountId, setAccountId] = useState(connection.account_id ?? "");
  const [inboxId, setInboxId] = useState(connection.inbox_id ?? "");
  const [apiAccessToken, setApiAccessToken] = useState("");
  const [webhookToken, setWebhookToken] = useState("");

  // twenty
  const [apiKey, setApiKey] = useState("");
  const [apiMode, setApiMode] = useState(connection.api_mode ?? "graphql");

  // ghl
  const [locationId, setLocationId] = useState(connection.location_id ?? "");
  const [outboundMode, setOutboundMode] = useState(connection.outbound_mode ?? "webhook");
  const [signatureScheme, setSignatureScheme] = useState(connection.signature_scheme ?? "hmac");
  const [pollEnabled, setPollEnabled] = useState(connection.poll_enabled ?? false);
  const [pollInterval, setPollInterval] = useState(connection.poll_interval_seconds ?? 30);
  const [webhookSecret, setWebhookSecret] = useState("");
  const [nativeWebhookKey, setNativeWebhookKey] = useState("");

  const [save, setSave] = useState<SaveState>({ status: "idle", message: "" });
  const [test, setTest] = useState<TestState>({ status: "idle" });

  function buildPayload(): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      base_url: baseUrl || null,
      enabled,
      dry_run: dryRun,
    };
    if (provider === "chatwoot") {
      payload.account_id = accountId || null;
      payload.inbox_id = inboxId || null;
      payload.allow_writes = allowWrites;
      if (apiAccessToken) payload.api_access_token = apiAccessToken;
      if (webhookToken) payload.webhook_token = webhookToken;
    } else if (provider === "twenty") {
      payload.api_mode = apiMode;
      payload.allow_writes = allowWrites;
      if (apiKey) payload.api_key = apiKey;
    } else if (provider === "ghl") {
      payload.location_id = locationId || null;
      payload.outbound_mode = outboundMode;
      payload.signature_scheme = signatureScheme;
      payload.poll_enabled = pollEnabled;
      payload.poll_interval_seconds = pollInterval;
      if (apiKey) payload.api_key = apiKey;
      if (webhookSecret) payload.webhook_secret = webhookSecret;
      if (nativeWebhookKey) payload.native_webhook_key = nativeWebhookKey;
    }
    return payload;
  }

  async function handleSave() {
    setSave({ status: "saving", message: "" });
    try {
      const response = await fetch(`/api/integrations/${provider}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      const data = (await response.json()) as { detail?: string; status?: string };
      if (response.ok) {
        setSave({ status: "saved", message: `Saved. Status: ${data.status ?? "updated"}.` });
        // Clear typed secrets so the stored value is retained on next save.
        setApiAccessToken("");
        setWebhookToken("");
        setApiKey("");
        setWebhookSecret("");
        setNativeWebhookKey("");
      } else {
        setSave({ status: "error", message: data.detail ?? `Save failed (HTTP ${response.status}).` });
      }
    } catch (error) {
      setSave({ status: "error", message: error instanceof Error ? error.message : "Save failed." });
    }
  }

  async function handleTest() {
    setTest({ status: "running" });
    try {
      const response = await fetch(`/api/integrations/${provider}/test`, { method: "POST" });
      const data = (await response.json()) as { status?: string; detail?: string };
      setTest({
        status: "done",
        result: { status: data.status ?? "error", detail: data.detail ?? "No detail returned." },
      });
    } catch (error) {
      setTest({
        status: "done",
        result: { status: "error", detail: error instanceof Error ? error.message : "Test failed." },
      });
    }
  }

  async function handleDisable() {
    setSave({ status: "saving", message: "" });
    try {
      const response = await fetch(`/api/integrations/${provider}/disable`, { method: "POST" });
      const data = (await response.json()) as { detail?: string; status?: string };
      if (response.ok) {
        setEnabled(false);
        setSave({ status: "saved", message: `${connection.name} disabled.` });
      } else {
        setSave({ status: "error", message: data.detail ?? `Disable failed (HTTP ${response.status}).` });
      }
    } catch (error) {
      setSave({ status: "error", message: error instanceof Error ? error.message : "Disable failed." });
    }
  }

  const missing = connection.missing;
  const statusTone = toneFromProductStatus(connection.status);

  return (
    <div className="grid gap-3 border-b border-border px-4 py-4 last:border-b-0 lg:grid-cols-[minmax(0,1fr)_220px_160px]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-foreground">{connection.name}</span>
          <span className="font-mono text-[10px] uppercase text-muted-foreground">{connection.kind}</span>
          <StatusPill tone={statusTone}>{connection.status}</StatusPill>
        </div>
        <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{connection.detail}</p>
        {missing.length > 0 ? (
          <p className="mt-1 text-[11px] text-muted-foreground">
            Missing: {missing.join(", ")}
          </p>
        ) : null}
        {test.status === "done" && test.result ? (
          <p
            className={cn(
              "mt-2 flex items-center gap-1.5 text-[11px]",
              test.result.status === "ready" ? "text-[var(--accent-text)]" : "text-danger",
            )}
          >
            {test.result.status === "ready" ? (
              <CheckCircle2 aria-hidden="true" size={13} />
            ) : (
              <XCircle aria-hidden="true" size={13} />
            )}
            {test.result.detail}
          </p>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs lg:grid-cols-1">
        {provider === "ghl" ? (
          <>
            <Stat label="Outbound" value={connection.outbound_mode ?? "—"} />
            <Stat label="Poller" value={connection.poll_enabled ? `${connection.poll_interval_seconds ?? 30}s` : "off"} />
          </>
        ) : (
          <>
            <Stat label="Mode" value={connection.api_mode ?? "—"} />
            <Stat label="Writes" value={connection.writes_enabled ? "Live" : "Gated"} />
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
        <Button onClick={handleTest} size="sm" type="button" variant="outline">
          {test.status === "running" ? <Loader2 aria-hidden="true" size={14} className="animate-spin" /> : null}
          Test
        </Button>
        <Button
          disabled={save.status === "saving" || !connection.enabled}
          onClick={handleDisable}
          size="sm"
          type="button"
          variant="ghost"
        >
          <Power aria-hidden="true" size={14} /> Disable
        </Button>
        <Dialog onOpenChange={setOpen} open={open}>
          <DialogTrigger asChild>
            <Button size="sm" type="button" variant="outline">
              <Pencil aria-hidden="true" size={14} /> Configure
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Configure {connection.name}</DialogTitle>
              <DialogDescription>
                Credentials are stored encrypted in Agent Studio. Existing secrets are kept unless you enter a new value.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-3 py-2">
              <FieldRow label="Base URL" htmlFor={`${provider}-base-url`}>
                <Input
                  className="font-mono text-xs"
                  id={`${provider}-base-url`}
                  onChange={(event) => setBaseUrl(event.target.value)}
                  value={baseUrl}
                />
              </FieldRow>

              {provider === "chatwoot" ? (
                <>
                  <FieldRow label="Account ID" htmlFor="chatwoot-account-id">
                    <Input id="chatwoot-account-id" onChange={(event) => setAccountId(event.target.value)} value={accountId} />
                  </FieldRow>
                  <FieldRow label="Inbox identifier" htmlFor="chatwoot-inbox-id" hint="Public inbox identifier, not the numeric inbox id.">
                    <Input id="chatwoot-inbox-id" onChange={(event) => setInboxId(event.target.value)} value={inboxId} />
                  </FieldRow>
                  <FieldRow label="API access token" htmlFor="chatwoot-api-token">
                    <SecretInput hasExisting={connection.has_api_access_token} id="chatwoot-api-token" onChange={setApiAccessToken} value={apiAccessToken} />
                  </FieldRow>
                  <FieldRow label="Webhook token" htmlFor="chatwoot-webhook-token">
                    <SecretInput hasExisting={connection.has_webhook_token} id="chatwoot-webhook-token" onChange={setWebhookToken} value={webhookToken} />
                  </FieldRow>
                </>
              ) : null}

              {provider === "twenty" ? (
                <>
                  <FieldRow label="API key" htmlFor="twenty-api-key">
                    <SecretInput hasExisting={connection.has_api_key} id="twenty-api-key" onChange={setApiKey} value={apiKey} />
                  </FieldRow>
                  <FieldRow label="API mode" htmlFor="twenty-api-mode">
                    <Select onValueChange={setApiMode} value={apiMode}>
                      <SelectTrigger id="twenty-api-mode">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="graphql">GraphQL</SelectItem>
                        <SelectItem value="rest">REST</SelectItem>
                      </SelectContent>
                    </Select>
                  </FieldRow>
                </>
              ) : null}

              {provider === "ghl" ? (
                <>
                  <FieldRow label="API key (Private Integration Token)" htmlFor="ghl-api-key">
                    <SecretInput hasExisting={connection.has_api_key} id="ghl-api-key" onChange={setApiKey} value={apiKey} />
                  </FieldRow>
                  <FieldRow label="Location ID" htmlFor="ghl-location-id">
                    <Input className="font-mono text-xs" id="ghl-location-id" onChange={(event) => setLocationId(event.target.value)} value={locationId} />
                  </FieldRow>
                  <FieldRow label="Outbound mode" htmlFor="ghl-outbound-mode">
                    <Select onValueChange={setOutboundMode} value={outboundMode}>
                      <SelectTrigger id="ghl-outbound-mode">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="webhook">webhook (live send)</SelectItem>
                        <SelectItem value="mcp">mcp (descriptor-only dry-run)</SelectItem>
                      </SelectContent>
                    </Select>
                  </FieldRow>
                  <FieldRow label="Signature scheme" htmlFor="ghl-signature-scheme" hint="hmac for Workflow/Custom webhook; ed25519 for the native InboundMessage webhook.">
                    <Select onValueChange={setSignatureScheme} value={signatureScheme}>
                      <SelectTrigger id="ghl-signature-scheme">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="hmac">hmac</SelectItem>
                        <SelectItem value="ed25519">ed25519</SelectItem>
                      </SelectContent>
                    </Select>
                  </FieldRow>
                  <FieldRow label="Webhook secret" htmlFor="ghl-webhook-secret">
                    <SecretInput hasExisting={connection.has_webhook_secret} id="ghl-webhook-secret" onChange={setWebhookSecret} value={webhookSecret} />
                  </FieldRow>
                  <FieldRow label="Native webhook public key (ed25519)" htmlFor="ghl-native-key">
                    <SecretInput hasExisting={connection.has_native_webhook_key} id="ghl-native-key" onChange={setNativeWebhookKey} value={nativeWebhookKey} />
                  </FieldRow>
                  <FieldRow label="Poll interval (seconds)" htmlFor="ghl-poll-interval">
                    <Input
                      id="ghl-poll-interval"
                      max={3600}
                      min={5}
                      onChange={(event) => setPollInterval(Number(event.target.value) || 30)}
                      type="number"
                      value={pollInterval}
                    />
                  </FieldRow>
                </>
              ) : null}

              <ToggleRow
                checked={enabled}
                description="When off, Agent Studio ignores this adapter entirely."
                id={`${provider}-enabled`}
                label="Enabled"
                onCheckedChange={setEnabled}
              />
              <ToggleRow
                checked={dryRun}
                description="Dry-run gates outbound writes; inbound still flows."
                id={`${provider}-dry-run`}
                label="Dry-run"
                onCheckedChange={setDryRun}
              />
              {provider !== "ghl" ? (
                <ToggleRow
                  checked={allowWrites}
                  description="Allow live outbound writes when enabled and not dry-run."
                  id={`${provider}-allow-writes`}
                  label="Allow writes"
                  onCheckedChange={setAllowWrites}
                />
              ) : null}
              {provider === "ghl" ? (
                <ToggleRow
                  checked={pollEnabled}
                  description="Run the background GHL inbound poller."
                  id="ghl-poll-enabled"
                  label="Poller enabled"
                  onCheckedChange={setPollEnabled}
                />
              ) : null}
            </div>

            {save.status === "error" ? (
              <p className="flex items-center gap-1.5 text-xs text-danger">
                <AlertTriangle aria-hidden="true" size={13} /> {save.message}
              </p>
            ) : null}
            {save.status === "saved" ? (
              <p className="flex items-center gap-1.5 text-xs text-[var(--accent-text)]">
                <CheckCircle2 aria-hidden="true" size={13} /> {save.message}
              </p>
            ) : null}

            <DialogFooter>
              <Button
                disabled={save.status === "saving"}
                onClick={handleSave}
                type="button"
              >
                {save.status === "saving" ? <Loader2 aria-hidden="true" size={14} className="animate-spin" /> : null}
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface-2 p-2">
      <div className="font-mono text-[10px] uppercase text-muted-foreground">{label}</div>
      <div className="mt-0.5 truncate text-xs font-semibold text-foreground">{value}</div>
    </div>
  );
}

export function AdaptersConsole({ connections }: { connections: IntegrationConnectionView[] }) {
  const ordered = [...connections].sort(
    (a, b) => providerOrderKey(a.provider) - providerOrderKey(b.provider),
  );
  const connected = connections.filter((row) => row.configured && row.enabled).length;

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Adapters" value={String(connections.length)} />
        <Stat label="Connected" value={String(connected)} />
        <Stat label="Browser secrets" value="0" />
      </div>
      <div className="rounded-md border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <PlugZap aria-hidden="true" size={15} className="text-[var(--accent-text)]" />
          <div className="text-sm font-semibold">Adapter connections</div>
          <span className="ml-auto text-[11px] text-muted-foreground">
            Credentials encrypted at rest · server-side only
          </span>
        </div>
        {ordered.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">No adapters provisioned.</p>
        ) : (
          ordered.map((connection) => (
            <AdapterConfigCard connection={connection} key={connection.provider} />
          ))
        )}
      </div>
    </div>
  );
}
