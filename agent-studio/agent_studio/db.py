from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import logging
import threading

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from agent_studio.config import Settings

DEFAULT_ORGANIZATION_SLUG = "johnred-workspace"
DEFAULT_USER_EMAIL = "owner@sagad.local"

_logger = logging.getLogger("agent_studio.db")

# Migrations are idempotent (CREATE ... IF NOT EXISTS), but we still memoize + lock so the
# startup path, the eager store constructors, and the /health/ready probe never run migrations
# concurrently or more than once after success. This keeps the container alive (liveness) even
# when the database is briefly unavailable, while readiness reflects the real DB state.
_migrations_lock = threading.Lock()
_migrations_applied = False


def initialize_database(settings: Settings) -> None:
    if not database_configured(settings):
        return
    with connect(settings) as connection:
        for path in migration_paths():
            with path.open("r", encoding="utf-8") as migration_file:
                connection.execute(migration_file.read())
        connection.commit()


def initialize_database_safe(settings: Settings, *, log: bool = True) -> bool:
    """Apply migrations without ever raising.

    Returns True if migrations are applied (or DATABASE_URL is unset), False on failure.
    Memoized + locked: once applied, subsequent calls are a cheap no-op. On failure the call
    is retryable — the next caller re-attempts, which self-heals once the database recovers.
    Use this at import time and in the lifespan so a slow/unreachable database never kills the
    process (which is what made the compose healthcheck report "unhealthy").
    """
    global _migrations_applied
    if not database_configured(settings):
        return True
    if _migrations_applied:
        return True
    with _migrations_lock:
        if _migrations_applied:  # double-check inside the lock
            return True
        try:
            initialize_database(settings)
            _migrations_applied = True
            return True
        except Exception as exc:  # noqa: BLE001 - startup must not crash the process
            if log:
                _logger.exception("Database initialization failed: %s", exc)
            return False


def database_ready(settings: Settings) -> tuple[bool, str]:
    """Cheap readiness probe that never raises.

    Ensures migrations are applied once (memoized), then performs a `SELECT 1` ping. Returns
    (ready, detail). Used by `/health/ready` so the probe does not re-run all migrations every
    call (the old behavior ran every migration file on each 10s probe).
    """
    if not database_configured(settings):
        return True, "DATABASE_URL is not configured; using in-memory preview stores."
    if not initialize_database_safe(settings, log=False):
        return False, "Database migrations failed; see agent_studio.db logs."
    try:
        with connect(settings) as connection:
            connection.execute("SELECT 1")
            connection.commit()
    except Exception as exc:  # noqa: BLE001 - readiness must not raise
        return False, f"Database ping failed: {exc.__class__.__name__}."
    return True, "Database reachable; migrations applied."


@dataclass(frozen=True)
class TrustedContext:
    organization_id: str | None = None
    user_id: str | None = None
    role: str = "supervisor"


def migrations_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "migrations"


def migration_paths() -> list[Path]:
    root = migrations_dir()
    if not root.exists():
        return []
    return sorted(root.glob("*.sql"))


def database_configured(settings: Settings) -> bool:
    return bool(settings.database_url and settings.database_url.strip())


@contextmanager
def connect(settings: Settings) -> Iterator[Connection[DictRow]]:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for the Postgres store.")
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=5) as connection:
        yield connection


def default_trusted_context(connection: Connection[DictRow]) -> TrustedContext:
    row = connection.execute(
        """
        SELECT
          organizations.id::text AS organization_id,
          users.id::text AS user_id,
          organization_members.role AS role
        FROM organization_members
        JOIN organizations ON organizations.id = organization_members.organization_id
        JOIN users ON users.id = organization_members.user_id
        WHERE organizations.slug = %s
          AND users.email = %s
          AND organization_members.status = 'active'
        LIMIT 1
        """,
        (DEFAULT_ORGANIZATION_SLUG, DEFAULT_USER_EMAIL),
    ).fetchone()
    if row is None:
        raise RuntimeError("Default Sagad organization seed was not found.")
    return TrustedContext(
        organization_id=str(row["organization_id"]),
        user_id=str(row["user_id"]),
        role=str(row["role"]),
    )


def resolve_trusted_context(
    connection: Connection[DictRow],
    context: TrustedContext | None,
) -> TrustedContext:
    default = default_trusted_context(connection)
    supplied = context or TrustedContext()
    user_id = supplied.user_id if supplied.user_id and supplied.user_id.isdigit() else default.user_id
    return TrustedContext(
        organization_id=supplied.organization_id or default.organization_id,
        user_id=user_id,
        role=supplied.role or default.role,
    )


def set_app_context(
    connection: Connection[DictRow],
    context: TrustedContext,
) -> None:
    if context.organization_id:
        connection.execute(
            "SELECT set_config('app.organization_id', %s, true)",
            (context.organization_id,),
        )
    if context.user_id:
        connection.execute(
            "SELECT set_config('app.user_id', %s, true)",
            (context.user_id,),
        )
    if context.role:
        connection.execute("SELECT set_config('app.role', %s, true)", (context.role,))
