import { Bot, Network, ShieldCheck, Wrench } from "lucide-react";
import {
  CodeBlock,
  MetricCard,
  Panel,
  SourcePill,
  StatusPill,
  TerminalBlock,
} from "@/components/product/product-ui";
import { asRecord, textOf } from "@/components/ui/data-access";

const agentStudioEnv = `LITELLM_ENABLED=true
LITELLM_BASE_URL=http://127.0.0.1:4000/v1
OPENAI_BASE_URL=http://127.0.0.1:4000/v1
OPENAI_MODEL=sagad-openai-fast`;

const liteLlmAliases = `sagad-openai-fast
sagad-openai-reasoning
sagad-deepseek-chat
sagad-openai-embedding`;

export function ModelGatewayConsole({ status }: { status: unknown }) {
  const row = asRecord(status);
  const agentStudioStatus = textOf(row, ["agentStudioStatus"], "not_configured");
  const gatewayStatus = textOf(row, ["status"], "unknown");
  const connected = agentStudioStatus === "connected";
  const ready = gatewayStatus.toLowerCase() === "ready";

  return (
    <div className="space-y-4">
      <section className="grid gap-3 md:grid-cols-4">
        <MetricCard
          detail="Console never calls LiteLLM directly"
          icon={ShieldCheck}
          label="Boundary"
          value="Server-side"
        />
        <MetricCard
          detail="Reported by Agent Studio"
          icon={Network}
          label="Agent Studio"
          value={connected ? "Connected" : "Unavailable"}
        />
        <MetricCard
          detail="OpenAI-compatible /v1"
          icon={Bot}
          label="Gateway"
          value={gatewayStatus}
        />
        <MetricCard
          detail="OpenAI and DeepSeek aliases"
          icon={Wrench}
          label="Model aliases"
          value="4"
        />
      </section>

      <Panel
        action={<StatusPill status={gatewayStatus}>{gatewayStatus}</StatusPill>}
        title="LiteLLM Model Gateway"
        eyebrow="Observe"
      >
        <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="space-y-3">
            <p className="text-sm leading-6 text-muted-foreground">
              {textOf(row, ["detail"], "LiteLLM status is unavailable.")}
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-md border border-border bg-surface-2 p-3">
                <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                  Agent Studio URL
                </div>
                <div className="mt-1 break-all text-sm font-semibold text-foreground">
                  {textOf(row, ["agentStudioBaseUrl"], "Not configured")}
                </div>
              </div>
              <div className="rounded-md border border-border bg-surface-2 p-3">
                <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
                  LiteLLM URL
                </div>
                <div className="mt-1 break-all text-sm font-semibold text-foreground">
                  {textOf(row, ["baseUrl"], "http://127.0.0.1:4000/v1")}
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <SourcePill>{textOf(row, ["boundary"], "Agent Studio server-side only")}</SourcePill>
              <SourcePill>{textOf(row, ["mode"], "OpenAI-compatible /v1 model gateway")}</SourcePill>
              <SourcePill>{ready ? "Readiness passed" : "Setup required"}</SourcePill>
            </div>
          </div>

          <div className="rounded-md border border-border bg-card p-3">
            <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
              Required Agent Studio env
            </div>
            <CodeBlock className="mt-2" code={agentStudioEnv} />
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Start LiteLLM" eyebrow="Docker profile">
          <div className="space-y-3 p-4">
            <TerminalBlock
              lines={[
                {
                  label: "$ ",
                  text: textOf(
                    row,
                    ["setupCommand"],
                    "docker compose -f compose.preview.yaml --profile litellm up -d litellm",
                  ),
                },
              ]}
            />
            <p className="text-sm leading-6 text-muted-foreground">
              Docker must be running before this profile can start. Agent Studio should point model calls at the private `/v1` endpoint.
            </p>
          </div>
        </Panel>

        <Panel title="Configured Aliases" eyebrow="infra/litellm/config.example.yaml">
          <div className="p-4">
            <CodeBlock code={liteLlmAliases} />
          </div>
        </Panel>
      </div>
    </div>
  );
}
