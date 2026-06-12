# LiteLLM Gateway

LiteLLM is an optional model gateway for Agent Studio. It gives Sagad OS one OpenAI-compatible endpoint while still letting operators test multiple providers such as OpenAI, DeepSeek, and OpenRouter.

## Why It Exists

Agent Studio uses LangChain's `ChatOpenAI` wrapper to perform model calling. Instead of hard-coding every provider, the wrapper automatically routes through one of three prioritized targets depending on the environment variables:

1. **LiteLLM Proxy** (if `LITELLM_ENABLED=true` and `LITELLM_BASE_URL` is set)
2. **OpenRouter** (if `OPENROUTER_API_KEY` is set and `LITELLM_MODEL` starts with `openrouter/`)
3. **Direct OpenAI** (fallback using `OPENAI_API_KEY` and optionally `OPENAI_BASE_URL`)

This allows the backend to easily switch models, test credits, and support streaming while keeping provider credentials securely stored in the environment.

## Local Preview

```powershell
docker compose -f compose.preview.yaml --profile litellm up -d --build
```

Agent Studio can point at the gateway, OpenRouter, or OpenAI with:

```env
# LiteLLM Proxy Option
LITELLM_ENABLED=true
LITELLM_BASE_URL=http://litellm:4000/v1
LITELLM_MASTER_KEY=replace-with-strong-litellm-key

# OpenRouter Option
OPENROUTER_API_KEY=replace-with-openrouter-key
LITELLM_MODEL=openrouter/google/gemini-2.5-flash

# OpenAI Direct Option (Fallback)
OPENAI_API_KEY=replace-with-openai-key
LITELLM_MODEL=gpt-4o-mini
```

## VPS Preview

```bash
docker compose -f compose.vps.yaml --profile litellm up -d --build
```

Use the internal service URL:

```env
LITELLM_ENABLED=true
LITELLM_BASE_URL=http://sagad-litellm:4000/v1
OPENAI_BASE_URL=http://sagad-litellm:4000/v1
OPENAI_MODEL=sagad-openai-fast
```

Do not expose LiteLLM publicly unless authentication, rate limits, and network policy are in place.

## Health

Agent Studio exposes a redacted gateway status:

```text
GET /integrations/litellm/health
```

Docker checks LiteLLM liveness at:

```text
GET /health/liveliness
```

## Config

The checked-in config is an example only:

```text
infra/litellm/config.example.yaml
```

It reads provider keys from environment variables. Do not commit real provider keys.

The example aliases are:

- `sagad-openai-fast`
- `sagad-openai-reasoning`
- `sagad-deepseek-chat`
- `sagad-openai-embedding`

`OPENAI_MODEL=gpt-5.4` will not work through LiteLLM unless that exact alias exists in the LiteLLM config. If embeddings should route through LiteLLM, set `OPENAI_BASE_URL` to the LiteLLM `/v1` endpoint and use an embedding alias such as `sagad-openai-embedding`.
