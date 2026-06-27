import { KeyRound, Lock } from "lucide-react";
import { StatusPill } from "@/components/product/product-ui";
import type { IntegrationConnectionView } from "@/lib/api";

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "—";
}

function SecretFlag({ label, set }: { label: string; set: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface-2 px-3 py-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <StatusPill tone={set ? "good" : "neutral"}>{set ? "stored" : "missing"}</StatusPill>
    </div>
  );
}

export function SecretsPolicyPanel({ connections }: { connections: IntegrationConnectionView[] }) {
  return (
    <div className="space-y-3 p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Lock aria-hidden="true" className="text-[var(--accent-text)]" size={14} />
        Secrets are encrypted at rest (<code className="font-mono">pgp_sym_encrypt</code>) in Agent Studio and never returned to the browser — only stored/missing booleans are shown here.
      </div>

      <div className="rounded-md border border-border bg-surface-2 p-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-2 font-semibold text-foreground">
          <KeyRound aria-hidden="true" className="text-[var(--accent-text)]" size={14} />
          Encryption key
        </div>
        <p className="mt-1.5 leading-5">
          The integration-secret encryption key is managed by Agent Studio via
          <code className="ml-1 font-mono">SAGAD_INTEGRATION_ENCRYPTION_KEY</code>
          (falling back to the internal secret). Rotate it on the Agent Studio side; a live status
          endpoint is a tracked follow-up.
        </p>
      </div>

      <div className="space-y-3">
        {connections.map((connection) => (
          <div className="rounded-md border border-border p-3" key={connection.provider}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-foreground">{connection.name}</span>
              <span className="font-mono text-[10px] uppercase text-muted-foreground">
                updated {formatDate(connection.updated_at)}
              </span>
            </div>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {connection.provider === "chatwoot" ? (
                <>
                  <SecretFlag label="API access token" set={connection.has_api_access_token} />
                  <SecretFlag label="Webhook token" set={connection.has_webhook_token} />
                </>
              ) : connection.provider === "ghl" ? (
                <>
                  <SecretFlag label="API key" set={connection.has_api_key} />
                  <SecretFlag label="Webhook secret" set={connection.has_webhook_secret} />
                  <SecretFlag label="Native webhook key" set={connection.has_native_webhook_key} />
                </>
              ) : (
                <SecretFlag label="API key" set={connection.has_api_key} />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
