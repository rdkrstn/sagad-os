from functools import lru_cache
import json
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pathlib import Path

# Load from repository root .env first, falling back to local .env
root_env = Path(__file__).resolve().parents[2] / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env)
else:
    load_dotenv()

# Map LANGSMITH_ env vars to LANGCHAIN_ equivalents for LangGraph tracing
if os.getenv("LANGSMITH_TRACING"):
    os.environ["LANGCHAIN_TRACING_V2"] = os.getenv("LANGSMITH_TRACING")
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
if os.getenv("LANGSMITH_PROJECT"):
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT")
if os.getenv("LANGSMITH_ENDPOINT"):
    os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")



def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _json_dict_env(name: str) -> dict[str, str] | None:
    """Parse a JSON object env var (e.g. ``{"sales_agent": "alice"}``). None when unset/blank."""
    value = os.getenv(name)
    if not value or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict):
        return {str(k): str(v) for k, v in parsed.items() if v is not None}
    return None


class Settings(BaseModel):
    database_url: str | None = None
    agent_studio_internal_secret: str | None = None
    chatwoot_base_url: str | None = None
    chatwoot_account_id: str | None = None
    chatwoot_inbox_identifier: str | None = None
    chatwoot_api_access_token: str | None = None
    chatwoot_webhook_token: str | None = None
    chatwoot_dry_run: bool = False
    # GoHighLevel (GHL) adapter — inbound webhook (HMAC) + outbound send.
    # outbound_mode: "webhook" (POST back to GHL messages API) or "mcp" (auto-send via MCP tool).
    ghl_webhook_secret: str | None = None
    ghl_api_key: str | None = None
    ghl_location_id: str | None = None
    ghl_base_url: str | None = None
    ghl_outbound_mode: str = "webhook"
    ghl_dry_run: bool = True
    # GHL inbound poller (tests the "direct inbound, not via webhook" theory using the
    # Private Integration Token's read scope). Off by default; enable with GHL_POLL_ENABLED.
    ghl_poll_enabled: bool = False
    ghl_poll_interval_seconds: int = 30
    ghl_poll_conversation_limit: int = 50
    ghl_poll_message_limit: int = 20
    ghl_poll_timeout_seconds: float = 20.0
    # GHL webhook signature scheme. "hmac" (default, X-GHL-Signature HMAC-SHA256, built) or
    # "ed25519" (native InboundMessage webhook, x-wh-signature, Marketplace/OAuth app -- groundwork
    # for the later native-webhook flip; activates only on this scheme).
    ghl_signature_scheme: str = "hmac"
    ghl_native_webhook_key: str | None = None
    # RevOps tiered auto-send: a narrow allowlist of low-risk intents that may be promoted to
    # compliance_status="pass" (and thus auto-sent) when risk=low + confidence>=threshold.
    # EMPTY by default => no promotion => existing needs_approval behavior is unchanged.
    revops_autosend_enabled: bool = True
    revops_autosend_intents: list[str] = Field(default_factory=list)
    revops_autosend_confidence: float = 0.88
    # RevOps ticket auto-assignment on creation: maps `selected_agent` (fallback `intent`) to a
    # default assignee id. EMPTY by default => no auto-assignment => existing behavior (assignee
    # stays None until a supervisor sets it via PATCH .../ticket). Set via
    # TICKET_DEFAULT_ASSIGNEES='{"sales_agent":"alice","support_agent":"bob"}'.
    ticket_default_assignees: dict[str, str] | None = None
    # Universal-webhook debouncing (opt-in). When enabled, /webhooks/{provider} returns 202
    # and coalesces a burst of messages into a single graph run after the debounce window.
    webhook_debounce_enabled: bool = False
    webhook_debounce_ms: int = 2500
    twenty_enabled: bool = False
    twenty_base_url: str | None = None
    twenty_api_key: str | None = None
    twenty_api_mode: str = "graphql"
    twenty_dry_run: bool = True
    twenty_allow_writes: bool = False
    twenty_timeout_seconds: float = 20
    langsmith_tracing: str | None = None
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None
    sagad_realtime_secret: str | None = None
    sagad_integration_encryption_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    litellm_enabled: bool = False
    litellm_base_url: str | None = None
    litellm_master_key: str | None = None
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    # --- Model provider config (env-driven; resolved by agent_studio.model_config) ---
    # Provider selection. Unknown values degrade to "none" (zero network, zero credentials).
    model_provider: str = "none"
    embedding_provider: str = "auto"
    # Fireworks AI (OpenAI-compatible at /inference/v1).
    fireworks_api_key: str | None = None
    fireworks_base_url: str = "https://api.fireworks.ai/inference/v1"
    fireworks_model: str = "accounts/fireworks/models/llama-v3p1-70b-instruct"
    fireworks_embedding_model: str = "nomic-embed-v1"
    # Ollama Cloud (OpenAI-compatible + key). Also covers self-hosted Ollama by setting
    # OLLAMA_CLOUD_BASE_URL=http://localhost:11434/v1 (and leaving the key unset).
    ollama_cloud_api_key: str | None = None
    ollama_cloud_base_url: str | None = None
    ollama_cloud_model: str = "llama3.1"
    ollama_cloud_embedding_model: str = "nomic-embed-text"
    # OpenRouter (one key, many providers; model is "<vendor>/<model>").
    openrouter_model: str = "openai/gpt-4o-mini"
    # LiteLLM gateway (model = alias configured in the gateway, e.g. sagad-openai-fast).
    litellm_model: str | None = None
    litellm_embedding_model: str | None = None
    # Per-node model overrides (fall back to the active provider's model when unset).
    classifier_model: str | None = None
    guardrail_model: str | None = None
    extractor_model: str | None = None
    supervisor_model: str | None = None
    # Optional explicit embedding vector size (overrides the model-dimension map).
    embedding_dimensions: int | None = None
    sagad_ocr_enabled: bool = False
    sagad_ocr_lang: str = "eng"
    sagad_ocr_max_pages: int = 10
    sagad_ocr_timeout_seconds: float = 30
    rerank_enabled: bool = False
    rerank_model: str = "cohere/rerank-english-v3.0"
    rerank_api_key: str | None = None
    sagad_docling_enabled: bool = False

    @property
    def chatwoot_send_enabled(self) -> bool:
        return self.chatwoot_configured and not self.chatwoot_dry_run

    @property
    def chatwoot_configured(self) -> bool:
        return all(
            [
                self.chatwoot_base_url,
                self.chatwoot_account_id,
                self.chatwoot_api_access_token,
            ],
        )

    @property
    def ghl_configured(self) -> bool:
        return all(
            [
                self.ghl_base_url,
                self.ghl_api_key,
                self.ghl_location_id,
            ],
        )

    @property
    def ghl_send_enabled(self) -> bool:
        return self.ghl_configured and not self.ghl_dry_run

    @property
    def twenty_configured(self) -> bool:
        return bool(self.twenty_base_url and self.twenty_api_key)

    @property
    def twenty_reads_enabled(self) -> bool:
        return self.twenty_enabled and self.twenty_configured

    @property
    def twenty_live_writes_enabled(self) -> bool:
        return (
            self.twenty_reads_enabled
            and self.twenty_allow_writes
            and not self.twenty_dry_run
        )

    @property
    def model_gateway_base_url(self) -> str | None:
        return self.openai_base_url or self.litellm_base_url

    @property
    def litellm_configured(self) -> bool:
        return bool(self.litellm_enabled and self.litellm_base_url)

    @property
    def litellm_health_base_url(self) -> str | None:
        if not self.litellm_base_url:
            return None
        return self.litellm_base_url.removesuffix("/v1").rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        agent_studio_internal_secret=os.getenv("AGENT_STUDIO_INTERNAL_SECRET"),
        chatwoot_base_url=os.getenv("CHATWOOT_BASE_URL"),
        chatwoot_account_id=os.getenv("CHATWOOT_ACCOUNT_ID"),
        chatwoot_inbox_identifier=os.getenv("CHATWOOT_INBOX_IDENTIFIER")
        or os.getenv("CHATWOOT_PUBLIC_INBOX_IDENTIFIER")
        or os.getenv("CHATWOOT_INBOX_ID"),
        chatwoot_api_access_token=os.getenv("CHATWOOT_API_ACCESS_TOKEN"),
        chatwoot_webhook_token=os.getenv("CHATWOOT_WEBHOOK_TOKEN"),
        chatwoot_dry_run=_bool_env("CHATWOOT_DRY_RUN", False),
        ghl_webhook_secret=os.getenv("GHL_WEBHOOK_SECRET"),
        ghl_api_key=os.getenv("GHL_API_KEY"),
        ghl_location_id=os.getenv("GHL_LOCATION_ID"),
        ghl_base_url=os.getenv("GHL_BASE_URL"),
        ghl_outbound_mode=os.getenv("GHL_OUTBOUND_MODE", "webhook"),
        ghl_dry_run=_bool_env("GHL_DRY_RUN", True),
        ghl_poll_enabled=_bool_env("GHL_POLL_ENABLED", False),
        ghl_poll_interval_seconds=_int_env("GHL_POLL_INTERVAL_SECONDS", 30),
        ghl_poll_conversation_limit=_int_env("GHL_POLL_CONVERSATION_LIMIT", 50),
        ghl_poll_message_limit=_int_env("GHL_POLL_MESSAGE_LIMIT", 20),
        ghl_poll_timeout_seconds=_float_env("GHL_POLL_TIMEOUT_SECONDS", 20.0),
        ghl_signature_scheme=os.getenv("GHL_SIGNATURE_SCHEME", "hmac"),
        ghl_native_webhook_key=os.getenv("GHL_NATIVE_WEBHOOK_KEY"),
        revops_autosend_enabled=_bool_env("REVOPS_AUTOSEND_ENABLED", True),
        revops_autosend_intents=[
            token.strip()
            for token in os.getenv("REVOPS_AUTOSEND_INTENTS", "").split(",")
            if token.strip()
        ],
        revops_autosend_confidence=_float_env("REVOPS_AUTOSEND_CONFIDENCE", 0.88),
        ticket_default_assignees=_json_dict_env("TICKET_DEFAULT_ASSIGNEES"),
        webhook_debounce_enabled=_bool_env("WEBHOOK_DEBOUNCE_ENABLED", False),
        webhook_debounce_ms=int(os.getenv("WEBHOOK_DEBOUNCE_MS", "2500")),
        twenty_enabled=_bool_env("TWENTY_ENABLED", False),
        twenty_base_url=os.getenv("TWENTY_BASE_URL"),
        twenty_api_key=os.getenv("TWENTY_API_KEY"),
        twenty_api_mode=os.getenv("TWENTY_API_MODE", "graphql"),
        twenty_dry_run=_bool_env("TWENTY_DRY_RUN", True),
        twenty_allow_writes=_bool_env("TWENTY_ALLOW_WRITES", False),
        twenty_timeout_seconds=float(os.getenv("TWENTY_TIMEOUT_SECONDS", "20")),
        langsmith_tracing=os.getenv("LANGSMITH_TRACING"),
        langsmith_api_key=os.getenv("LANGSMITH_API_KEY"),
        langsmith_project=os.getenv("LANGSMITH_PROJECT"),
        sagad_realtime_secret=os.getenv("SAGAD_REALTIME_SECRET"),
        sagad_integration_encryption_key=os.getenv("SAGAD_INTEGRATION_ENCRYPTION_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        openai_embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
        litellm_enabled=_bool_env("LITELLM_ENABLED", False),
        litellm_base_url=os.getenv("LITELLM_BASE_URL"),
        litellm_master_key=os.getenv("LITELLM_MASTER_KEY"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        model_provider=os.getenv("MODEL_PROVIDER", "none"),
        embedding_provider=os.getenv("EMBEDDING_PROVIDER", "auto"),
        fireworks_api_key=os.getenv("FIREWORKS_API_KEY"),
        fireworks_base_url=os.getenv(
            "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"
        ),
        fireworks_model=os.getenv(
            "FIREWORKS_MODEL", "accounts/fireworks/models/llama-v3p1-70b-instruct"
        ),
        fireworks_embedding_model=os.getenv("FIREWORKS_EMBEDDING_MODEL", "nomic-embed-v1"),
        ollama_cloud_api_key=os.getenv("OLLAMA_CLOUD_API_KEY"),
        ollama_cloud_base_url=os.getenv("OLLAMA_CLOUD_BASE_URL"),
        ollama_cloud_model=os.getenv("OLLAMA_CLOUD_MODEL", "llama3.1"),
        ollama_cloud_embedding_model=os.getenv("OLLAMA_CLOUD_EMBEDDING_MODEL", "nomic-embed-text"),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        litellm_model=os.getenv("LITELLM_MODEL"),
        litellm_embedding_model=os.getenv("LITELLM_EMBEDDING_MODEL"),
        classifier_model=os.getenv("CLASSIFIER_MODEL"),
        guardrail_model=os.getenv("GUARDRAIL_MODEL"),
        extractor_model=os.getenv("EXTRACTOR_MODEL"),
        supervisor_model=os.getenv("SUPERVISOR_MODEL"),
        embedding_dimensions=(
            int(os.getenv("EMBEDDING_DIMENSIONS"))
            if os.getenv("EMBEDDING_DIMENSIONS")
            else None
        ),
        sagad_ocr_enabled=_bool_env("SAGAD_OCR_ENABLED", False),
        sagad_ocr_lang=os.getenv("SAGAD_OCR_LANG", "eng"),
        sagad_ocr_max_pages=_int_env("SAGAD_OCR_MAX_PAGES", 10),
        sagad_ocr_timeout_seconds=_float_env("SAGAD_OCR_TIMEOUT_SECONDS", 30),
        rerank_enabled=_bool_env("RERANK_ENABLED", False),
        rerank_model=os.getenv("RERANK_MODEL", "cohere/rerank-english-v3.0"),
        rerank_api_key=os.getenv("RERANK_API_KEY"),
        sagad_docling_enabled=_bool_env("SAGAD_DOCLING_ENABLED", False),
    )
