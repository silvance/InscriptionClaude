"""SQL schema and forward-only migration runner.

Migrations are plain functions keyed by the target schema version. To add a
migration, append a new function to :data:`MIGRATIONS` that upgrades from
``version - 1`` to ``version``. The runner applies them in order.

We deliberately avoid Alembic: the schema is small, migrations are rare, and
a 30-line runner beats the dependency cost.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from inscription.cases.models import SCHEMA_VERSION
from inscription.storage.errors import SchemaVersionError

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable

logger = logging.getLogger(__name__)


#: Initial schema, applied when a case is first created. Subsequent versions
#: are reached by running migrations in order.
INITIAL_SCHEMA_SQL = """
CREATE TABLE case_info (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    case_number     TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    examiner        TEXT    NOT NULL,
    agency          TEXT,
    description     TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    schema_version  INTEGER NOT NULL
);

CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT    NOT NULL,
    ended_at        TEXT,
    capture_mode    TEXT    NOT NULL DEFAULT 'hotkey'
);

CREATE TABLE steps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    sequence        INTEGER NOT NULL,
    captured_at     TEXT    NOT NULL,
    kind            TEXT    NOT NULL,
    title           TEXT    NOT NULL DEFAULT '',
    body_markdown   TEXT    NOT NULL DEFAULT '',
    screenshot_path TEXT
);

CREATE INDEX idx_steps_session_sequence ON steps(session_id, sequence);
"""


#: Forward-only migrations keyed by target version. v1 is the initial schema.
#: Each function must be idempotent on a DB already at that version.
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}


def current_schema_version(conn: sqlite3.Connection) -> int:
    """Return the schema version recorded in ``case_info``, or 0 if none."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='case_info'"
    ).fetchone()
    if row is None:
        return 0
    result = conn.execute("SELECT schema_version FROM case_info WHERE id = 1").fetchone()
    if result is None:
        return 0
    version: int = result[0]
    return version


def initialise_schema(conn: sqlite3.Connection) -> None:
    """Apply the initial schema to a brand-new database."""
    conn.executescript(INITIAL_SCHEMA_SQL)
    conn.commit()
    logger.debug("Initial schema applied (version %d)", SCHEMA_VERSION)


def migrate_to_latest(conn: sqlite3.Connection) -> None:
    """Bring an existing DB up to :data:`SCHEMA_VERSION`.

    Raises:
        SchemaVersionError: If the DB is newer than this Inscription build
            knows how to handle.
    """
    version = current_schema_version(conn)
    if version > SCHEMA_VERSION:
        msg = (
            f"Case database schema version {version} is newer than this "
            f"Inscription build supports (max {SCHEMA_VERSION}). Update "
            f"Inscription or use a compatible build."
        )
        raise SchemaVersionError(msg)
    while version < SCHEMA_VERSION:
        target = version + 1
        migration = MIGRATIONS.get(target)
        if migration is None:
            msg = f"No migration registered for schema version {target}"
            raise SchemaVersionError(msg)
        logger.info("Migrating schema %d -> %d", version, target)
        migration(conn)
        conn.execute(
            "UPDATE case_info SET schema_version = ?, updated_at = updated_at WHERE id = 1",
            (target,),
        )
        conn.commit()
        version = target
