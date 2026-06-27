"""DB-backed model-provider config (SuperAdmin console, writable).

One ``model_provider_config`` row per org holds the active chat/embedding provider + a JSONB
blob of non-secret per-provider fields. API keys live in ``model_provider_secret_versions``,
encrypted with ``pgp_sym_encrypt`` using the same key as integration secrets.

``configured_settings()`` (integration_config.py) merges this row over env -- DB wins, env is
the fallback when no row exists -- so the resolver (model_config.py) reads merged Settings and
does not need to change. Keys in ``NON_SECRET_FIELDS`` match ``Settings`` field names so the
merge is a straight dict update.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Protocol

from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from agent_studio.config import Settings, get_settings
from agent_studio.db import (
    TrustedContext,
    connect,
    database_configured,
    initialize_database_safe,
    resolve_trusted_context,
    set_app_context,
)
from agent_studio.schemas import ModelProviderConfigUpsertRequest
from agent_studio.store import StoreContext

# Keys match Settings field names -- the configured_settings merge is `updates[field] = value`.
NON_SECRET_FIELDS: tuple[str, ...] = (
    "openai_base_url",
    "openai_model",
    "openai_embedding_model",
    "fireworks_base_url",
    "fireworks_model",
    "fireworks_embedding_model",
    "ollama_cloud_base_url",
    "ollama_cloud_model",
    "ollama_cloud_embedding_model",
    "openrouter_model",
    "litellm_base_url",
    "litellm_model",
    "litellm_embedding_model",
    "embedding_dimensions",
    "classifier_model",
    "guardrail_model",
    "extractor_model",
    "supervisor_model",
)
SECRET_FIELDS: tuple[str, ...] = (
    "openai_api_key",
    "fireworks_api_key",
    "ollama_cloud_api_key",
    "openrouter_api_key",
    "litellm_master_key",
)


def _trusted_context(context: StoreContext | None) -> TrustedContext:
    scoped = context or StoreContext()
    return TrustedContext(
        organization_id=scoped.organization_id,
        user_id=scoped.user_id,
        role=scoped.role,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encryption_key(settings: Settings) -> str:
    return (
        settings.sagad_integration_encryption_key
        or settings.agent_studio_internal_secret
        or "sagad-local-integration-key"
    )


@dataclass
class ModelProviderConfigRecord:
    chat_provider: str = "none"
    embedding_provider: str = "auto"
    config: dict[str, object] = field(default_factory=dict)
    secrets: dict[str, str | None] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=_now)


class ModelProviderConfigStoreProtocol(Protocol):
    backend_name: str

    def get(self, context: StoreContext | None = None) -> ModelProviderConfigRecord | None:
        ...

    def upsert(
        self,
        request: ModelProviderConfigUpsertRequest,
        context: StoreContext | None = None,
    ) -> ModelProviderConfigRecord:
        ...

    def clear(self) -> None:
        ...


def _merge_config(existing: dict[str, object] | None, request: ModelProviderConfigUpsertRequest) -> dict[str, object]:
    merged: dict[str, object] = dict(existing or {})
    for field_name in NON_SECRET_FIELDS:
        value = getattr(request, field_name)
        if value is not None:
            merged[field_name] = value
    return merged


def _merge_secrets(
    existing: dict[str, str | None] | None,
    request: ModelProviderConfigUpsertRequest,
) -> dict[str, str | None]:
    merged: dict[str, str | None] = dict(existing or {})
    for secret_name in SECRET_FIELDS:
        value = getattr(request, secret_name)
        if value:  # only non-empty values are written; empty/None keeps the stored value
            merged[secret_name] = value
    return merged


class InMemoryModelProviderConfigStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._record: ModelProviderConfigRecord | None = None

    def get(self, context: StoreContext | None = None) -> ModelProviderConfigRecord | None:
        if self._record is None:
            return None
        return replace(self._record, config=dict(self._record.config), secrets=dict(self._record.secrets))

    def upsert(
        self,
        request: ModelProviderConfigUpsertRequest,
        context: StoreContext | None = None,
    ) -> ModelProviderConfigRecord:
        existing = self._record
        config = _merge_config(existing.config if existing else {}, request)
        secrets = _merge_secrets(existing.secrets if existing else {}, request)
        chat_provider = request.chat_provider or (existing.chat_provider if existing else "none")
        embedding_provider = request.embedding_provider or (existing.embedding_provider if existing else "auto")
        self._record = ModelProviderConfigRecord(
            chat_provider=chat_provider,
            embedding_provider=embedding_provider,
            config=config,
            secrets=secrets,
            updated_at=_now(),
        )
        return self.get(context=context)  # type: ignore[return-value]

    def clear(self) -> None:
        self._record = None


class PostgresModelProviderConfigStore:
    backend_name = "postgres"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        initialize_database_safe(settings)

    def get(self, context: StoreContext | None = None) -> ModelProviderConfigRecord | None:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            row = connection.execute(
                """
                SELECT
                  model_provider_config.chat_provider,
                  model_provider_config.embedding_provider,
                  model_provider_config.config,
                  model_provider_config.updated_at,
                  pgp_sym_decrypt(s_openai.encrypted_secret, %s) AS openai_api_key,
                  pgp_sym_decrypt(s_fireworks.encrypted_secret, %s) AS fireworks_api_key,
                  pgp_sym_decrypt(s_ollama.encrypted_secret, %s) AS ollama_cloud_api_key,
                  pgp_sym_decrypt(s_openrouter.encrypted_secret, %s) AS openrouter_api_key,
                  pgp_sym_decrypt(s_litellm.encrypted_secret, %s) AS litellm_master_key
                FROM model_provider_config
                LEFT JOIN model_provider_secret_versions s_openai
                  ON s_openai.organization_id = model_provider_config.organization_id
                 AND s_openai.secret_name = 'openai_api_key' AND s_openai.is_active
                LEFT JOIN model_provider_secret_versions s_fireworks
                  ON s_fireworks.organization_id = model_provider_config.organization_id
                 AND s_fireworks.secret_name = 'fireworks_api_key' AND s_fireworks.is_active
                LEFT JOIN model_provider_secret_versions s_ollama
                  ON s_ollama.organization_id = model_provider_config.organization_id
                 AND s_ollama.secret_name = 'ollama_cloud_api_key' AND s_ollama.is_active
                LEFT JOIN model_provider_secret_versions s_openrouter
                  ON s_openrouter.organization_id = model_provider_config.organization_id
                 AND s_openrouter.secret_name = 'openrouter_api_key' AND s_openrouter.is_active
                LEFT JOIN model_provider_secret_versions s_litellm
                  ON s_litellm.organization_id = model_provider_config.organization_id
                 AND s_litellm.secret_name = 'litellm_master_key' AND s_litellm.is_active
                WHERE model_provider_config.organization_id = %s
                LIMIT 1
                """,
                (
                    self._encryption_key(),
                    self._encryption_key(),
                    self._encryption_key(),
                    self._encryption_key(),
                    self._encryption_key(),
                    scoped.organization_id,
                ),
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    def upsert(
        self,
        request: ModelProviderConfigUpsertRequest,
        context: StoreContext | None = None,
    ) -> ModelProviderConfigRecord:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            org_id = scoped.organization_id

            existing = connection.execute(
                """
                SELECT chat_provider, embedding_provider, config
                FROM model_provider_config
                WHERE organization_id = %s
                """,
                (org_id,),
            ).fetchone()
            existing_config = dict(existing["config"]) if existing and existing["config"] else {}
            existing_chat = existing["chat_provider"] if existing else "none"
            existing_embedding = existing["embedding_provider"] if existing else "auto"

            merged_config = _merge_config(existing_config, request)
            chat_provider = request.chat_provider or existing_chat
            embedding_provider = request.embedding_provider or existing_embedding

            connection.execute(
                """
                INSERT INTO model_provider_config (
                  organization_id, chat_provider, embedding_provider, config, updated_by
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (organization_id) DO UPDATE SET
                  chat_provider = EXCLUDED.chat_provider,
                  embedding_provider = EXCLUDED.embedding_provider,
                  config = EXCLUDED.config,
                  updated_by = EXCLUDED.updated_by,
                  updated_at = now()
                """,
                (org_id, chat_provider, embedding_provider, Jsonb(merged_config), scoped.user_id),
            )
            for secret_name in SECRET_FIELDS:
                value = getattr(request, secret_name)
                if value:
                    self._upsert_secret(connection, org_id, secret_name, value)
            connection.commit()
        return self.get(context=context)  # type: ignore[return-value]

    def _upsert_secret(
        self,
        connection,
        organization_id: str | None,
        secret_name: str,
        secret_value: str,
    ) -> None:
        if not secret_value or organization_id is None:
            return
        connection.execute(
            """
            UPDATE model_provider_secret_versions
            SET is_active = false
            WHERE organization_id = %s AND secret_name = %s AND is_active
            """,
            (organization_id, secret_name),
        )
        connection.execute(
            """
            INSERT INTO model_provider_secret_versions (
              organization_id, secret_name, encrypted_secret
            )
            VALUES (%s, %s, pgp_sym_encrypt(%s, %s))
            """,
            (organization_id, secret_name, secret_value, self._encryption_key()),
        )

    def _encryption_key(self) -> str:
        return _encryption_key(self.settings)

    def clear(self) -> None:
        with connect(self.settings) as connection:
            connection.execute("TRUNCATE model_provider_secret_versions CASCADE")
            connection.execute("TRUNCATE model_provider_config CASCADE")
            connection.commit()


def _record_from_row(row: DictRow) -> ModelProviderConfigRecord:
    config = row["config"]
    return ModelProviderConfigRecord(
        chat_provider=row["chat_provider"],
        embedding_provider=row["embedding_provider"],
        config=dict(config) if isinstance(config, dict) else {},
        secrets={
            "openai_api_key": row["openai_api_key"],
            "fireworks_api_key": row["fireworks_api_key"],
            "ollama_cloud_api_key": row["ollama_cloud_api_key"],
            "openrouter_api_key": row["openrouter_api_key"],
            "litellm_master_key": row["litellm_master_key"],
        },
        updated_at=row["updated_at"],
    )


def build_model_provider_config_store(settings: Settings) -> ModelProviderConfigStoreProtocol:
    if database_configured(settings):
        return PostgresModelProviderConfigStore(settings)
    return InMemoryModelProviderConfigStore()


model_provider_config_store = build_model_provider_config_store(get_settings())


def _effective(record: ModelProviderConfigRecord | None, settings: Settings, field_name: str, default: object = None) -> object:
    if record and record.config.get(field_name) is not None:
        return record.config[field_name]
    return getattr(settings, field_name, default)


def model_provider_config_view(
    record: ModelProviderConfigRecord | None,
    settings: Settings,
) -> dict[str, object]:
    """Console-safe view: effective non-secret values + has_* secret booleans (never raw secrets)."""
    has = lambda secret_name: bool(record and record.secrets.get(secret_name))
    return {
        "chat_provider": record.chat_provider if record else settings.model_provider,
        "embedding_provider": record.embedding_provider if record else settings.embedding_provider,
        "openai": {
            "base_url": _effective(record, settings, "openai_base_url"),
            "model": _effective(record, settings, "openai_model"),
            "embedding_model": _effective(record, settings, "openai_embedding_model"),
            "has_api_key": has("openai_api_key"),
        },
        "fireworks": {
            "base_url": _effective(record, settings, "fireworks_base_url"),
            "model": _effective(record, settings, "fireworks_model"),
            "embedding_model": _effective(record, settings, "fireworks_embedding_model"),
            "has_api_key": has("fireworks_api_key"),
        },
        "ollama_cloud": {
            "base_url": _effective(record, settings, "ollama_cloud_base_url"),
            "model": _effective(record, settings, "ollama_cloud_model"),
            "embedding_model": _effective(record, settings, "ollama_cloud_embedding_model"),
            "has_api_key": has("ollama_cloud_api_key"),
        },
        "openrouter": {
            "model": _effective(record, settings, "openrouter_model"),
            "has_api_key": has("openrouter_api_key"),
        },
        "litellm": {
            "base_url": _effective(record, settings, "litellm_base_url"),
            "model": _effective(record, settings, "litellm_model"),
            "embedding_model": _effective(record, settings, "litellm_embedding_model"),
            "has_api_key": has("litellm_master_key"),
        },
        "embedding_dimensions": _effective(record, settings, "embedding_dimensions"),
        "classifier_model": _effective(record, settings, "classifier_model"),
        "guardrail_model": _effective(record, settings, "guardrail_model"),
        "extractor_model": _effective(record, settings, "extractor_model"),
        "supervisor_model": _effective(record, settings, "supervisor_model"),
    }
