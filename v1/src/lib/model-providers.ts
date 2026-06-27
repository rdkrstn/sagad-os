// Client-safe model-provider types + helpers (no server-only imports).
//
// @/lib/api/index.ts imports auth.ts (fs/pg/nodemailer) for its server-side fetchers, so it
// cannot be imported into a client component. This module is pure (types + fetch + parsers),
// so the SuperAdmin Model Providers panel can import it without pulling node built-ins into
// the client bundle.

export type ProviderStatusView = {
  provider: string;
  active: boolean;
  embedding_active: boolean;
  configured: boolean;
  embedding_configured: boolean;
  base_url: string | null;
  model: string | null;
  detail: string;
};

export type ProviderConfigView = {
  base_url: string | null;
  model: string | null;
  embedding_model: string | null;
  has_api_key: boolean;
};

export type ModelProviderConfigView = {
  chat_provider: string;
  embedding_provider: string;
  openai: ProviderConfigView;
  fireworks: ProviderConfigView;
  ollama_cloud: ProviderConfigView;
  openrouter: { model: string | null; has_api_key: boolean };
  litellm: ProviderConfigView;
  embedding_dimensions: number | null;
  classifier_model: string | null;
  guardrail_model: string | null;
  extractor_model: string | null;
  supervisor_model: string | null;
};

export type ModelProvidersView = {
  active: string;
  embedding_active: string;
  chat_model: string;
  embedding_model: string | null;
  embedding_dimensions: number;
  providers: ProviderStatusView[];
  config: ModelProviderConfigView;
  source: "agent-studio" | "mock";
  detail: string;
};

export type ModelProviderConfigUpsertRequest = {
  chat_provider?: string;
  embedding_provider?: string;
  openai_base_url?: string | null;
  openai_model?: string | null;
  openai_embedding_model?: string | null;
  fireworks_base_url?: string | null;
  fireworks_model?: string | null;
  fireworks_embedding_model?: string | null;
  ollama_cloud_base_url?: string | null;
  ollama_cloud_model?: string | null;
  ollama_cloud_embedding_model?: string | null;
  openrouter_model?: string | null;
  litellm_base_url?: string | null;
  litellm_model?: string | null;
  litellm_embedding_model?: string | null;
  embedding_dimensions?: number | null;
  classifier_model?: string | null;
  guardrail_model?: string | null;
  extractor_model?: string | null;
  supervisor_model?: string | null;
  openai_api_key?: string | null;
  fireworks_api_key?: string | null;
  ollama_cloud_api_key?: string | null;
  openrouter_api_key?: string | null;
  litellm_master_key?: string | null;
};

export type ModelProviderTestResult = {
  chat: { ok: boolean; detail: string; model: string };
  embedding: { ok: boolean; detail: string; model: string };
};

export function readConfig(payload: unknown): ModelProviderConfigView | null {
  if (!payload || typeof payload !== "object") return null;
  const c = payload as Record<string, unknown>;
  const provider = (raw: unknown, withBaseUrl = true, withEmbedding = true): ProviderConfigView => {
    const p = (raw ?? {}) as Record<string, unknown>;
    return {
      base_url: withBaseUrl && p.base_url ? String(p.base_url) : null,
      model: p.model ? String(p.model) : null,
      embedding_model: withEmbedding && p.embedding_model ? String(p.embedding_model) : null,
      has_api_key: Boolean(p.has_api_key),
    };
  };
  const orRaw = (c.openrouter ?? {}) as Record<string, unknown>;
  return {
    chat_provider: String(c.chat_provider ?? "none"),
    embedding_provider: String(c.embedding_provider ?? "auto"),
    openai: provider(c.openai),
    fireworks: provider(c.fireworks),
    ollama_cloud: provider(c.ollama_cloud),
    openrouter: { model: orRaw.model ? String(orRaw.model) : null, has_api_key: Boolean(orRaw.has_api_key) },
    litellm: provider(c.litellm),
    embedding_dimensions: c.embedding_dimensions == null ? null : Number(c.embedding_dimensions),
    classifier_model: c.classifier_model ? String(c.classifier_model) : null,
    guardrail_model: c.guardrail_model ? String(c.guardrail_model) : null,
    extractor_model: c.extractor_model ? String(c.extractor_model) : null,
    supervisor_model: c.supervisor_model ? String(c.supervisor_model) : null,
  };
}

export function mockConfig(): ModelProviderConfigView {
  const empty = (model: string | null, baseUrl: string | null = null, embeddingModel: string | null = null): ProviderConfigView => ({
    base_url: baseUrl,
    model,
    embedding_model: embeddingModel,
    has_api_key: false,
  });
  return {
    chat_provider: "none",
    embedding_provider: "auto",
    openai: empty("gpt-4o-mini", null, "text-embedding-3-small"),
    fireworks: empty("accounts/fireworks/models/llama-v3p1-70b-instruct", "https://api.fireworks.ai/inference/v1", "nomic-embed-v1"),
    ollama_cloud: empty("llama3.1", null, "nomic-embed-text"),
    openrouter: { model: "openai/gpt-4o-mini", has_api_key: false },
    litellm: empty(null, null, null),
    embedding_dimensions: null,
    classifier_model: null,
    guardrail_model: null,
    extractor_model: null,
    supervisor_model: null,
  };
}

export function mockModelProviders(): ModelProvidersView {
  return {
    active: "none",
    embedding_active: "none",
    chat_model: "",
    embedding_model: null,
    embedding_dimensions: 1536,
    config: mockConfig(),
    providers: [
      {
        provider: "none",
        active: true,
        embedding_active: true,
        configured: true,
        embedding_configured: false,
        base_url: null,
        model: null,
        detail: "Zero-credential default (DryRun chat + deterministic embeddings).",
      },
      {
        provider: "openai",
        active: false,
        embedding_active: false,
        configured: false,
        embedding_configured: false,
        base_url: null,
        model: "gpt-4o-mini",
        detail: "not configured",
      },
      {
        provider: "fireworks",
        active: false,
        embedding_active: false,
        configured: false,
        embedding_configured: false,
        base_url: "https://api.fireworks.ai/inference/v1",
        model: "accounts/fireworks/models/llama-v3p1-70b-instruct",
        detail: "not configured",
      },
      {
        provider: "ollama_cloud",
        active: false,
        embedding_active: false,
        configured: false,
        embedding_configured: false,
        base_url: null,
        model: "llama3.1",
        detail: "not configured",
      },
      {
        provider: "openrouter",
        active: false,
        embedding_active: false,
        configured: false,
        embedding_configured: false,
        base_url: null,
        model: "openai/gpt-4o-mini",
        detail: "not configured",
      },
      {
        provider: "litellm",
        active: false,
        embedding_active: false,
        configured: false,
        embedding_configured: false,
        base_url: null,
        model: null,
        detail: "not configured",
      },
    ],
    source: "mock",
    detail: "Set SAGAD_API_BASE_URL to load live model-provider status from Agent Studio.",
  };
}

export async function updateModelProviders(
  body: ModelProviderConfigUpsertRequest,
): Promise<{ active: string; config: ModelProviderConfigView }> {
  const response = await fetch("/api/admin/model-providers", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = (await response.json()) as {
    active?: string;
    config?: unknown;
    detail?: string;
  };
  if (!response.ok) {
    throw new Error(data.detail ?? `Save failed (HTTP ${response.status}).`);
  }
  return {
    active: String(data.active ?? "none"),
    config: readConfig(data.config) ?? mockConfig(),
  };
}
