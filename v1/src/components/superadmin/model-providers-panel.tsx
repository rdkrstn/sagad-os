"use client";

import { useState } from "react";
import {
  AlertTriangle,
  Boxes,
  ChevronDown,
  FlaskConical,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusPill } from "@/components/product/product-ui";
import { cn } from "@/lib/utils";
import {
  updateModelProviders,
  type ModelProviderConfigUpsertRequest,
  type ModelProviderConfigView,
  type ModelProvidersView,
  type ModelProviderTestResult,
  type ProviderConfigView,
} from "@/lib/model-providers";

export type { ModelProvidersView };

const PROVIDER_LABELS: Record<string, string> = {
  none: "None (zero-credential)",
  openai: "OpenAI",
  fireworks: "Fireworks AI",
  ollama_cloud: "Ollama Cloud",
  openrouter: "OpenRouter",
  litellm: "LiteLLM Gateway",
};

const CHAT_OPTIONS = ["none", "openai", "fireworks", "ollama_cloud", "openrouter", "litellm"];
const EMBED_OPTIONS = ["auto", "none", "openai", "fireworks", "ollama_cloud", "litellm"];

type ProviderName = "openai" | "fireworks" | "ollama_cloud" | "openrouter" | "litellm";

type FormState = {
  chat_provider: string;
  embedding_provider: string;
  openai_base_url: string;
  openai_model: string;
  openai_embedding_model: string;
  openai_api_key: string;
  fireworks_base_url: string;
  fireworks_model: string;
  fireworks_embedding_model: string;
  fireworks_api_key: string;
  ollama_cloud_base_url: string;
  ollama_cloud_model: string;
  ollama_cloud_embedding_model: string;
  ollama_cloud_api_key: string;
  openrouter_model: string;
  openrouter_api_key: string;
  litellm_base_url: string;
  litellm_model: string;
  litellm_embedding_model: string;
  litellm_master_key: string;
  embedding_dimensions: string;
  classifier_model: string;
  guardrail_model: string;
  extractor_model: string;
  supervisor_model: string;
};

function formFromConfig(config: ModelProviderConfigView): FormState {
  const p = (c: ProviderConfigView) => ({
    base_url: c.base_url ?? "",
    model: c.model ?? "",
    embedding_model: c.embedding_model ?? "",
  });
  return {
    chat_provider: config.chat_provider,
    embedding_provider: config.embedding_provider,
    openai_base_url: p(config.openai).base_url,
    openai_model: p(config.openai).model,
    openai_embedding_model: p(config.openai).embedding_model,
    openai_api_key: "",
    fireworks_base_url: p(config.fireworks).base_url,
    fireworks_model: p(config.fireworks).model,
    fireworks_embedding_model: p(config.fireworks).embedding_model,
    fireworks_api_key: "",
    ollama_cloud_base_url: p(config.ollama_cloud).base_url,
    ollama_cloud_model: p(config.ollama_cloud).model,
    ollama_cloud_embedding_model: p(config.ollama_cloud).embedding_model,
    ollama_cloud_api_key: "",
    openrouter_model: config.openrouter.model ?? "",
    openrouter_api_key: "",
    litellm_base_url: p(config.litellm).base_url,
    litellm_model: p(config.litellm).model,
    litellm_embedding_model: p(config.litellm).embedding_model,
    litellm_master_key: "",
    embedding_dimensions: config.embedding_dimensions == null ? "" : String(config.embedding_dimensions),
    classifier_model: config.classifier_model ?? "",
    guardrail_model: config.guardrail_model ?? "",
    extractor_model: config.extractor_model ?? "",
    supervisor_model: config.supervisor_model ?? "",
  };
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
      placeholder={hasExisting ? "•••••••• (leave blank to keep stored key)" : "Paste API key"}
      type="password"
      value={value}
    />
  );
}

function FieldRow({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-1.5">
      <Label className="text-xs font-medium text-muted-foreground" htmlFor={htmlFor}>
        {label}
      </Label>
      {children}
    </div>
  );
}

function ProviderCard({
  name,
  form,
  setField,
  hasKey,
  showBaseUrl,
  showEmbedding,
}: {
  name: ProviderName;
  form: FormState;
  setField: (key: keyof FormState, value: string) => void;
  hasKey: boolean;
  showBaseUrl: boolean;
  showEmbedding: boolean;
}) {
  const prefix = name;
  const label = PROVIDER_LABELS[name] ?? name;
  const modelKey = `${prefix}_model` as keyof FormState;
  const baseUrlKey = `${prefix}_base_url` as keyof FormState;
  const embeddingKey = `${prefix}_embedding_model` as keyof FormState;
  const secretKey = (name === "openrouter" ? "openrouter_api_key" : name === "litellm" ? "litellm_master_key" : `${prefix}_api_key`) as keyof FormState;
  return (
    <div className="rounded-md border border-border bg-surface-2 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-foreground">{label}</span>
        <StatusPill tone={hasKey ? "good" : "neutral"}>{hasKey ? "key stored" : "no key"}</StatusPill>
      </div>
      <div className="grid gap-2.5">
        <FieldRow label="Model" htmlFor={`${prefix}-model`}>
          <Input
            className="font-mono text-xs"
            id={`${prefix}-model`}
            onChange={(event) => setField(modelKey, event.target.value)}
            value={form[modelKey] as string}
          />
        </FieldRow>
        {showBaseUrl ? (
          <FieldRow label="Base URL" htmlFor={`${prefix}-base-url`}>
            <Input
              className="font-mono text-xs"
              id={`${prefix}-base-url`}
              onChange={(event) => setField(baseUrlKey, event.target.value)}
              value={form[baseUrlKey] as string}
            />
          </FieldRow>
        ) : null}
        {showEmbedding ? (
          <FieldRow label="Embedding model" htmlFor={`${prefix}-embedding`}>
            <Input
              className="font-mono text-xs"
              id={`${prefix}-embedding`}
              onChange={(event) => setField(embeddingKey, event.target.value)}
              value={form[embeddingKey] as string}
            />
          </FieldRow>
        ) : null}
        <FieldRow label="API key" htmlFor={`${prefix}-api-key`}>
          <SecretInput
            hasExisting={hasKey}
            id={`${prefix}-api-key`}
            onChange={(next) => setField(secretKey, next)}
            value={form[secretKey] as string}
          />
        </FieldRow>
      </div>
    </div>
  );
}

export function ModelProvidersPanel({ initial }: { initial: ModelProvidersView }) {
  const [view, setView] = useState<ModelProvidersView>(initial);
  const [form, setForm] = useState<FormState>(() => formFromConfig(initial.config));
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; message: string } | null>(null);
  const [testResult, setTestResult] = useState<ModelProviderTestResult | null>(null);
  const [showOverrides, setShowOverrides] = useState(false);

  function setField(key: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function buildBody(): ModelProviderConfigUpsertRequest {
    const initialForm = formFromConfig(view.config);
    // Only persist fields the user actually changed (null = leave unchanged) so env stays
    // the source of truth for untouched fields.
    const diff = (key: keyof FormState): string | null => {
      const current = form[key];
      return current && current !== initialForm[key] ? current : null;
    };
    return {
      chat_provider: form.chat_provider,
      embedding_provider: form.embedding_provider,
      openai_base_url: diff("openai_base_url"),
      openai_model: diff("openai_model"),
      openai_embedding_model: diff("openai_embedding_model"),
      fireworks_base_url: diff("fireworks_base_url"),
      fireworks_model: diff("fireworks_model"),
      fireworks_embedding_model: diff("fireworks_embedding_model"),
      ollama_cloud_base_url: diff("ollama_cloud_base_url"),
      ollama_cloud_model: diff("ollama_cloud_model"),
      ollama_cloud_embedding_model: diff("ollama_cloud_embedding_model"),
      openrouter_model: diff("openrouter_model"),
      litellm_base_url: diff("litellm_base_url"),
      litellm_model: diff("litellm_model"),
      litellm_embedding_model: diff("litellm_embedding_model"),
      embedding_dimensions: form.embedding_dimensions && form.embedding_dimensions !== initialForm.embedding_dimensions
        ? Number(form.embedding_dimensions)
        : null,
      classifier_model: diff("classifier_model"),
      guardrail_model: diff("guardrail_model"),
      extractor_model: diff("extractor_model"),
      supervisor_model: diff("supervisor_model"),
      // Secrets: only send when the user typed a new value.
      openai_api_key: form.openai_api_key || null,
      fireworks_api_key: form.fireworks_api_key || null,
      ollama_cloud_api_key: form.ollama_cloud_api_key || null,
      openrouter_api_key: form.openrouter_api_key || null,
      litellm_master_key: form.litellm_master_key || null,
    };
  }

  async function handleSave() {
    setSaving(true);
    setFeedback(null);
    try {
      const result = await updateModelProviders(buildBody());
      setView((current) => ({
        ...current,
        active: result.active,
        config: result.config,
      }));
      setForm(formFromConfig(result.config));
      setFeedback({ ok: true, message: `Saved. Active chat provider: ${result.active}.` });
    } catch (error) {
      setFeedback({ ok: false, message: error instanceof Error ? error.message : "Save failed." });
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setFeedback(null);
    try {
      const response = await fetch("/api/admin/model-providers/test", { method: "POST" });
      const data = (await response.json()) as ModelProviderTestResult & { detail?: string };
      if (response.ok && data.chat && data.embedding) {
        setTestResult(data);
      } else {
        setFeedback({ ok: false, message: data.detail ?? `Test failed (HTTP ${response.status}).` });
      }
    } catch (error) {
      setFeedback({ ok: false, message: error instanceof Error ? error.message : "Test failed." });
    } finally {
      setTesting(false);
    }
  }

  const cfg = view.config;

  return (
    <div className="space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Boxes aria-hidden="true" className="text-[var(--accent-text)]" size={15} />
        <span className="text-sm font-semibold">Active: {PROVIDER_LABELS[view.active] ?? view.active}</span>
        <StatusPill tone={view.active === "none" ? "info" : "good"}>
          {view.active === "none" ? "dry-run" : "active"}
        </StatusPill>
        <span className="ml-auto text-[11px] text-muted-foreground">
          Encrypted at rest · per-org config
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <FieldRow label="Chat provider" htmlFor="mp-chat-provider">
          <Select onValueChange={(value) => setField("chat_provider", value)} value={form.chat_provider}>
            <SelectTrigger id="mp-chat-provider">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CHAT_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {PROVIDER_LABELS[option] ?? option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldRow>
        <FieldRow label="Embedding provider" htmlFor="mp-embedding-provider">
          <Select onValueChange={(value) => setField("embedding_provider", value)} value={form.embedding_provider}>
            <SelectTrigger id="mp-embedding-provider">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {EMBED_OPTIONS.map((option) => (
                <SelectItem key={option} value={option}>
                  {option === "auto" ? "auto (follow chat)" : PROVIDER_LABELS[option] ?? option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </FieldRow>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <ProviderCard name="openai" form={form} setField={setField} hasKey={cfg.openai.has_api_key} showBaseUrl showEmbedding />
        <ProviderCard name="fireworks" form={form} setField={setField} hasKey={cfg.fireworks.has_api_key} showBaseUrl showEmbedding />
        <ProviderCard name="ollama_cloud" form={form} setField={setField} hasKey={cfg.ollama_cloud.has_api_key} showBaseUrl showEmbedding />
        <ProviderCard name="openrouter" form={form} setField={setField} hasKey={cfg.openrouter.has_api_key} showBaseUrl={false} showEmbedding={false} />
        <ProviderCard name="litellm" form={form} setField={setField} hasKey={cfg.litellm.has_api_key} showBaseUrl showEmbedding />
      </div>

      <div className="rounded-md border border-border">
        <button
          aria-expanded={showOverrides}
          className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm font-medium"
          onClick={() => setShowOverrides((current) => !current)}
          type="button"
        >
          <span>Per-node model overrides + embedding dimensions</span>
          <ChevronDown aria-hidden="true" className={cn("size-4 transition-transform", !showOverrides && "-rotate-90")} />
        </button>
        {showOverrides ? (
          <div className="grid gap-2.5 border-t border-border p-3 md:grid-cols-2">
            <FieldRow label="Embedding dimensions" htmlFor="mp-embedding-dimensions">
              <Input
                id="mp-embedding-dimensions"
                onChange={(event) => setField("embedding_dimensions", event.target.value)}
                placeholder="e.g. 768 (blank = model default)"
                type="number"
                value={form.embedding_dimensions}
              />
            </FieldRow>
            <FieldRow label="Classifier model" htmlFor="mp-classifier">
              <Input className="font-mono text-xs" id="mp-classifier" onChange={(event) => setField("classifier_model", event.target.value)} value={form.classifier_model} />
            </FieldRow>
            <FieldRow label="Guardrail model" htmlFor="mp-guardrail">
              <Input className="font-mono text-xs" id="mp-guardrail" onChange={(event) => setField("guardrail_model", event.target.value)} value={form.guardrail_model} />
            </FieldRow>
            <FieldRow label="Extractor model" htmlFor="mp-extractor">
              <Input className="font-mono text-xs" id="mp-extractor" onChange={(event) => setField("extractor_model", event.target.value)} value={form.extractor_model} />
            </FieldRow>
            <FieldRow label="Supervisor model" htmlFor="mp-supervisor">
              <Input className="font-mono text-xs" id="mp-supervisor" onChange={(event) => setField("supervisor_model", event.target.value)} value={form.supervisor_model} />
            </FieldRow>
          </div>
        ) : null}
      </div>

      {feedback ? (
        <p className={cn("flex items-center gap-1.5 text-xs", feedback.ok ? "text-[var(--accent-text)]" : "text-danger")}>
          {feedback.ok ? <CheckCircle2 aria-hidden="true" size={13} /> : <AlertTriangle aria-hidden="true" size={13} />}
          {feedback.message}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={saving} onClick={handleSave} type="button">
          {saving ? <Loader2 aria-hidden="true" size={14} className="animate-spin" /> : <CheckCircle2 aria-hidden="true" size={14} />}
          Save
        </Button>
        <Button disabled={testing} onClick={handleTest} size="sm" type="button" variant="outline">
          {testing ? <Loader2 aria-hidden="true" size={14} className="animate-spin" /> : <FlaskConical aria-hidden="true" size={14} />}
          Test active provider
        </Button>
        {view.source === "mock" ? (
          <span className="text-[11px] text-muted-foreground">{view.detail}</span>
        ) : null}
      </div>

      {testResult ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {([
            ["Chat", testResult.chat],
            ["Embedding", testResult.embedding],
          ] as const).map(([label, result]) => (
            <div
              key={label}
              className={cn(
                "flex items-start gap-2 rounded-md border p-2 text-xs",
                result.ok ? "border-[var(--sui-green-border)] bg-[var(--sui-green-soft)]" : "border-[var(--danger-border)] bg-[var(--danger-soft)]",
              )}
            >
              {result.ok ? (
                <CheckCircle2 aria-hidden="true" className="mt-0.5 shrink-0 text-[var(--accent-text)]" size={14} />
              ) : (
                <XCircle aria-hidden="true" className="mt-0.5 shrink-0 text-danger" size={14} />
              )}
              <div className="min-w-0">
                <div className="font-semibold">{label}</div>
                <div className={result.ok ? "text-[var(--accent-text)]" : "text-danger"}>{result.detail}</div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
