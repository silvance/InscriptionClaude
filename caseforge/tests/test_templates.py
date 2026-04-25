"""Built-in + user-defined scope templates."""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING
from unittest.mock import patch

from caseforge.templates import (
    NO_TEMPLATE,
    ScopeTemplate,
    is_no_template,
    list_templates,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_list_templates_starts_with_the_no_template_sentinel() -> None:
    templates = list_templates()
    assert templates[0].id == NO_TEMPLATE.id
    assert is_no_template(templates[0])
    assert is_no_template(templates[1]) is False


def test_built_in_templates_are_present() -> None:
    """The four shipped templates should appear without any user dir."""
    with patch("caseforge.templates.TEMPLATES_DIR") as mock_dir:
        mock_dir.exists.return_value = False
        templates = list_templates()
    labels = {t.label for t in templates}
    assert "Forensic image acquisition" in labels
    assert "Mobile device extraction" in labels
    assert "Live system triage" in labels
    assert "Malware sandbox triage" in labels


def test_user_templates_load_from_disk(tmp_path: Path) -> None:
    payload = {
        "id": "internal-mobile",
        "label": "Internal mobile (Cellebrite)",
        "scope": {
            "exam_type": "Mobile",
            "device_classes": ["mobile-android"],
            "evidence_items": ["UFED extraction"],
            "summary": "Standard internal mobile path.",
            "notes": "See SOP MOB-2024.",
        },
    }
    (tmp_path / "internal-mobile.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    with patch("caseforge.templates.TEMPLATES_DIR", tmp_path):
        templates = list_templates()

    user = next(t for t in templates if t.id == "internal-mobile")
    assert user.label == "Internal mobile (Cellebrite)"
    assert user.scope.exam_type == "Mobile"
    assert user.scope.device_classes == ["mobile-android"]


def test_user_template_with_missing_id_falls_back_to_filename(tmp_path: Path) -> None:
    payload = {"label": "No ID Template", "scope": {"exam_type": "X"}}
    (tmp_path / "no-id.json").write_text(json.dumps(payload), encoding="utf-8")

    with patch("caseforge.templates.TEMPLATES_DIR", tmp_path):
        templates = list_templates()

    fallback = next(t for t in templates if t.label == "No ID Template")
    assert fallback.id == "no-id"


def test_malformed_user_template_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not valid", encoding="utf-8")
    (tmp_path / "good.json").write_text(
        json.dumps({"id": "g", "label": "Good", "scope": {}}),
        encoding="utf-8",
    )

    with patch("caseforge.templates.TEMPLATES_DIR", tmp_path):
        templates = list_templates()

    ids = {t.id for t in templates}
    assert "g" in ids
    assert "broken" not in ids


def test_template_with_non_object_root_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "list.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with patch("caseforge.templates.TEMPLATES_DIR", tmp_path):
        templates = list_templates()

    assert all(t.id != "list" for t in templates)


def test_no_template_scope_is_blank() -> None:
    blank = NO_TEMPLATE.scope
    assert blank.exam_type == ""
    assert blank.device_classes == []
    assert blank.evidence_items == []
    assert blank.agencies == []


def test_scope_template_round_trips_through_replace() -> None:
    """Frozen dataclass — `replace` should produce a new instance, not mutate."""
    template = list_templates()[1]  # first built-in
    assert isinstance(template, ScopeTemplate)
    copy = dataclasses.replace(template, label="Mutated")
    assert copy.label == "Mutated"
    assert template.label != "Mutated"
