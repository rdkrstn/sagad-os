# Model Providers

Sagad OS Agent Studio talks to LLM + embedding providers through **one provider model**. You pick a chat provider with `MODEL_PROVIDER` and an embedding provider with `EMBEDDING_PROVIDER`. Both chat and embeddings ask the same resolver (`agent_studio/model_config.py`), so there is a single source of truth instead of scattered env vars.

## The default is `none` (zero credentials, zero network)

```
MODEL_PROVIDER=none
EMBEDDING_PROVIDER=auto
```

With `none`:
- **Chat** uses `DryRunChatModel` — the graph runs end-to-end deterministically with canned responses. No API key, no network.
- **Embeddings** use the local hash-based `deterministic_embedding`. No network call is attempted.

This is the safe open-source default. The console and pipelines never 500 and never hang on a dead endpoint. Set a real provider only when you have credentials and a reachable endpoint.

## LiteLLM is the chat engine (you don't need to "use" it directly)

For chat, Agent Studio always calls `litellm.completion` under the hood. LiteLLM is a router: it knows how to reach OpenAI, Fireworks, OpenRouter, Ollama, and OpenAI-compatible endpoints. You do **not** configure LiteLLM the library — you pick `MODEL_PROVIDER` and the resolver maps it to the right LiteLLM model prefix + endpoint + key:

| `MODEL_PROVIDER` | LiteLLM model sent | Endpoint | Key |
| --- | --- | --- | --- |
| `openai` | `openai/<model>` | `OPENAI_BASE_URL` (or OpenAI default) | `OPENAI_API_KEY` |
| `fireworks` | `fireworks_ai/<model>` | `FIREWORKS_BASE_URL` | `FIREWORKS_API_KEY` |
| `ollama_cloud` | `openai/<model>` | `OLLAMA_CLOUD_BASE_URL` | `OLLAMA_CLOUD_API_KEY` (optional for local) |
| `openrouter` | `openrouter/<model>` | (LiteLLM built-in) | `OPENROUTER_API_KEY` |
| `litellm` | `<alias>` | `LITELLM_BASE_URL` | `LITELLM_MASTER_KEY` |

The `litellm` provider is for the **optional LiteLLM gateway** (a separate container that fronts many models behind one URL). Use it only if you run that gateway. Otherwise pick the provider you have credentials for directly.

## Embeddings are a separate dial

OpenRouter has no embeddings endpoint, and you may want chat from one provider and embeddings from another (e.g. chat via OpenRouter, embeddings via Fireworks). So embeddings have their own selector:

```
EMBEDDING_PROVIDER=auto   # follow MODEL_PROVIDER (openrouter/none -> deterministic)
EMBEDDING_PROVIDER=none   # always deterministic, never any network call
EMBEDDING_PROVIDER=fireworks   # force Fireworks embeddings regardless of chat provider
```

`auto` follows `MODEL_PROVIDER`, except `openrouter` and `none` fall back to `none` (deterministic). All embedding providers (OpenAI, Fireworks, Ollama Cloud, LiteLLM) speak the OpenAI-compatible `/embeddings` shape, so the same code path serves them.

If the embedding endpoint is unreachable, `EmbeddingService` logs `embed_text_failed provider=... base_url=...` and falls back to deterministic — the pipeline keeps running. A *real* provider with a *dead* URL is the only way to get that warning now; the default `none` makes no network call at all.

## Provider setup (copy-paste)

### Fireworks AI
```
MODEL_PROVIDER=fireworks
FIREWORKS_API_KEY=fw-...
FIREWORKS_MODEL=accounts/fireworks/models/llama-v3p1-70b-instruct
FIREWORKS_EMBEDDING_MODEL=nomic-embed-v1
EMBEDDING_PROVIDER=auto
```

### Ollama Cloud (or self-hosted Ollama)
```
MODEL_PROVIDER=ollama_cloud
OLLAMA_CLOUD_BASE_URL=https://<your-ollama-cloud-endpoint>/v1
OLLAMA_CLOUD_API_KEY=...            # leave empty for local Ollama
OLLAMA_CLOUD_MODEL=llama3.1
OLLAMA_CLOUD_EMBEDDING_MODEL=nomic-embed-text
```
For self-hosted Ollama: `OLLAMA_CLOUD_BASE_URL=http://localhost:11434/v1` and leave the key empty.

### OpenRouter (chat only)
```
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini
EMBEDDING_PROVIDER=fireworks   # OpenRouter has no embeddings -- pick one
```

### OpenAI
```
MODEL_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### LiteLLM gateway (optional)
```
MODEL_PROVIDER=litellm
LITELLM_BASE_URL=http://sagad-litellm:4000/v1
LITELLM_MASTER_KEY=...
LITELLM_MODEL=sagad-openai-fast            # alias from infra/litellm/config.example.yaml
LITELLM_EMBEDDING_MODEL=sagad-openai-embedding
```

## Per-node model overrides

You can route specific graph nodes to a different model (same provider) without changing the default:

```
CLASSIFIER_MODEL=accounts/fireworks/models/llama-v3p1-8b-instruct
SUPERVISOR_MODEL=accounts/fireworks/models/deepseek-v4
```

These are bare model names for the active provider; the provider prefix is applied automatically.

## Force a no-LLM run

```
LLM_MODE=dry_run
```

Takes precedence over `MODEL_PROVIDER`. The whole graph runs with `DryRunChatModel` — used by the compose e2e roundtrip in CI/local.

## SuperAdmin console

`/superadmin` -> **Model Providers** shows the active provider, per-provider configured status, and a **Test active provider** button that does a 1-token chat completion + a 1-text embedding against the resolved config and reports ok/fail with a concrete reason. It is read-only (config is env-driven); change providers by editing env vars and restarting Agent Studio.

## Troubleshooting

- `embed_text_failed ... ConnectError -> falling back to deterministic embedding` — an embedding provider is selected but its endpoint is unreachable. Either set `EMBEDDING_PROVIDER=none` (no network) or fix the `*_BASE_URL`.
- `litellm error: Failed to connect to streaming endpoint` — the active chat provider's endpoint is unreachable. Check the provider's base URL / API key, or set `MODEL_PROVIDER=none` to fall back to DryRun.
- Both warnings disappear at the default `MODEL_PROVIDER=none` / `EMBEDDING_PROVIDER=auto` because no network call is attempted.
