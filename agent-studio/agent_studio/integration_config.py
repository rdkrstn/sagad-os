from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from psycopg.rows import DictRow

from agent_studio.config import Settings, get_settings
from agent_studio.db import (
    TrustedContext,
    connect,
    database_configured,
    initialize_database,
    initialize_database_safe,
    resolve_trusted_context,
    set_app_context,
)
from agent_studio.schemas import (
    IntegrationConnection,
    IntegrationConnectionUpsertRequest,
    IntegrationKind,
    IntegrationProvider,
)
from agent_studio.model_provider_config import (
    NON_SECRET_FIELDS as MP_NON_SECRET_FIELDS,
    SECRET_FIELDS as MP_SECRET_FIELDS,
    model_provider_config_store,
)
from agent_studio.store import StoreContext


ADMIN_ROLES = {"owner", "admin"}
#: Providers that participate in the integration-config store / display surface. The DB
#: CHECK (migrations 0001 + 0007) already allows these three; the store loops over this tuple
#: so a new provider is added in one place.
_CONFIGURED_PROVIDERS: tuple[IntegrationProvider, ...] = ("chatwoot", "twenty", "ghl")
# TODO: Consider adding caching to the PostgresIntegrationConfigStore for efficiency, with appropriate invalidation on updates.
@dataclass
class IntegrationConnectionRecord:
    provider: IntegrationProvider
    base_url: str | None = None
    account_id: str | None = None
    inbox_id: str | None = None
    api_mode: str | None = None
    enabled: bool = True
    dry_run: bool = True
    allow_writes: bool = False
    api_access_token: str | None = None
    webhook_token: str | None = None
    api_key: str | None = None
    # GHL-specific (nullable; only set on 'ghl' rows).
    location_id: str | None = None
    outbound_mode: str | None = None
    signature_scheme: str | None = None
    poll_enabled: bool | None = None
    poll_interval_seconds: int | None = None
    poll_conversation_limit: int | None = None
    poll_message_limit: int | None = None
    webhook_secret: str | None = None
    native_webhook_key: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class IntegrationConfigStoreProtocol(Protocol):
    backend_name: str

    def list(self, context: StoreContext | None = None) -> list[IntegrationConnection]:
        ...

    def get(
        self,
        provider: IntegrationProvider,
        context: StoreContext | None = None,
    ) -> IntegrationConnectionRecord | None:
        ...

    def upsert(
        self,
        provider: IntegrationProvider,
        request: IntegrationConnectionUpsertRequest,
        context: StoreContext | None = None,
    ) -> IntegrationConnection:
        ...

    def disable(
        self,
        provider: IntegrationProvider,
        context: StoreContext | None = None,
    ) -> IntegrationConnection:
        ...

    def clear(self) -> None:
        ...


def _trusted_context(context: StoreContext | None) -> TrustedContext:
    scoped = context or StoreContext()
    return TrustedContext(
        organization_id=scoped.organization_id,
        user_id=scoped.user_id,
        role=scoped.role,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _provider_name(provider: IntegrationProvider) -> str:
    if provider == "chatwoot":
        return "Chatwoot"
    if provider == "ghl":
        return "GoHighLevel"
    return "Twenty CRM"


def _provider_kind(provider: IntegrationProvider) -> IntegrationKind:
    if provider in ("chatwoot", "ghl"):
        return "channel"
    return "crm"


def _provider_required_fields(provider: IntegrationProvider) -> list[str]:
    if provider == "chatwoot":
        return ["base_url", "account_id", "api_access_token"]
    if provider == "ghl":
        return ["base_url", "api_key", "location_id"]
    return ["base_url", "api_key"]


def _connection_from_record(record: IntegrationConnectionRecord | None, provider: IntegrationProvider) -> IntegrationConnection:
    if record is None:
        return IntegrationConnection(
            provider=provider,
            name=_provider_name(provider),
            kind=_provider_kind(provider),
            status="unconfigured",
            configured=False,
            enabled=False,
            base_url=None,
            dry_run=True,
            writes_enabled=False,
            missing=_provider_required_fields(provider),
            detail=f"{_provider_name(provider)} is not configured yet.",
        )

    missing: list[str] = []
    if not record.base_url:
        missing.append("base_url")
    if provider == "chatwoot":
        if not record.account_id:
            missing.append("account_id")
        if not record.api_access_token:
            missing.append("api_access_token")
    elif provider == "ghl":
        if not record.api_key:
            missing.append("api_key")
        if not record.location_id:
            missing.append("location_id")
    else:
        if not record.api_key:
            missing.append("api_key")
    configured = not missing
    status = "ready" if configured and record.enabled and not record.dry_run else "dry_run"
    if not record.enabled:
        status = "disabled"
    if not configured:
        status = "unconfigured"

    if provider == "ghl":
        # GHL has no separate allow_writes flag: dry_run is the live-send gate.
        writes_enabled = bool(record.enabled) and bool(configured) and not bool(record.dry_run)
    else:
        writes_enabled = (
            bool(record.enabled)
            and bool(configured)
            and bool(record.allow_writes)
            and not bool(record.dry_run)
        )
    detail = _connection_detail(provider, status, missing, writes_enabled)
    connection = IntegrationConnection(
        provider=provider,
        name=_provider_name(provider),
        kind=_provider_kind(provider),
        status=status,  # type: ignore[arg-type]
        configured=configured,
        enabled=record.enabled,
        base_url=record.base_url,
        account_id=record.account_id,
        inbox_id=record.inbox_id,
        api_mode=record.api_mode or ("graphql" if provider == "twenty" else None),
        dry_run=record.dry_run,
        writes_enabled=writes_enabled,
        has_api_access_token=bool(record.api_access_token),
        has_webhook_token=bool(record.webhook_token),
        has_api_key=bool(record.api_key),
        missing=missing,
        detail=detail,
        updated_at=record.updated_at,
    )
    if provider == "ghl":
        connection.location_id = record.location_id
        connection.outbound_mode = record.outbound_mode
        connection.signature_scheme = record.signature_scheme
        connection.poll_enabled = record.poll_enabled
        connection.poll_interval_seconds = record.poll_interval_seconds
        connection.has_webhook_secret = bool(record.webhook_secret)
        connection.has_native_webhook_key = bool(record.native_webhook_key)
    return connection


def _runtime_connection_from_settings(
    settings: Settings,
    provider: IntegrationProvider,
) -> IntegrationConnection:
    if provider == "chatwoot":
        has_runtime_values = any(
            [
                settings.chatwoot_base_url,
                settings.chatwoot_account_id,
                settings.chatwoot_api_access_token,
                settings.chatwoot_webhook_token,
            ],
        )
        record = (
            IntegrationConnectionRecord(
                provider="chatwoot",
                base_url=settings.chatwoot_base_url,
                account_id=settings.chatwoot_account_id,
                api_access_token="env-set" if settings.chatwoot_api_access_token else None,
                webhook_token="env-set" if settings.chatwoot_webhook_token else None,
                enabled=has_runtime_values,
                dry_run=settings.chatwoot_dry_run,
                allow_writes=settings.chatwoot_send_enabled,
            )
            if has_runtime_values
            else None
        )
    elif provider == "ghl":
        has_runtime_values = any(
            [
                settings.ghl_base_url,
                settings.ghl_api_key,
                settings.ghl_location_id,
            ],
        )
        record = (
            IntegrationConnectionRecord(
                provider="ghl",
                base_url=settings.ghl_base_url,
                api_key="env-set" if settings.ghl_api_key else None,
                location_id=settings.ghl_location_id,
                outbound_mode=settings.ghl_outbound_mode,
                signature_scheme=settings.ghl_signature_scheme,
                poll_enabled=settings.ghl_poll_enabled,
                poll_interval_seconds=settings.ghl_poll_interval_seconds,
                poll_conversation_limit=settings.ghl_poll_conversation_limit,
                poll_message_limit=settings.ghl_poll_message_limit,
                webhook_secret="env-set" if settings.ghl_webhook_secret else None,
                native_webhook_key="env-set" if settings.ghl_native_webhook_key else None,
                enabled=has_runtime_values,
                dry_run=settings.ghl_dry_run,
            )
            if has_runtime_values
            else None
        )
    else:
        has_runtime_values = any(
            [
                settings.twenty_base_url,
                settings.twenty_api_key,
                settings.twenty_enabled,
            ],
        )
        record = (
            IntegrationConnectionRecord(
                provider="twenty",
                base_url=settings.twenty_base_url,
                api_mode=settings.twenty_api_mode,
                api_key="env-set" if settings.twenty_api_key else None,
                enabled=settings.twenty_enabled,
                dry_run=settings.twenty_dry_run,
                allow_writes=settings.twenty_allow_writes,
            )
            if has_runtime_values
            else None
        )

    connection = _connection_from_record(record, provider)
    if connection.configured:
        connection.detail = f"{connection.name} is configured from Agent Studio environment variables."
    return connection


def integration_connections_for_display(
    settings: Settings,
    context: StoreContext | None = None,
) -> list[IntegrationConnection]:
    connections: list[IntegrationConnection] = []
    for provider in _CONFIGURED_PROVIDERS:
        saved = _connection_from_record(
            integration_config_store.get(provider, context=context),
            provider,
        )
        runtime = _runtime_connection_from_settings(settings, provider)
        connections.append(saved if saved.configured else runtime)
    return connections


def _connection_detail(
    provider: IntegrationProvider,
    status: str,
    missing: list[str],
    writes_enabled: bool,
) -> str:
    name = _provider_name(provider)
    if missing:
        return f"{name} is missing: {', '.join(missing)}."
    if status == "disabled":
        return f"{name} is configured but disabled."
    if status == "dry_run":
        return f"{name} is configured in dry-run mode."
    if writes_enabled:
        return f"{name} is configured and live writes are enabled."
    return f"{name} is configured for server-side Agent Studio access."


class InMemoryIntegrationConfigStore:
    backend_name = "memory"

    def __init__(self) -> None:
        self._records: dict[IntegrationProvider, IntegrationConnectionRecord] = {}

    def list(self, context: StoreContext | None = None) -> list[IntegrationConnection]:
        return [_connection_from_record(self._records.get(provider), provider) for provider in ("chatwoot", "twenty")]

    def get(
        self,
        provider: IntegrationProvider,
        context: StoreContext | None = None,
    ) -> IntegrationConnectionRecord | None:
        return self._records.get(provider)

    def upsert(
        self,
        provider: IntegrationProvider,
        request: IntegrationConnectionUpsertRequest,
        context: StoreContext | None = None,
    ) -> IntegrationConnection:
        existing = self._records.get(provider)
        record = IntegrationConnectionRecord(
            provider=provider,
            base_url=request.base_url if request.base_url is not None else existing.base_url if existing else None,
            account_id=request.account_id if request.account_id is not None else existing.account_id if existing else None,
            inbox_id=request.inbox_id if request.inbox_id is not None else existing.inbox_id if existing else None,
            api_mode=request.api_mode if request.api_mode is not None else existing.api_mode if existing else "graphql",
            enabled=request.enabled,
            dry_run=request.dry_run,
            allow_writes=request.allow_writes,
            api_access_token=request.api_access_token if request.api_access_token else existing.api_access_token if existing else None,
            webhook_token=request.webhook_token if request.webhook_token else existing.webhook_token if existing else None,
            api_key=request.api_key if request.api_key else existing.api_key if existing else None,
            location_id=request.location_id if request.location_id is not None else existing.location_id if existing else None,
            outbound_mode=request.outbound_mode if request.outbound_mode is not None else existing.outbound_mode if existing else None,
            signature_scheme=request.signature_scheme if request.signature_scheme is not None else existing.signature_scheme if existing else None,
            poll_enabled=request.poll_enabled if request.poll_enabled is not None else existing.poll_enabled if existing else None,
            poll_interval_seconds=request.poll_interval_seconds if request.poll_interval_seconds is not None else existing.poll_interval_seconds if existing else None,
            poll_conversation_limit=request.poll_conversation_limit if request.poll_conversation_limit is not None else existing.poll_conversation_limit if existing else None,
            poll_message_limit=request.poll_message_limit if request.poll_message_limit is not None else existing.poll_message_limit if existing else None,
            webhook_secret=request.webhook_secret if request.webhook_secret else existing.webhook_secret if existing else None,
            native_webhook_key=request.native_webhook_key if request.native_webhook_key else existing.native_webhook_key if existing else None,
            updated_at=_now(),
        )
        self._records[provider] = record
        return _connection_from_record(record, provider)

    def disable(
        self,
        provider: IntegrationProvider,
        context: StoreContext | None = None,
    ) -> IntegrationConnection:
        existing = self._records.get(provider) or IntegrationConnectionRecord(provider=provider)
        existing.enabled = False
        existing.updated_at = _now()
        self._records[provider] = existing
        return _connection_from_record(existing, provider)

    def clear(self) -> None:
        self._records.clear()


class PostgresIntegrationConfigStore:
    backend_name = "postgres"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Non-fatal: must not kill the process at import time when the DB is briefly unavailable.
        initialize_database_safe(settings)

    def list(self, context: StoreContext | None = None) -> list[IntegrationConnection]:
        return [_connection_from_record(self.get(provider, context=context), provider) for provider in _CONFIGURED_PROVIDERS]

    def get(
        self,
        provider: IntegrationProvider,
        context: StoreContext | None = None,
    ) -> IntegrationConnectionRecord | None:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            row = connection.execute(
                """
                SELECT
                  integration_connections.provider,
                  integration_connections.base_url,
                  integration_connections.account_id,
                  integration_connections.inbox_id,
                  integration_connections.api_mode,
                  integration_connections.enabled,
                  integration_connections.dry_run,
                  integration_connections.allow_writes,
                  integration_connections.location_id,
                  integration_connections.outbound_mode,
                  integration_connections.signature_scheme,
                  integration_connections.poll_enabled,
                  integration_connections.poll_interval_seconds,
                  integration_connections.poll_conversation_limit,
                  integration_connections.poll_message_limit,
                  integration_connections.updated_at,
                  pgp_sym_decrypt(api_access.encrypted_secret, %s) AS api_access_token,
                  pgp_sym_decrypt(webhook.encrypted_secret, %s) AS webhook_token,
                  pgp_sym_decrypt(api_key.encrypted_secret, %s) AS api_key,
                  pgp_sym_decrypt(ghl_webhook.encrypted_secret, %s) AS ghl_webhook_secret,
                  pgp_sym_decrypt(ghl_native.encrypted_secret, %s) AS ghl_native_webhook_key
                FROM integration_connections
                LEFT JOIN integration_secret_versions api_access
                  ON api_access.connection_id = integration_connections.id
                 AND api_access.secret_name = 'api_access_token'
                 AND api_access.is_active
                LEFT JOIN integration_secret_versions webhook
                  ON webhook.connection_id = integration_connections.id
                 AND webhook.secret_name = 'webhook_token'
                 AND webhook.is_active
                LEFT JOIN integration_secret_versions api_key
                  ON api_key.connection_id = integration_connections.id
                 AND api_key.secret_name = 'api_key'
                 AND api_key.is_active
                LEFT JOIN integration_secret_versions ghl_webhook
                  ON ghl_webhook.connection_id = integration_connections.id
                 AND ghl_webhook.secret_name = 'ghl_webhook_secret'
                 AND ghl_webhook.is_active
                LEFT JOIN integration_secret_versions ghl_native
                  ON ghl_native.connection_id = integration_connections.id
                 AND ghl_native.secret_name = 'ghl_native_webhook_key'
                 AND ghl_native.is_active
                WHERE integration_connections.organization_id = %s
                  AND integration_connections.provider = %s
                LIMIT 1
                """,
                (
                    self._encryption_key(),
                    self._encryption_key(),
                    self._encryption_key(),
                    self._encryption_key(),
                    self._encryption_key(),
                    scoped.organization_id,
                    provider,
                ),
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    def upsert(
        self,
        provider: IntegrationProvider,
        request: IntegrationConnectionUpsertRequest,
        context: StoreContext | None = None,
    ) -> IntegrationConnection:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            row = connection.execute(
                """
                INSERT INTO integration_connections (
                  organization_id,
                  provider,
                  base_url,
                  account_id,
                  inbox_id,
                  api_mode,
                  enabled,
                  dry_run,
                  allow_writes,
                  location_id,
                  outbound_mode,
                  signature_scheme,
                  poll_enabled,
                  poll_interval_seconds,
                  poll_conversation_limit,
                  poll_message_limit,
                  updated_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, provider) DO UPDATE SET
                  base_url = COALESCE(EXCLUDED.base_url, integration_connections.base_url),
                  account_id = COALESCE(EXCLUDED.account_id, integration_connections.account_id),
                  inbox_id = COALESCE(EXCLUDED.inbox_id, integration_connections.inbox_id),
                  api_mode = COALESCE(EXCLUDED.api_mode, integration_connections.api_mode),
                  enabled = EXCLUDED.enabled,
                  dry_run = EXCLUDED.dry_run,
                  allow_writes = EXCLUDED.allow_writes,
                  location_id = COALESCE(EXCLUDED.location_id, integration_connections.location_id),
                  outbound_mode = COALESCE(EXCLUDED.outbound_mode, integration_connections.outbound_mode),
                  signature_scheme = COALESCE(EXCLUDED.signature_scheme, integration_connections.signature_scheme),
                  poll_enabled = EXCLUDED.poll_enabled,
                  poll_interval_seconds = COALESCE(EXCLUDED.poll_interval_seconds, integration_connections.poll_interval_seconds),
                  poll_conversation_limit = COALESCE(EXCLUDED.poll_conversation_limit, integration_connections.poll_conversation_limit),
                  poll_message_limit = COALESCE(EXCLUDED.poll_message_limit, integration_connections.poll_message_limit),
                  updated_by = EXCLUDED.updated_by,
                  updated_at = now()
                RETURNING id
                """,
                (
                    scoped.organization_id,
                    provider,
                    request.base_url,
                    request.account_id,
                    request.inbox_id,
                    request.api_mode,
                    request.enabled,
                    request.dry_run,
                    request.allow_writes,
                    request.location_id,
                    request.outbound_mode,
                    request.signature_scheme,
                    request.poll_enabled,
                    request.poll_interval_seconds,
                    request.poll_conversation_limit,
                    request.poll_message_limit,
                    scoped.user_id,
                ),
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to save integration connection.")
            connection_id = str(row["id"])
            self._upsert_secret(
                connection,
                scoped.organization_id,
                connection_id,
                "api_access_token",
                request.api_access_token,
            )
            self._upsert_secret(
                connection,
                scoped.organization_id,
                connection_id,
                "webhook_token",
                request.webhook_token,
            )
            self._upsert_secret(
                connection,
                scoped.organization_id,
                connection_id,
                "api_key",
                request.api_key,
            )
            self._upsert_secret(
                connection,
                scoped.organization_id,
                connection_id,
                "ghl_webhook_secret",
                request.webhook_secret,
            )
            self._upsert_secret(
                connection,
                scoped.organization_id,
                connection_id,
                "ghl_native_webhook_key",
                request.native_webhook_key,
            )
            connection.commit()
        return _connection_from_record(self.get(provider, context=context), provider)

    def disable(
        self,
        provider: IntegrationProvider,
        context: StoreContext | None = None,
    ) -> IntegrationConnection:
        with connect(self.settings) as connection:
            scoped = resolve_trusted_context(connection, _trusted_context(context))
            set_app_context(connection, scoped)
            connection.execute(
                """
                UPDATE integration_connections
                SET enabled = false,
                    updated_by = %s,
                    updated_at = now()
                WHERE organization_id = %s
                  AND provider = %s
                """,
                (scoped.user_id, scoped.organization_id, provider),
            )
            connection.commit()
        return _connection_from_record(self.get(provider, context=context), provider)

    def clear(self) -> None:
        with connect(self.settings) as connection:
            connection.execute("TRUNCATE integration_secret_versions CASCADE")
            connection.execute("TRUNCATE integration_connections CASCADE")
            connection.commit()

    def _upsert_secret(
        self,
        connection,
        organization_id: str | None,
        connection_id: str,
        secret_name: str,
        secret_value: str | None,
    ) -> None:
        if not secret_value or organization_id is None:
            return
        connection.execute(
            """
            UPDATE integration_secret_versions
            SET is_active = false
            WHERE connection_id = %s
              AND secret_name = %s
              AND is_active
            """,
            (connection_id, secret_name),
        )
        connection.execute(
            """
            INSERT INTO integration_secret_versions (
              organization_id,
              connection_id,
              secret_name,
              encrypted_secret
            )
            VALUES (%s, %s, %s, pgp_sym_encrypt(%s, %s))
            """,
            (
                organization_id,
                connection_id,
                secret_name,
                secret_value,
                self._encryption_key(),
            ),
        )

    def _encryption_key(self) -> str:
        return (
            self.settings.sagad_integration_encryption_key
            or self.settings.agent_studio_internal_secret
            or "sagad-local-integration-key"
        )


def _record_from_row(row: DictRow) -> IntegrationConnectionRecord:
    return IntegrationConnectionRecord(
        provider=row["provider"],
        base_url=row["base_url"],
        account_id=row["account_id"],
        inbox_id=row["inbox_id"],
        api_mode=row["api_mode"],
        enabled=bool(row["enabled"]),
        dry_run=bool(row["dry_run"]),
        allow_writes=bool(row["allow_writes"]),
        api_access_token=row["api_access_token"],
        webhook_token=row["webhook_token"],
        api_key=row["api_key"],
        location_id=row["location_id"],
        outbound_mode=row["outbound_mode"],
        signature_scheme=row["signature_scheme"],
        poll_enabled=row["poll_enabled"],
        poll_interval_seconds=row["poll_interval_seconds"],
        poll_conversation_limit=row["poll_conversation_limit"],
        poll_message_limit=row["poll_message_limit"],
        webhook_secret=row["ghl_webhook_secret"],
        native_webhook_key=row["ghl_native_webhook_key"],
        updated_at=row["updated_at"],
    )


def build_integration_config_store(settings: Settings) -> IntegrationConfigStoreProtocol:
    if database_configured(settings):
        return PostgresIntegrationConfigStore(settings)
    return InMemoryIntegrationConfigStore()


integration_config_store = build_integration_config_store(get_settings())


def configured_settings(
    settings: Settings,
    context: StoreContext | None = None,
) -> Settings:
    chatwoot = integration_config_store.get("chatwoot", context=context)
    twenty = integration_config_store.get("twenty", context=context)
    ghl = integration_config_store.get("ghl", context=context)
    updates: dict[str, object] = {}
    if ghl and ghl.enabled:
        updates.update(
            {
                "ghl_base_url": ghl.base_url or settings.ghl_base_url,
                "ghl_api_key": ghl.api_key or settings.ghl_api_key,
                "ghl_location_id": ghl.location_id or settings.ghl_location_id,
                "ghl_outbound_mode": ghl.outbound_mode or settings.ghl_outbound_mode,
                "ghl_signature_scheme": ghl.signature_scheme or settings.ghl_signature_scheme,
                "ghl_dry_run": ghl.dry_run,
                "ghl_poll_enabled": ghl.poll_enabled
                if ghl.poll_enabled is not None
                else settings.ghl_poll_enabled,
                "ghl_poll_interval_seconds": ghl.poll_interval_seconds
                if ghl.poll_interval_seconds is not None
                else settings.ghl_poll_interval_seconds,
                "ghl_poll_conversation_limit": ghl.poll_conversation_limit
                if ghl.poll_conversation_limit is not None
                else settings.ghl_poll_conversation_limit,
                "ghl_poll_message_limit": ghl.poll_message_limit
                if ghl.poll_message_limit is not None
                else settings.ghl_poll_message_limit,
                "ghl_webhook_secret": ghl.webhook_secret or settings.ghl_webhook_secret,
                "ghl_native_webhook_key": ghl.native_webhook_key
                or settings.ghl_native_webhook_key,
            },
        )
    if chatwoot and chatwoot.enabled:
        updates.update(
            {
                "chatwoot_base_url": chatwoot.base_url or settings.chatwoot_base_url,
                "chatwoot_account_id": chatwoot.account_id or settings.chatwoot_account_id,
                "chatwoot_inbox_identifier": chatwoot.inbox_id
                or settings.chatwoot_inbox_identifier,
                "chatwoot_api_access_token": chatwoot.api_access_token
                or settings.chatwoot_api_access_token,
                "chatwoot_webhook_token": chatwoot.webhook_token or settings.chatwoot_webhook_token,
                "chatwoot_dry_run": chatwoot.dry_run,
            },
        )
    if twenty and twenty.enabled:
        updates.update(
            {
                "twenty_enabled": True,
                "twenty_base_url": twenty.base_url,
                "twenty_api_key": twenty.api_key,
                "twenty_api_mode": twenty.api_mode or settings.twenty_api_mode,
                "twenty_dry_run": twenty.dry_run,
                "twenty_allow_writes": twenty.allow_writes,
            },
        )
    # Model-provider config (SuperAdmin console). DB row overrides env; env is the fallback
    # when no row exists (mp is None). The resolver (model_config.py) reads merged Settings.
    mp = model_provider_config_store.get(context=context)
    if mp is not None:
        if mp.chat_provider:
            updates["model_provider"] = mp.chat_provider
        if mp.embedding_provider:
            updates["embedding_provider"] = mp.embedding_provider
        for field_name in MP_NON_SECRET_FIELDS:
            value = mp.config.get(field_name)
            if value is not None:
                updates[field_name] = value
        for secret_name in MP_SECRET_FIELDS:
            value = mp.secrets.get(secret_name)
            if value:
                updates[secret_name] = value
    return settings.model_copy(update=updates)


def _probe_ghl_connection(settings: Settings) -> tuple[str, str]:
    """Live, read-only GHL credential probe. Returns ``(status, detail)``.

    Hits the GHL location endpoint with the configured Bearer token + ``Version: 2021-04-15``
    header (same auth shape as ``adapters/ghl.py``). Never raises: any transport or HTTP
    failure is reported as ``error`` with a concrete reason so the supervisor sees the real
    outcome instead of a generic "configuration is present".
    """
    import httpx

    base_url = str(settings.ghl_base_url or "").rstrip("/")
    if not base_url or not settings.ghl_api_key or not settings.ghl_location_id:
        return ("unconfigured", "GHL base URL, API key, and location ID are required to test.")
    url = f"{base_url}/locations/{settings.ghl_location_id}"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(
                url,
                headers={
                    "Authorization": f"Bearer {settings.ghl_api_key}",
                    "Version": "2021-04-15",
                    "Accept": "application/json",
                },
            )
    except httpx.RequestError as exc:
        return ("error", f"GHL test request failed before a response: {exc.__class__.__name__}.")
    if response.is_success:
        return ("ready", f"GHL location reachable (HTTP {response.status_code}).")
    if response.status_code in (401, 403):
        return ("error", f"GHL credentials rejected (HTTP {response.status_code}).")
    return ("error", f"GHL test failed (HTTP {response.status_code}).")


def connection_test_result(
    provider: IntegrationProvider,
    context: StoreContext | None = None,
) -> tuple[str, str, IntegrationConnection]:
    connection = _connection_from_record(
        integration_config_store.get(provider, context=context),
        provider,
    )
    if connection.missing:
        return (
            "unconfigured",
            f"Missing {', '.join(connection.missing).replace('_', ' ')} before {connection.name} can be tested.",
            connection,
        )
    if not connection.enabled:
        return ("disabled", f"{connection.name} is configured but disabled.", connection)
    if provider == "ghl":
        # Dry-run gates sends, not reads — probe the live endpoint regardless of dry_run so
        # the supervisor sees whether the credentials actually work.
        settings = configured_settings(get_settings(), context=context)
        status, detail = _probe_ghl_connection(settings)
        return (status, detail, connection)
    if connection.dry_run:
        return ("dry_run", f"{connection.name} configuration is present; dry-run is enabled.", connection)
    return ("ready", f"{connection.name} configuration is present.", connection)
