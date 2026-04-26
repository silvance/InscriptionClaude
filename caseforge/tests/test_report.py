"""Report renderer + ReportContext tests.

The renderer tests need ``docxtpl`` installed; they skip cleanly when
it isn't, the same way the pytest-qt-dependent suites do. The
context-builder tests don't need docxtpl and run unconditionally — a
context can be assembled and inspected without ever rendering a
template.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from caseforge.model import (
    Case,
    CustodyRecord,
    ExaminerIdentity,
    ExamScope,
)
from caseforge.report.context import build_context
from caseforge.report.suggestions_reader import (
    suggestions_path as caseguide_suggestions_path,
)
from caseforge.storage import write_case

if TYPE_CHECKING:
    from pathlib import Path


_NOW = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


def _seed_case(case_dir: Path) -> Case:
    case = Case(
        name="Smoketest CSAM",
        case_reference="ST-001",
        created_at=_NOW,
        updated_at=_NOW,
        examiner=ExaminerIdentity(
            name="Alex Smith",
            organisation="Cyber Crimes Unit",
            badge_id="CCU-0421",
        ),
        scope=ExamScope(
            exam_type="CSAM possession",
            primary_tool="axiom",
            device_classes=["windows-laptop"],
            evidence_items=["E01 image"],
            agencies=["FBI", "ICAC"],
            summary="Single laptop, single image, single user.",
        ),
        custody=CustodyRecord(
            received_at=_NOW,
            received_from="Det. Rivers",
            delivery_method="in person",
            evidence_bag_ids=["BAG-12", "BAG-13"],
        ),
    )
    case_dir.mkdir(parents=True, exist_ok=True)
    write_case(case_dir, case)
    return case


def _write_suggestions(case_dir: Path) -> None:
    target = caseguide_suggestions_path(case_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-04-26T11:00:00+00:00",
                "scope_summary": "CSAM possession; Win11 laptop.",
                "playbooks": ["verify-image-hash", "axiom-ci-processing"],
                "suggestions": [
                    {
                        "id": "verify-image-hash",
                        "action": "Verify SHA-256.",
                        "priority": "required",
                        "category": "verification",
                        "expected_result": "Hash matches.",
                        "completed": True,
                        "completed_at": "2026-04-26T11:30:00+00:00",
                    },
                    {
                        "id": "axiom-ci-processing",
                        "action": "Run AXIOM Process.",
                        "priority": "required",
                        "category": "processing",
                        "depends_on": ["verify-image-hash"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


# ----------------------------------------------------- context builder


def test_context_builds_from_case_only(tmp_path: Path) -> None:
    """A fresh case dir with no suggestions / sessions still builds a context."""
    case_dir = tmp_path / "case"
    _seed_case(case_dir)

    ctx = build_context(case_dir, now=_NOW)
    assert ctx.case.name == "Smoketest CSAM"
    assert ctx.case.reference == "ST-001"
    assert ctx.examiner.name == "Alex Smith"
    assert ctx.examiner.is_present is True
    assert ctx.scope.exam_type == "CSAM possession"
    assert ctx.scope.evidence_items_csv == "E01 image"
    assert ctx.suggestions.has_data is False
    assert ctx.suggestions.total == 0
    assert ctx.suggestions.completed == []
    assert ctx.sessions.count == 0
    assert ctx.generated_at_iso == _NOW.isoformat()


def test_context_picks_up_suggestions_when_present(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _seed_case(case_dir)
    _write_suggestions(case_dir)

    ctx = build_context(case_dir, now=_NOW)
    assert ctx.suggestions.has_data is True
    assert ctx.suggestions.total == 2
    assert ctx.suggestions.completed_count == 1
    assert ctx.suggestions.required_count == 2
    assert [s.id for s in ctx.suggestions.completed] == ["verify-image-hash"]
    assert [s.id for s in ctx.suggestions.open] == ["axiom-ci-processing"]
    assert ctx.suggestions.completed[0].completed_at_str.startswith("2026-04-26 11:30")


def test_context_template_dict_is_render_safe(tmp_path: Path) -> None:
    """The flattened dict must not contain dataclass instances at any depth.

    docxtpl's Jinja2 sandbox is happier with plain dicts than with
    frozen-slots dataclasses, so the flattening must be total.
    """
    case_dir = tmp_path / "case"
    _seed_case(case_dir)
    _write_suggestions(case_dir)

    payload = build_context(case_dir, now=_NOW).as_template_dict()
    # Top-level: dict of dict / scalar
    assert isinstance(payload["case"], dict)
    assert isinstance(payload["suggestions"], dict)
    # Nested suggestion entries are dicts, not dataclasses
    completed = payload["suggestions"]["completed"]
    assert isinstance(completed, list)
    assert isinstance(completed[0], dict)
    assert completed[0]["id"] == "verify-image-hash"


def test_context_tolerates_malformed_suggestions(tmp_path: Path) -> None:
    """A garbage suggestions.json renders as 'no data' rather than raising."""
    case_dir = tmp_path / "case"
    _seed_case(case_dir)
    target = caseguide_suggestions_path(case_dir)
    target.parent.mkdir(parents=True)
    target.write_text("{not valid json", encoding="utf-8")

    ctx = build_context(case_dir, now=_NOW)
    assert ctx.suggestions.has_data is False


# --------------------------------------------------------- renderer

pytest.importorskip("docxtpl")
# The renderer tests below only run when docxtpl is installed.

from docx import Document  # noqa: E402  - import after the skip guard

from caseforge.report.render import RenderError, render_report  # noqa: E402


def _build_template(target: Path, body: str) -> None:
    """Write a tiny .docx whose only paragraph is ``body``."""
    doc = Document()
    doc.add_paragraph(body)
    doc.save(str(target))


def _read_paragraphs(path: Path) -> list[str]:
    return [p.text for p in Document(str(path)).paragraphs if p.text]


def test_render_substitutes_top_level_tokens(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _seed_case(case_dir)
    template = tmp_path / "template.docx"
    _build_template(
        template,
        "{{ case.name }} ({{ case.reference }}) — {{ examiner.name }}",
    )
    output = tmp_path / "out.docx"
    render_report(
        template_path=template,
        context=build_context(case_dir, now=_NOW),
        output_path=output,
    )
    paragraphs = _read_paragraphs(output)
    assert paragraphs == ["Smoketest CSAM (ST-001) — Alex Smith"]


def test_render_iterates_completed_suggestions(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _seed_case(case_dir)
    _write_suggestions(case_dir)
    template = tmp_path / "template.docx"
    _build_template(
        template,
        "{% for s in suggestions.completed %}DONE: {{ s.action }}{% endfor %}",
    )
    output = tmp_path / "out.docx"
    render_report(
        template_path=template,
        context=build_context(case_dir, now=_NOW),
        output_path=output,
    )
    paragraphs = _read_paragraphs(output)
    assert paragraphs == ["DONE: Verify SHA-256."]


def test_render_raises_on_missing_template(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _seed_case(case_dir)
    bogus = tmp_path / "does-not-exist.docx"
    with pytest.raises(RenderError, match="Template not found"):
        render_report(
            template_path=bogus,
            context=build_context(case_dir, now=_NOW),
            output_path=tmp_path / "out.docx",
        )


def test_render_raises_on_jinja_syntax_error(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    _seed_case(case_dir)
    template = tmp_path / "template.docx"
    _build_template(template, "{% for s in suggestions.completed %}oops")  # missing endfor
    with pytest.raises(RenderError):
        render_report(
            template_path=template,
            context=build_context(case_dir, now=_NOW),
            output_path=tmp_path / "out.docx",
        )
