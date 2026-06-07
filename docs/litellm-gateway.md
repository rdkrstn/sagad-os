# LiteLLM Gateway

LiteLLM is an optional model gateway for Agent Studio. It gives Sagad OS one OpenAI-compatible endpoint while still letting operators test multiple providers such as OpenAI and DeepSeek.

## Why It Exists

Agent Studio should not hard-code every model provider directly into graph nodes. A gateway lets the backend switch models, test credits, and keep browser code away from model-provider credentials.

The current Sagad conversation graph is still deterministic. LiteLLM readiness does not enable full LLM-powered Sales or Support drafting yet; that comes after adapter correctness is stable.

## Local Preview

```powershell
docker compose -f compose.preview.yaml --profile litellm up -d --build
```

Agent Studio can point at the gateway with:

```env
LITELLM_ENABLED=true
LITELLM_BASE_URL=http://litellm:4000/v1
OPENAI_BASE_URL=http://litellm:4000/v1
LITELLM_MASTER_KEY=replace-with-strong-litellm-key
OPENAI_API_KEY=replace-with-openai-key
DEEPSEEK_API_KEY=replace-with-deepseek-key
OPENAI_MODEL=sagad-openai-fast
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
