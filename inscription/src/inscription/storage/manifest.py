"""JSON manifest read/write.

The manifest is a small file that duplicates a summary of case metadata so
the case list can populate without opening every SQLite database. It is
derived from ``case.db`` and is rewritten on every save; the DB remains the
source of truth.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from inscription.cases.models import SCHEMA_VERSION, CaseManifest

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def write_manifest(path: Path, manifest: CaseManifest) -> None:
    """Write ``manifest`` to ``path`` as pretty-printed JSON."""
    data = {
        "case_number": manifest.case_number,
        "title": manifest.title,
        "examiner": manifest.examiner,
        "created_at": manifest.created_at.isoformat(),
        "updated_at": manifest.updated_at.isoformat(),
        "step_count": manifest.step_count,
        "schema_version": manifest.schema_version,
        "tags": manifest.tags,
    }
    # Atomic write: stage to .tmp, rename in place. Avoids torn writes if
    # Inscription crashes mid-flush.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_manifest(path: Path) -> CaseManifest:
    """Load a manifest from disk."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return CaseManifest(
        case_number=raw["case_number"],
        title=raw["title"],
        examiner=raw["examiner"],
        created_at=datetime.fromisoformat(raw["created_at"]),
        updated_at=datetime.fromisoformat(raw["updated_at"]),
        step_count=int(raw["step_count"]),
        schema_version=int(raw.get("schema_version", SCHEMA_VERSION)),
        tags=list(raw.get("tags", [])),
    )
