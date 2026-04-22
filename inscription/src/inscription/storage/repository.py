"""High-level persistence API for cases.

This is the only module higher layers (controllers, UI) should use to talk
to case storage. It wraps SQLite, the filesystem layout, manifest I/O, and
lockfile management.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

from inscription.cases.models import (
    SCHEMA_VERSION,
    Case,
    CaseInfo,
    CaseManifest,
    Session,
    Step,
    StepKind,
    utcnow,
)
from inscription.cases.slug import slugify_case_number
from inscription.storage import locking
from inscription.storage.errors import (
    CaseAlreadyExistsError,
    CaseNotFoundError,
    StorageError,
)
from inscription.storage.manifest import read_manifest, write_manifest
from inscription.storage.schema import (
    initialise_schema,
    migrate_to_latest,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

logger = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


class CaseRepository:
    """Persistence API for a single open case.

    Instances are created via :meth:`create` or :meth:`open_existing` and
    must be closed with :meth:`close` (or used as a context manager).
    """

    def __init__(self, case: Case, conn: sqlite3.Connection) -> None:
        self._case = case
        self._conn = conn
        # SQLite connection is opened with check_same_thread=False; this lock
        # serialises access so the capture engine's worker thread and the UI
        # main thread can share the same connection safely.
        self._lock = threading.Lock()

    # ---------------------------------------------------------- lifecycle

    @classmethod
    def create(
        cls,
        *,
        workspace_root: Path,
        case_number: str,
        title: str,
        examiner: str,
        agency: str | None = None,
        description: str | None = None,
    ) -> CaseRepository:
        """Create a new case in ``workspace_root`` and open it."""
        slug = slugify_case_number(case_number)
        case_root = workspace_root / slug
        if case_root.exists():
            msg = f"Case directory {case_root} already exists"
            raise CaseAlreadyExistsError(msg)

        now = utcnow()
        info = CaseInfo(
            case_number=case_number,
            title=title,
            examiner=examiner,
            agency=agency,
            description=description,
            created_at=now,
            updated_at=now,
        )
        case = Case(info=info, root=case_root)

        # Lay out directories before anything else so lock acquisition
        # has a place to write.
        case.screenshots_dir.mkdir(parents=True, exist_ok=False)
        case.internal_dir.mkdir(parents=True, exist_ok=False)
        locking.acquire(case.internal_dir / "case.lock")

        conn = sqlite3.connect(case.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            initialise_schema(conn)
            conn.execute(
                """
                INSERT INTO case_info
                    (id, case_number, title, examiner, agency, description,
                     created_at, updated_at, schema_version)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    info.case_number,
                    info.title,
                    info.examiner,
                    info.agency,
                    info.description,
                    _iso(info.created_at),
                    _iso(info.updated_at),
                    SCHEMA_VERSION,
                ),
            )
            conn.commit()
        except Exception:
            conn.close()
            locking.release(case.internal_dir / "case.lock")
            raise

        repo = cls(case, conn)
        repo._write_manifest()
        (case.internal_dir / "version").write_text(str(SCHEMA_VERSION), encoding="utf-8")
        logger.info("Created case %s at %s", case_number, case_root)
        return repo

    @classmethod
    def open_existing(cls, *, workspace_root: Path, case_number: str) -> CaseRepository:
        """Open an existing case from ``workspace_root``."""
        slug = slugify_case_number(case_number)
        case_root = workspace_root / slug
        if not case_root.exists():
            msg = f"Case {case_number} not found in {workspace_root}"
            raise CaseNotFoundError(msg)
        return cls._open_at_root(case_root)

    @classmethod
    def _open_at_root(cls, case_root: Path) -> CaseRepository:
        if not (case_root / "case.db").exists():
            msg = f"No case.db under {case_root}"
            raise CaseNotFoundError(msg)
        case_root.mkdir(exist_ok=True)
        (case_root / "screenshots").mkdir(exist_ok=True)
        (case_root / ".inscription").mkdir(exist_ok=True)
        locking.acquire(case_root / ".inscription" / "case.lock")

        conn = sqlite3.connect(case_root / "case.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            migrate_to_latest(conn)
            info = cls._load_case_info(conn)
        except Exception:
            conn.close()
            locking.release(case_root / ".inscription" / "case.lock")
            raise

        case = Case(info=info, root=case_root)
        return cls(case, conn)

    def close(self) -> None:
        """Flush manifest, close DB, release lock."""
        try:
            self._write_manifest()
        finally:
            self._conn.close()
            locking.release(self._case.internal_dir / "case.lock")
        logger.info("Closed case %s", self._case.info.case_number)

    def __enter__(self) -> CaseRepository:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------ queries

    @property
    def case(self) -> Case:
        return self._case

    @staticmethod
    def _load_case_info(conn: sqlite3.Connection) -> CaseInfo:
        row = conn.execute("SELECT * FROM case_info WHERE id = 1").fetchone()
        if row is None:
            msg = "case_info row missing from database"
            raise StorageError(msg)
        return CaseInfo(
            case_number=row["case_number"],
            title=row["title"],
            examiner=row["examiner"],
            agency=row["agency"],
            description=row["description"],
            created_at=_parse_iso(row["created_at"]),
            updated_at=_parse_iso(row["updated_at"]),
            schema_version=row["schema_version"],
        )

    def list_steps(self, session_id: int | None = None) -> list[Step]:
        """Return all steps, optionally filtered to a session, in sequence order."""
        with self._lock:
            if session_id is None:
                rows = self._conn.execute(
                    "SELECT * FROM steps ORDER BY session_id, sequence"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM steps WHERE session_id = ? ORDER BY sequence",
                    (session_id,),
                ).fetchall()
        return [self._row_to_step(r) for r in rows]

    def list_sessions(self) -> list[Session]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM sessions ORDER BY id").fetchall()
        return [self._row_to_session(r) for r in rows]

    @staticmethod
    def _row_to_step(row: sqlite3.Row) -> Step:
        return Step(
            id=row["id"],
            session_id=row["session_id"],
            sequence=row["sequence"],
            captured_at=_parse_iso(row["captured_at"]),
            kind=StepKind(row["kind"]),
            title=row["title"],
            body_markdown=row["body_markdown"],
            screenshot_path=row["screenshot_path"],
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        return Session(
            id=row["id"],
            started_at=_parse_iso(row["started_at"]),
            ended_at=_parse_iso(row["ended_at"]) if row["ended_at"] else None,
            capture_mode=row["capture_mode"],
        )

    # ------------------------------------------------------------ mutations

    def start_session(self, capture_mode: str = "hotkey") -> Session:
        """Open a new capture session and return it."""
        started = utcnow()
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO sessions (started_at, capture_mode) VALUES (?, ?)",
                (_iso(started), capture_mode),
            )
            self._conn.commit()
            session_id = cursor.lastrowid
        assert session_id is not None
        return Session(id=session_id, started_at=started, capture_mode=capture_mode)

    def end_session(self, session_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
                (_iso(utcnow()), session_id),
            )
            self._conn.commit()

    def append_step(
        self,
        *,
        session_id: int,
        kind: StepKind,
        title: str = "",
        body_markdown: str = "",
        screenshot_path: str | None = None,
        captured_at: datetime | None = None,
    ) -> Step:
        """Append a step to the given session. Sequence is assigned automatically."""
        captured_at = captured_at or utcnow()
        with self._lock:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM steps WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            next_seq: int = row[0]
            cursor = self._conn.execute(
                """
                INSERT INTO steps
                    (session_id, sequence, captured_at, kind, title,
                     body_markdown, screenshot_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    next_seq,
                    _iso(captured_at),
                    kind.value,
                    title,
                    body_markdown,
                    screenshot_path,
                ),
            )
            self._touch_updated_at_locked()
            self._conn.commit()
            step_id = cursor.lastrowid
        assert step_id is not None
        return Step(
            id=step_id,
            session_id=session_id,
            sequence=next_seq,
            captured_at=captured_at,
            kind=kind,
            title=title,
            body_markdown=body_markdown,
            screenshot_path=screenshot_path,
        )

    def update_step_text(self, step_id: int, *, title: str, body_markdown: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE steps SET title = ?, body_markdown = ? WHERE id = ?",
                (title, body_markdown, step_id),
            )
            self._touch_updated_at_locked()
            self._conn.commit()

    def _touch_updated_at_locked(self) -> None:
        """Update the case's ``updated_at`` timestamp.

        Caller must already hold ``self._lock``.
        """
        self._conn.execute(
            "UPDATE case_info SET updated_at = ? WHERE id = 1",
            (_iso(utcnow()),),
        )

    # ------------------------------------------------------------ manifest

    def _write_manifest(self) -> None:
        with self._lock:
            count_row = self._conn.execute("SELECT COUNT(*) FROM steps").fetchone()
            info = self._load_case_info(self._conn)
        manifest = CaseManifest(
            case_number=info.case_number,
            title=info.title,
            examiner=info.examiner,
            created_at=info.created_at,
            updated_at=info.updated_at,
            step_count=count_row[0],
        )
        write_manifest(self._case.manifest_path, manifest)

    # ------------------------------------------------------------ transactions

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield the raw connection inside a transaction.

        Use sparingly; prefer the higher-level methods. Useful for batch
        operations added in future phases. Holds the repository's lock for
        the duration of the transaction.
        """
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise


# --------------------------------------------------------------- free funcs


def list_cases(workspace_root: Path) -> list[CaseManifest]:
    """Return a manifest for every case in ``workspace_root``.

    Cases without a manifest are silently skipped; we don't want a corrupt
    directory to break the case picker.
    """
    if not workspace_root.exists():
        return []
    manifests: list[CaseManifest] = []
    for child in sorted(workspace_root.iterdir()):
        manifest_path = child / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifests.append(read_manifest(manifest_path))
        except (OSError, ValueError, KeyError) as exc:
            logger.warning("Skipping malformed manifest at %s: %s", manifest_path, exc)
    return manifests
