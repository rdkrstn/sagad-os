from functools import lru_cache
import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    chatwoot_base_url: str | None = None
    chatwoot_account_id: str | None = None
    chatwoot_api_access_token: str | None = None
    chatwoot_webhook_token: str | None = None
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
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4"
    openai_embedding_model: str = "text-embedding-3-small"

    @property
    def chatwoot_send_enabled(self) -> bool:
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


@lru_cache
def get_settings() -> Settings:
    return Settings(
        chatwoot_base_url=os.getenv("CHATWOOT_BASE_URL"),
        chatwoot_account_id=os.getenv("CHATWOOT_ACCOUNT_ID"),
        chatwoot_api_access_token=os.getenv("CHATWOOT_API_ACCESS_TOKEN"),
        chatwoot_webhook_token=os.getenv("CHATWOOT_WEBHOOK_TOKEN"),
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
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4"),
        openai_embedding_model=os.getenv(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        ),
    )
