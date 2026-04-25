"""Case-scope templates.

Templates are pre-filled :class:`ExamScope` values an examiner can drop
into the New-case dialog instead of typing the same boilerplate every
time. CaseForge ships a small built-in set; users can add their own by
dropping a JSON file into ``%LOCALAPPDATA%\\CaseForge\\templates\\``.

User-template format (one template per file):

```json
{
  "id": "internal-mobile-extraction",
  "label": "Internal mobile extraction (Cellebrite)",
  "scope": {
    "exam_type": "Mobile device extraction",
    "device_classes": ["mobile-android"],
    "evidence_items": ["Cellebrite extraction"],
    "agencies": [],
    "summary": "Extract a logical and (where supported) physical image.",
    "notes": "Refer to internal SOP MOB-2024 for the consent paperwork."
  }
}
```

Anything missing falls back to a sensible default. Malformed files are
logged and skipped — they don't take down the picker.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from caseforge.model import ExamScope
from caseforge.paths import TEMPLATES_DIR

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeTemplate:
    """Named pre-fill for the Scope tab on a new case."""

    id: str
    label: str
    scope: ExamScope


_BUILTIN_TEMPLATES: tuple[ScopeTemplate, ...] = (
    ScopeTemplate(
        id="builtin-image-acquisition",
        label="Forensic image acquisition",
        scope=ExamScope(
            exam_type="Forensic image acquisition",
            device_classes=["windows-laptop"],
            evidence_items=["E01 image"],
            agencies=[],
            summary=(
                "Acquire a forensic image of the subject device, verify the "
                "hash against the acquisition log, and stage the image for "
                "analysis."
            ),
            notes=(
                "Steps: chain-of-custody intake -> write-blocker on -> "
                "FTK Imager / dd acquire -> SHA-256 verify."
            ),
        ),
    ),
    ScopeTemplate(
        id="builtin-mobile-extraction",
        label="Mobile device extraction",
        scope=ExamScope(
            exam_type="Mobile device extraction",
            device_classes=["mobile-android", "mobile-ios"],
            evidence_items=["Cellebrite extraction"],
            agencies=[],
            summary=(
                "Logical and (where supported) physical extraction of the "
                "subject mobile device using Cellebrite UFED."
            ),
            notes="Confirm passcode / consent before extraction.",
        ),
    ),
    ScopeTemplate(
        id="builtin-live-triage",
        label="Live system triage",
        scope=ExamScope(
            exam_type="Live system triage",
            device_classes=["windows-laptop"],
            evidence_items=["Volatile RAM capture", "Triage artefact bundle"],
            agencies=[],
            summary=(
                "Capture volatile memory and a triage artefact bundle "
                "(registry hives, event logs, prefetch, browser history) "
                "from the running system."
            ),
            notes="Document RAM-capture tool and version in the notes.",
        ),
    ),
    ScopeTemplate(
        id="builtin-malware-triage",
        label="Malware sandbox triage",
        scope=ExamScope(
            exam_type="Malware triage",
            device_classes=["sandbox-vm"],
            evidence_items=["Suspicious binary"],
            agencies=[],
            summary=(
                "Detonate the suspect sample inside an isolated sandbox VM "
                "and collect runtime artefacts."
            ),
            notes=(
                "Snapshot the sandbox before detonation; revert after. "
                "Network isolation must be verified."
            ),
        ),
    ),
)


_NO_TEMPLATE_ID = "__none__"
NO_TEMPLATE = ScopeTemplate(
    id=_NO_TEMPLATE_ID,
    label="(no template)",
    scope=ExamScope(),
)


def list_templates() -> list[ScopeTemplate]:
    """Return the picker feed: ``(no template)`` first, then built-ins, then user templates."""
    user = _load_user_templates(TEMPLATES_DIR)
    return [NO_TEMPLATE, *_BUILTIN_TEMPLATES, *user]


def is_no_template(template: ScopeTemplate) -> bool:
    return template.id == _NO_TEMPLATE_ID


def _load_user_templates(directory: Path) -> list[ScopeTemplate]:
    if not directory.exists() or not directory.is_dir():
        return []
    out: list[ScopeTemplate] = []
    for path in sorted(directory.glob("*.json")):
        parsed = _parse_template(path)
        if parsed is not None:
            out.append(parsed)
    return out


def _parse_template(path: Path) -> ScopeTemplate | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Skipping malformed template %s: %s", path, exc)
        return None
    if not isinstance(raw, dict):
        logger.warning("Template %s is not a JSON object", path)
        return None
    template_id = str(raw.get("id") or path.stem)
    label = str(raw.get("label") or path.stem)
    scope_raw = raw.get("scope", {})
    if not isinstance(scope_raw, dict):
        scope_raw = {}
    return ScopeTemplate(
        id=template_id,
        label=label,
        scope=ExamScope(
            exam_type=str(scope_raw.get("exam_type", "")),
            device_classes=_string_list(scope_raw.get("device_classes")),
            evidence_items=_string_list(scope_raw.get("evidence_items")),
            agencies=_string_list(scope_raw.get("agencies")),
            summary=str(scope_raw.get("summary", "")),
            notes=str(scope_raw.get("notes", "")),
        ),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]
