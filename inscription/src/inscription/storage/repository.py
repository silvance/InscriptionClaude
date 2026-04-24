"""High-level persistence API for sessions.

This is the only module higher layers (controllers, UI) should use to talk
to session storage. It wraps SQLite, the filesystem layout, manifest I/O,
and lockfile management.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from inscription.model import (
    SCHEMA_VERSION,
    DraftStep,
    EventKind,
    RawEvent,
    ResolvedElement,
    ScreenshotArtifact,
    Session,
    SessionInfo,
    SessionManifest,
    utcnow,
)
from inscription.storage import locking
from inscription.storage.errors import (
    SessionAlreadyExistsError,
    SessionNotFoundError,
    StorageError,
)
from inscription.storage.manifest import read_manifest, write_manifest
from inscription.storage.schema import initialise_schema, migrate_to_latest
from inscription.storage.slug import slugify

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _dumps_rect(rect: tuple[int, int, int, int] | None) -> str | None:
    if rect is None:
        return None
    return json.dumps(list(rect))


def _loads_rect(raw: str | None) -> tuple[int, int, int, int] | None:
    if raw is None:
        return None
    parts = json.loads(raw)
    return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))


class SessionRepository:
    """Persistence API for a single open session."""

    def __init__(self, session: Session, conn: sqlite3.Connection) -> None:
        self._session = session
        self._conn = conn
        self._lock = threading.Lock()

    # ---------------------------------------------------------- lifecycle

    @classmethod
    def create(
        cls, *, workspace_root: Path, name: str, recorder_version: str = ""
    ) -> SessionRepository:
        """Create a new session directory and open it."""
        slug = slugify(name)
        root = workspace_root / slug
        if root.exists():
            msg = f"Session directory {root} already exists"
            raise SessionAlreadyExistsError(msg)

        now = utcnow()
        info = SessionInfo(name=name, started_at=now, recorder_version=recorder_version)
        session = Session(info=info, root=root)

        session.screenshots_dir.mkdir(parents=True, exist_ok=False)
        session.exports_dir.mkdir(parents=True, exist_ok=False)
        session.internal_dir.mkdir(parents=True, exist_ok=False)
        locking.acquire(session.internal_dir / "session.lock")

        conn = sqlite3.connect(session.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            initialise_schema(conn)
            conn.execute(
                """
                INSERT INTO session_info
                    (id, name, started_at, ended_at, recorder_version, schema_version)
                VALUES (1, ?, ?, NULL, ?, ?)
                """,
                (info.name, _iso(info.started_at), recorder_version, SCHEMA_VERSION),
            )
            conn.commit()
        except Exception:
            conn.close()
            locking.release(session.internal_dir / "session.lock")
            raise

        repo = cls(session, conn)
        repo._write_manifest()
        logger.info("Created session %r at %s", name, root)
        return repo

    @classmethod
    def open_existing(cls, *, workspace_root: Path, slug: str) -> SessionRepository:
        root = workspace_root / slug
        if not root.exists():
            msg = f"Session {slug!r} not found in {workspace_root}"
            raise SessionNotFoundError(msg)
        return cls._open_at_root(root)

    @classmethod
    def _open_at_root(cls, root: Path) -> SessionRepository:
        if not (root / "session.db").exists():
            msg = f"No session.db under {root}"
            raise SessionNotFoundError(msg)
        (root / "screenshots").mkdir(exist_ok=True)
        (root / "exports").mkdir(exist_ok=True)
        (root / ".inscription").mkdir(exist_ok=True)
        locking.acquire(root / ".inscription" / "session.lock")

        conn = sqlite3.connect(root / "session.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            migrate_to_latest(conn)
            info = cls._load_info(conn)
        except Exception:
            conn.close()
            locking.release(root / ".inscription" / "session.lock")
            raise

        session = Session(info=info, root=root)
        return cls(session, conn)

    def close(self) -> None:
        try:
            self._write_manifest()
        finally:
            self._conn.close()
            locking.release(self._session.internal_dir / "session.lock")
        logger.info("Closed session %r", self._session.info.name)

    def __enter__(self) -> SessionRepository:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ----------------------------------------------------------- queries

    @property
    def session(self) -> Session:
        return self._session

    @staticmethod
    def _load_info(conn: sqlite3.Connection) -> SessionInfo:
        row = conn.execute("SELECT * FROM session_info WHERE id = 1").fetchone()
        if row is None:
            msg = "session_info row missing from database"
            raise StorageError(msg)
        return SessionInfo(
            name=row["name"],
            started_at=_parse_iso(row["started_at"]),
            ended_at=_parse_iso(row["ended_at"]) if row["ended_at"] else None,
            recorder_version=row["recorder_version"],
            schema_version=row["schema_version"],
        )

    def list_events(self) -> list[RawEvent]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM raw_events ORDER BY sequence").fetchall()
        return [self._row_to_event(r) for r in rows]

    def list_steps(self, *, include_suppressed: bool = False) -> list[DraftStep]:
        with self._lock:
            if include_suppressed:
                rows = self._conn.execute("SELECT * FROM draft_steps ORDER BY sequence").fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM draft_steps WHERE suppressed = 0 ORDER BY sequence"
                ).fetchall()
        return [self._row_to_step(r) for r in rows]

    def list_screenshots(self) -> list[ScreenshotArtifact]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM screenshot_artifacts ORDER BY id").fetchall()
        return [self._row_to_screenshot(r) for r in rows]

    def get_screenshot(self, screenshot_id: int) -> ScreenshotArtifact | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM screenshot_artifacts WHERE id = ?", (screenshot_id,)
            ).fetchone()
        return self._row_to_screenshot(row) if row else None

    def get_resolved_element(self, element_id: int) -> ResolvedElement | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM resolved_elements WHERE id = ?", (element_id,)
            ).fetchone()
        return self._row_to_element(row) if row else None

    # --------------------------------------------------------- mutations

    def end_session(self) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE session_info SET ended_at = ? WHERE id = 1 AND ended_at IS NULL",
                (_iso(utcnow()),),
            )
            self._conn.commit()

    def add_screenshot(
        self,
        *,
        relative_path: str,
        captured_at: datetime,
        width: int,
        height: int,
        sha256: str = "",
        highlight_rect: tuple[int, int, int, int] | None = None,
    ) -> ScreenshotArtifact:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO screenshot_artifacts
                    (relative_path, captured_at, width, height, sha256, highlight_rect)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    relative_path,
                    _iso(captured_at),
                    width,
                    height,
                    sha256,
                    _dumps_rect(highlight_rect),
                ),
            )
            self._conn.commit()
            screenshot_id = cursor.lastrowid
        assert screenshot_id is not None
        return ScreenshotArtifact(
            id=screenshot_id,
            relative_path=relative_path,
            captured_at=captured_at,
            width=width,
            height=height,
            sha256=sha256,
            highlight_rect=highlight_rect,
        )

    def add_resolved_element(self, element: ResolvedElement) -> ResolvedElement:
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO resolved_elements
                    (name, control_type, automation_id, class_name, role,
                     confidence, method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    element.name,
                    element.control_type,
                    element.automation_id,
                    element.class_name,
                    element.role,
                    element.confidence,
                    element.method,
                ),
            )
            self._conn.commit()
            element_id = cursor.lastrowid
        assert element_id is not None
        return ResolvedElement(
            id=element_id,
            name=element.name,
            control_type=element.control_type,
            automation_id=element.automation_id,
            class_name=element.class_name,
            role=element.role,
            confidence=element.confidence,
            method=element.method,
        )

    def append_event(
        self,
        *,
        kind: EventKind,
        occurred_at: datetime | None = None,
        button: str | None = None,
        x: int | None = None,
        y: int | None = None,
        key: str | None = None,
        text: str | None = None,
        window_title: str | None = None,
        process_name: str | None = None,
        screenshot_id: int | None = None,
        resolved_element_id: int | None = None,
    ) -> RawEvent:
        occurred_at = occurred_at or utcnow()
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM raw_events"
            ).fetchone()
            next_seq: int = row[0]
            cursor = self._conn.execute(
                """
                INSERT INTO raw_events
                    (sequence, occurred_at, kind, button, x, y, key, text,
                     window_title, process_name, screenshot_id,
                     resolved_element_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    next_seq,
                    _iso(occurred_at),
                    kind.value,
                    button,
                    x,
                    y,
                    key,
                    text,
                    window_title,
                    process_name,
                    screenshot_id,
                    resolved_element_id,
                ),
            )
            self._conn.commit()
            event_id = cursor.lastrowid
        assert event_id is not None
        return RawEvent(
            id=event_id,
            sequence=next_seq,
            occurred_at=occurred_at,
            kind=kind,
            button=button,
            x=x,
            y=y,
            key=key,
            text=text,
            window_title=window_title,
            process_name=process_name,
            screenshot_id=screenshot_id,
            resolved_element_id=resolved_element_id,
        )

    def replace_steps(self, steps: list[DraftStep]) -> list[DraftStep]:
        """Replace every draft step with ``steps``, reassigning sequences.

        Used by the step generator after grouping raw events.
        """
        saved: list[DraftStep] = []
        with self._lock:
            self._conn.execute("DELETE FROM draft_steps")
            for i, step in enumerate(steps, start=1):
                cursor = self._conn.execute(
                    """
                    INSERT INTO draft_steps
                        (sequence, text, source_event_ids, screenshot_id,
                         suppressed, manual_edit)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        i,
                        step.text,
                        json.dumps(list(step.source_event_ids)),
                        step.screenshot_id,
                        1 if step.suppressed else 0,
                        1 if step.manual_edit else 0,
                    ),
                )
                step_id = cursor.lastrowid
                assert step_id is not None
                saved.append(
                    DraftStep(
                        id=step_id,
                        sequence=i,
                        text=step.text,
                        source_event_ids=step.source_event_ids,
                        screenshot_id=step.screenshot_id,
                        suppressed=step.suppressed,
                        manual_edit=step.manual_edit,
                    )
                )
            self._conn.commit()
        return saved

    def update_step_text(self, step_id: int, text: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE draft_steps SET text = ?, manual_edit = 1 WHERE id = ?",
                (text, step_id),
            )
            self._conn.commit()

    def set_step_suppressed(self, step_id: int, *, suppressed: bool) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE draft_steps SET suppressed = ? WHERE id = ?",
                (1 if suppressed else 0, step_id),
            )
            self._conn.commit()

    def reorder_steps(self, ordered_step_ids: list[int]) -> None:
        """Rewrite sequence numbers to match ``ordered_step_ids``."""
        with self._lock:
            for i, step_id in enumerate(ordered_step_ids, start=1):
                self._conn.execute(
                    "UPDATE draft_steps SET sequence = ? WHERE id = ?",
                    (i, step_id),
                )
            self._conn.commit()

    def set_step_screenshot(self, step_id: int, screenshot_id: int | None) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE draft_steps SET screenshot_id = ? WHERE id = ?",
                (screenshot_id, step_id),
            )
            self._conn.commit()

    # ----------------------------------------------------------- manifest

    def _write_manifest(self) -> None:
        with self._lock:
            event_row = self._conn.execute("SELECT COUNT(*) FROM raw_events").fetchone()
            step_row = self._conn.execute(
                "SELECT COUNT(*) FROM draft_steps WHERE suppressed = 0"
            ).fetchone()
            info = self._load_info(self._conn)
        manifest = SessionManifest(
            name=info.name,
            started_at=info.started_at,
            ended_at=info.ended_at,
            event_count=event_row[0],
            step_count=step_row[0],
        )
        write_manifest(self._session.manifest_path, manifest)

    def flush_manifest(self) -> None:
        """Re-derive and write the manifest. Call after bulk mutations."""
        self._write_manifest()

    # --------------------------------------------------------- row mapping

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> RawEvent:
        return RawEvent(
            id=row["id"],
            sequence=row["sequence"],
            occurred_at=_parse_iso(row["occurred_at"]),
            kind=EventKind(row["kind"]),
            button=row["button"],
            x=row["x"],
            y=row["y"],
            key=row["key"],
            text=row["text"],
            window_title=row["window_title"],
            process_name=row["process_name"],
            screenshot_id=row["screenshot_id"],
            resolved_element_id=row["resolved_element_id"],
        )

    @staticmethod
    def _row_to_step(row: sqlite3.Row) -> DraftStep:
        return DraftStep(
            id=row["id"],
            sequence=row["sequence"],
            text=row["text"],
            source_event_ids=tuple(json.loads(row["source_event_ids"])),
            screenshot_id=row["screenshot_id"],
            suppressed=bool(row["suppressed"]),
            manual_edit=bool(row["manual_edit"]),
        )

    @staticmethod
    def _row_to_screenshot(row: sqlite3.Row) -> ScreenshotArtifact:
        return ScreenshotArtifact(
            id=row["id"],
            relative_path=row["relative_path"],
            captured_at=_parse_iso(row["captured_at"]),
            width=row["width"],
            height=row["height"],
            sha256=row["sha256"],
            highlight_rect=_loads_rect(row["highlight_rect"]),
        )

    @staticmethod
    def _row_to_element(row: sqlite3.Row) -> ResolvedElement:
        return ResolvedElement(
            id=row["id"],
            name=row["name"],
            control_type=row["control_type"],
            automation_id=row["automation_id"],
            class_name=row["class_name"],
            role=row["role"],
            confidence=row["confidence"],
            method=row["method"],
        )


# --------------------------------------------------------------- free funcs


def list_sessions(workspace_root: Path) -> list[tuple[str, SessionManifest]]:
    """Return ``(slug, manifest)`` pairs for every session in ``workspace_root``.

    Directories without a manifest are silently skipped.
    """
    if not workspace_root.exists():
        return []
    out: list[tuple[str, SessionManifest]] = []
    for child in sorted(workspace_root.iterdir()):
        if not child.is_dir():
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            out.append((child.name, read_manifest(manifest_path)))
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Skipping malformed manifest at %s: %s", manifest_path, exc)
    return out
