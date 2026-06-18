from functools import lru_cache
import os

from dotenv import load_dotenv
from pydantic import BaseModel
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


class Settings(BaseModel):
    database_url: str | None = None
    agent_studio_internal_secret: str | None = None
    chatwoot_base_url: str | None = None
    chatwoot_account_id: str | None = None
    chatwoot_inbox_identifier: str | None = None
    chatwoot_api_access_token: str | None = None
    chatwoot_webhook_token: str | None = None
    chatwoot_dry_run: bool = False
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
    openai_model: str = "gpt-5.4"
    openai_embedding_model: str = "text-embedding-3-small"
    litellm_enabled: bool = False
    litellm_base_url: str | None = None
    litellm_master_key: str | None = None
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    sagad_ocr_enabled: bool = False
    sagad_ocr_lang: str = "eng"
    sagad_ocr_max_pages: int = 10
    sagad_ocr_timeout_seconds: float = 30
    rerank_enabled: bool = False
    rerank_model: str = "cohere/rerank-english-v3.0"
    rerank_api_key: str | None = None
    sagad_docling_enabled: bool = True

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
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        openai_embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
        litellm_enabled=_bool_env("LITELLM_ENABLED", False),
        litellm_base_url=os.getenv("LITELLM_BASE_URL"),
        litellm_master_key=os.getenv("LITELLM_MASTER_KEY"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        sagad_ocr_enabled=_bool_env("SAGAD_OCR_ENABLED", False),
        sagad_ocr_lang=os.getenv("SAGAD_OCR_LANG", "eng"),
        sagad_ocr_max_pages=_int_env("SAGAD_OCR_MAX_PAGES", 10),
        sagad_ocr_timeout_seconds=_float_env("SAGAD_OCR_TIMEOUT_SECONDS", 30),
        rerank_enabled=_bool_env("RERANK_ENABLED", False),
        rerank_model=os.getenv("RERANK_MODEL", "cohere/rerank-english-v3.0"),
        rerank_api_key=os.getenv("RERANK_API_KEY"),
        sagad_docling_enabled=_bool_env("SAGAD_DOCLING_ENABLED", True),
    )
