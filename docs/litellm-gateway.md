# LiteLLM Gateway

LiteLLM is an optional model gateway for Agent Studio. It gives Sagad OS one OpenAI-compatible endpoint while still letting operators test multiple providers such as OpenAI and DeepSeek.

## Why It Exists

Agent Studio should not hard-code every model provider directly into graph nodes. A gateway lets the backend switch models, test credits, and keep browser code away from model-provider credentials.

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
```

## VPS Preview

```bash
docker compose -f compose.vps.yaml --profile litellm up -d --build
```

Use the internal service URL:

```env
LITELLM_BASE_URL=http://sagad-litellm:4000/v1
OPENAI_BASE_URL=http://sagad-litellm:4000/v1
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
