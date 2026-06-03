from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg import Connection
from psycopg.rows import DictRow, dict_row

from agent_studio.config import Settings

DEFAULT_ORGANIZATION_SLUG = "johnred-workspace"
DEFAULT_USER_EMAIL = "owner@sagad.local"


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
    with psycopg.connect(settings.database_url, row_factory=dict_row) as connection:
        yield connection


def initialize_database(settings: Settings) -> None:
    if not database_configured(settings):
        return
    with connect(settings) as connection:
        for path in migration_paths():
            with path.open("r", encoding="utf-8") as migration_file:
                connection.execute(migration_file.read())
        connection.commit()


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
