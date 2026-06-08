from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from agent_studio.config import Settings, get_settings
from agent_studio.db import (
    TrustedContext,
    connect,
    database_configured,
    initialize_database,
    resolve_trusted_context,
    set_app_context,
)
from agent_studio.schemas import (
    IntegrationConnection,
    IntegrationConnectionUpsertRequest,
    IntegrationKind,
    IntegrationProvider,
)
from agent_studio.store import StoreContext


ADMIN_ROLES = {"owner", "admin"}
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
    return "Chatwoot" if provider == "chatwoot" else "Twenty CRM"


def _provider_kind(provider: IntegrationProvider) -> IntegrationKind:
    return "channel" if provider == "chatwoot" else "crm"


def _connection_from_record(record: IntegrationConnectionRecord | None, provider: IntegrationProvider) -> IntegrationConnection:
    if record is None:
        missing = ["base_url", "api_access_token"] if provider == "chatwoot" else ["base_url", "api_key"]
        if provider == "chatwoot":
            missing.append("account_id")
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
            missing=missing,
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
        configured = not missing
        status = "ready" if configured and record.enabled and not record.dry_run else "dry_run"
        if not record.enabled:
            status = "disabled"
    else:
        if not record.api_key:
            missing.append("api_key")
        configured = not missing
        status = "ready" if configured and record.enabled and not record.dry_run else "dry_run"
        if not record.enabled:
            status = "disabled"

    if not configured:
        status = "unconfigured"

    writes_enabled = (
        bool(record.enabled)
        and bool(configured)
        and bool(record.allow_writes)
        and not bool(record.dry_run)
    )
    detail = _connection_detail(provider, status, missing, writes_enabled)
    return IntegrationConnection(
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
    for provider in ("chatwoot", "twenty"):
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
        initialize_database(settings)

    def list(self, context: StoreContext | None = None) -> list[IntegrationConnection]:
        return [_connection_from_record(self.get(provider, context=context), provider) for provider in ("chatwoot", "twenty")]

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
                  integration_connections.updated_at,
                  pgp_sym_decrypt(api_access.encrypted_secret, %s) AS api_access_token,
                  pgp_sym_decrypt(webhook.encrypted_secret, %s) AS webhook_token,
                  pgp_sym_decrypt(api_key.encrypted_secret, %s) AS api_key
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
                WHERE integration_connections.organization_id = %s
                  AND integration_connections.provider = %s
                LIMIT 1
                """,
                (
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
                  updated_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (organization_id, provider) DO UPDATE SET
                  base_url = COALESCE(EXCLUDED.base_url, integration_connections.base_url),
                  account_id = COALESCE(EXCLUDED.account_id, integration_connections.account_id),
                  inbox_id = COALESCE(EXCLUDED.inbox_id, integration_connections.inbox_id),
                  api_mode = COALESCE(EXCLUDED.api_mode, integration_connections.api_mode),
                  enabled = EXCLUDED.enabled,
                  dry_run = EXCLUDED.dry_run,
                  allow_writes = EXCLUDED.allow_writes,
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
    updates: dict[str, object] = {}
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
    return settings.model_copy(update=updates)


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
    if connection.dry_run:
        return ("dry_run", f"{connection.name} configuration is present; dry-run is enabled.", connection)
    return ("ready", f"{connection.name} configuration is present.", connection)
