"""Forward-only schema migrations.

Simulates a v1 session database (the shipped alpha), runs the migration
runner, and asserts the v2 ``bounding_rect`` column is present afterwards
and the repository can read/write it.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from inscription.model import ResolvedElement
from inscription.storage import SessionRepository

if TYPE_CHECKING:
    from pathlib import Path

# Inline copy of the v1 INITIAL_SCHEMA_SQL. Pinned here so future changes
# to the current schema don't silently retune this test — the whole point
# is to exercise the migration from the actually-shipped v1 shape.
_V1_SCHEMA = """
CREATE TABLE session_info (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    name              TEXT    NOT NULL,
    started_at        TEXT    NOT NULL,
    ended_at          TEXT,
    recorder_version  TEXT    NOT NULL DEFAULT '',
    schema_version    INTEGER NOT NULL
);

CREATE TABLE resolved_elements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT,
    control_type    TEXT,
    automation_id   TEXT,
    class_name      TEXT,
    role            TEXT,
    confidence      REAL    NOT NULL DEFAULT 0,
    method          TEXT    NOT NULL DEFAULT 'none'
);

CREATE TABLE screenshot_artifacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    relative_path   TEXT    NOT NULL UNIQUE,
    captured_at     TEXT    NOT NULL,
    width           INTEGER NOT NULL,
    height          INTEGER NOT NULL,
    sha256          TEXT    NOT NULL DEFAULT '',
    highlight_rect  TEXT
);

CREATE TABLE raw_events (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence             INTEGER NOT NULL,
    occurred_at          TEXT    NOT NULL,
    kind                 TEXT    NOT NULL,
    button               TEXT,
    x                    INTEGER,
    y                    INTEGER,
    key                  TEXT,
    text                 TEXT,
    window_title         TEXT,
    process_name         TEXT,
    screenshot_id        INTEGER REFERENCES screenshot_artifacts(id),
    resolved_element_id  INTEGER REFERENCES resolved_elements(id)
);

CREATE INDEX idx_raw_events_sequence ON raw_events(sequence);

CREATE TABLE draft_steps (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence          INTEGER NOT NULL,
    text              TEXT    NOT NULL DEFAULT '',
    source_event_ids  TEXT    NOT NULL DEFAULT '[]',
    screenshot_id     INTEGER REFERENCES screenshot_artifacts(id),
    suppressed        INTEGER NOT NULL DEFAULT 0,
    manual_edit       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_draft_steps_sequence ON draft_steps(sequence);
"""


def _build_v1_session(root: Path, name: str) -> None:
    """Lay out a session folder matching what a v1 build would have left."""
    slug = name
    session_root = root / slug
    session_root.mkdir()
    (session_root / "screenshots").mkdir()
    (session_root / "exports").mkdir()
    (session_root / ".inscription").mkdir()
    (session_root / "manifest.json").write_text(
        '{"name": "' + name + '", "started_at": "2026-04-24T00:00:00+00:00",'
        ' "ended_at": null, "event_count": 0, "step_count": 0,'
        ' "schema_version": 1, "tags": []}\n',
        encoding="utf-8",
    )
    conn = sqlite3.connect(session_root / "session.db")
    conn.executescript(_V1_SCHEMA)
    conn.execute(
        "INSERT INTO session_info (id, name, started_at, schema_version) "
        "VALUES (1, ?, '2026-04-24T00:00:00+00:00', 1)",
        (name,),
    )
    # Pre-existing row — exercises ALTER TABLE backfilling NULL into new column.
    conn.execute(
        "INSERT INTO resolved_elements (name, control_type, confidence, method) "
        "VALUES ('Legacy', 'Button', 0.9, 'uia')"
    )
    conn.commit()
    conn.close()


def test_v1_session_migrates_and_exposes_bounding_rect(tmp_path: Path) -> None:
    _build_v1_session(tmp_path, "Legacy-Session")

    repo = SessionRepository.open_existing(workspace_root=tmp_path, slug="Legacy-Session")
    try:
        # Existing row survives the ALTER TABLE and has None for the new column.
        legacy = repo.get_resolved_element(1)
        assert legacy is not None
        assert legacy.name == "Legacy"
        assert legacy.bounding_rect is None

        # New inserts write and read the rect end-to-end.
        fresh = repo.add_resolved_element(
            ResolvedElement(
                id=None,
                name="New",
                control_type="Button",
                confidence=0.9,
                method="uia",
                bounding_rect=(10, 20, 110, 50),
            )
        )
        assert fresh.id is not None
        reloaded = repo.get_resolved_element(fresh.id)
        assert reloaded is not None
        assert reloaded.bounding_rect == (10, 20, 110, 50)
    finally:
        repo.close()
