"""Build the data context the DOCX template renders against.

The template vocabulary is documented exhaustively here so an
examiner authoring a template has a single reference. Tokens are
exposed as nested attributes (``case.name``, ``examiner.name``) and
iteration is done with Jinja2 ``{% for %}`` blocks.

------------------------------------------------------------------------
SUPPORTED TEMPLATE TOKENS
------------------------------------------------------------------------

Top-level singletons:

- ``{{ generated_at }}``                Human-readable timestamp of
                                        the report render itself.
- ``{{ generated_at_iso }}``            ISO 8601 form of the same.

Case (from ``case.json``):

- ``{{ case.name }}``                   The case name CaseForge wrote.
- ``{{ case.reference }}``              External case reference.
- ``{{ case.created_at }}``             Case-creation timestamp (raw
                                        datetime — call ``.strftime``
                                        for custom formats).
- ``{{ case.created_at_str }}``         Pre-formatted creation
                                        timestamp ("YYYY-MM-DD HH:MM UTC").
- ``{{ case.updated_at }}``             Last-edit timestamp (raw).
- ``{{ case.updated_at_str }}``         Pre-formatted last-edit ts.
- ``{{ case.path }}``                   Absolute path to the case dir.

Examiner identity (from ``case.json``):

- ``{{ examiner.name }}``
- ``{{ examiner.organisation }}``
- ``{{ examiner.badge_id }}``
- ``{{ examiner.is_present }}``         True when name is set.

Exam scope (from ``case.json``):

- ``{{ scope.exam_type }}``
- ``{{ scope.primary_tool }}``          Display label, not the stable id.
- ``{{ scope.summary }}``
- ``{{ scope.notes }}``
- ``{{ scope.device_classes_csv }}``    Comma-joined for prose.
- ``{{ scope.evidence_items_csv }}``    Comma-joined for prose.
- ``{{ scope.agencies_csv }}``          Comma-joined for prose.
- ``scope.device_classes``              List, for ``{% for d in ... %}``.
- ``scope.evidence_items``              List, for ``{% for e in ... %}``.
- ``scope.agencies``                    List, for ``{% for a in ... %}``.

Custody (from ``case.json``):

- ``{{ custody.received_at }}``         Raw datetime, or None — guard
                                        with ``{% if custody.received_at %}``
                                        before calling ``.strftime``.
- ``{{ custody.received_at_str }}``     Pre-formatted, or empty string
                                        when no received_at is set
                                        (avoids "None" appearing in
                                        the rendered report).
- ``{{ custody.received_from }}``
- ``{{ custody.delivery_method }}``
- ``{{ custody.evidence_bag_ids_csv }}``
- ``custody.evidence_bag_ids``          List form.

Suggestions (from ``.caseguide/suggestions.json``; everything is
present-but-empty when CaseGuide hasn't been run on this case):

- ``{{ suggestions.total }}``           Total count.
- ``{{ suggestions.completed_count }}``
- ``{{ suggestions.required_count }}``
- ``{{ suggestions.scope_summary }}``   The CaseGuide scope blurb.
- ``{{ suggestions.has_data }}``        False when no file present.
- ``suggestions.completed``             List of completed entries
                                        for ``{% for s in ... %}``.
- ``suggestions.open``                  List of incomplete entries.
- ``suggestions.all``                   Full ordered list.
- ``suggestions.playbooks``             Source-playbook id list.

  Each entry exposes: ``id``, ``action``, ``priority``, ``category``,
  ``expected_result``, ``rationale``, ``references`` (list),
  ``completed`` (bool), ``completed_at`` (datetime or None),
  ``completed_at_str`` (str, "" when not completed).

Inscription sessions (one entry per recorded session under the case
dir):

- ``{{ sessions.count }}``              Total recorded sessions.
- ``sessions.all``                      List form, newest first.
- ``sessions.completed``                List of finished sessions
                                        (``ended_at`` is set).
- ``sessions.in_progress``              List of unfinished sessions.

  Each entry: ``slug``, ``name``, ``started_at``, ``ended_at`` (or
  None), ``started_at_str``, ``ended_at_str`` ("" when in progress),
  ``event_count``, ``step_count``, ``path`` (str), ``is_in_progress``.

------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from caseforge.inscription_sessions import (
    InscriptionSession,
    list_inscription_sessions,
)
from caseforge.report.suggestions_reader import (
    CaseguideDocument,
    CaseguideSuggestion,
    read_suggestions,
)
from caseforge.storage import read_case
from caseforge.version import __version__

if TYPE_CHECKING:
    from pathlib import Path

    from caseforge.model import Case

#: Date format we hand templates by default. ISO is unambiguous and
#: still readable; reports that want a friendlier format can call
#: ``.strftime`` on the raw datetime objects.
_DEFAULT_TS_FORMAT = "%Y-%m-%d %H:%M UTC"


@dataclass(frozen=True, slots=True, kw_only=True)
class _ExaminerView:
    name: str
    organisation: str
    badge_id: str
    is_present: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class _ScopeView:
    exam_type: str
    primary_tool: str
    summary: str
    notes: str
    device_classes: list[str]
    evidence_items: list[str]
    agencies: list[str]
    device_classes_csv: str
    evidence_items_csv: str
    agencies_csv: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _CustodyView:
    received_at: datetime | None
    received_at_str: str  # "" when received_at is None — avoids "None" in reports
    received_from: str
    delivery_method: str
    evidence_bag_ids: list[str]
    evidence_bag_ids_csv: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _CaseView:
    name: str
    reference: str
    created_at: datetime
    created_at_str: str
    updated_at: datetime
    updated_at_str: str
    path: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _SuggestionView:
    id: str
    action: str
    priority: str
    category: str
    expected_result: str
    rationale: str
    references: list[str]
    depends_on: list[str]
    completed: bool
    completed_at: datetime | None
    completed_at_str: str


@dataclass(frozen=True, slots=True, kw_only=True)
class _SuggestionsView:
    total: int
    completed_count: int
    required_count: int
    scope_summary: str
    playbooks: list[str]
    has_data: bool
    completed: list[_SuggestionView]
    open: list[_SuggestionView]
    all: list[_SuggestionView] = field(default_factory=list)


@dataclass(frozen=True, slots=True, kw_only=True)
class _SessionView:
    slug: str
    name: str
    started_at: datetime
    ended_at: datetime | None
    started_at_str: str
    ended_at_str: str
    event_count: int
    step_count: int
    path: str
    is_in_progress: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class _SessionsView:
    count: int
    all: list[_SessionView]
    completed: list[_SessionView]
    in_progress: list[_SessionView]


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportContext:
    """Top-level template namespace.

    Built once via :func:`build_context`; passed straight to docxtpl
    as the render context. Field names are deliberately stable —
    they're the contract templates author against.
    """

    generated_at: str
    generated_at_iso: str
    case: _CaseView
    examiner: _ExaminerView
    scope: _ScopeView
    custody: _CustodyView
    suggestions: _SuggestionsView
    sessions: _SessionsView
    caseforge_version: str

    def as_template_dict(self) -> dict[str, Any]:
        """Flatten to the dict shape ``DocxTemplate.render`` expects.

        ``docxtpl`` accepts dataclass attribute access via Jinja2's
        attribute lookup, but flattening to dicts keeps the rendering
        path independent of dataclass internals (slots, frozen flag)
        which historically have surprised Jinja sandboxes.
        """
        return {
            "generated_at": self.generated_at,
            "generated_at_iso": self.generated_at_iso,
            "case": _to_dict(self.case),
            "examiner": _to_dict(self.examiner),
            "scope": _to_dict(self.scope),
            "custody": _to_dict(self.custody),
            "suggestions": _suggestions_to_dict(self.suggestions),
            "sessions": _sessions_to_dict(self.sessions),
            "caseforge_version": self.caseforge_version,
        }


def build_context(case_dir: Path, *, now: datetime | None = None) -> ReportContext:
    """Assemble a :class:`ReportContext` from on-disk case data.

    ``case.json`` is required; suggestions and Inscription sessions
    are optional — when absent they render as empty collections so
    templates can guard with ``{% if suggestions.has_data %}`` /
    ``{% if sessions.count %}``.
    """
    case = read_case(case_dir)
    suggestions = read_suggestions(case_dir)
    sessions = list_inscription_sessions(case_dir)
    timestamp = now or datetime.now(UTC)

    return ReportContext(
        generated_at=timestamp.strftime(_DEFAULT_TS_FORMAT),
        generated_at_iso=timestamp.isoformat(),
        case=_case_view(case, case_dir),
        examiner=_examiner_view(case),
        scope=_scope_view(case),
        custody=_custody_view(case),
        suggestions=_suggestions_view(suggestions),
        sessions=_sessions_view(sessions),
        caseforge_version=__version__,
    )


# -------------------------------------------------------- view builders


def _case_view(case: Case, case_dir: Path) -> _CaseView:
    return _CaseView(
        name=case.name,
        reference=case.case_reference,
        created_at=case.created_at,
        created_at_str=case.created_at.strftime(_DEFAULT_TS_FORMAT),
        updated_at=case.updated_at,
        updated_at_str=case.updated_at.strftime(_DEFAULT_TS_FORMAT),
        path=str(case_dir.resolve()),
    )


def _examiner_view(case: Case) -> _ExaminerView:
    e = case.examiner
    return _ExaminerView(
        name=e.name,
        organisation=e.organisation,
        badge_id=e.badge_id,
        is_present=e.is_present,
    )


def _scope_view(case: Case) -> _ScopeView:
    s = case.scope
    return _ScopeView(
        exam_type=s.exam_type,
        primary_tool=s.primary_tool,
        summary=s.summary,
        notes=s.notes,
        device_classes=list(s.device_classes),
        evidence_items=list(s.evidence_items),
        agencies=list(s.agencies),
        device_classes_csv=", ".join(s.device_classes),
        evidence_items_csv=", ".join(s.evidence_items),
        agencies_csv=", ".join(s.agencies),
    )


def _custody_view(case: Case) -> _CustodyView:
    c = case.custody
    received_at_str = (
        c.received_at.strftime(_DEFAULT_TS_FORMAT) if c.received_at is not None else ""
    )
    return _CustodyView(
        received_at=c.received_at,
        received_at_str=received_at_str,
        received_from=c.received_from,
        delivery_method=c.delivery_method,
        evidence_bag_ids=list(c.evidence_bag_ids),
        evidence_bag_ids_csv=", ".join(c.evidence_bag_ids),
    )


def _suggestions_view(doc: CaseguideDocument | None) -> _SuggestionsView:
    if doc is None:
        return _SuggestionsView(
            total=0,
            completed_count=0,
            required_count=0,
            scope_summary="",
            playbooks=[],
            has_data=False,
            completed=[],
            open=[],
            all=[],
        )
    rendered = [_suggestion_view(s) for s in doc.suggestions]
    completed = [s for s in rendered if s.completed]
    open_ = [s for s in rendered if not s.completed]
    return _SuggestionsView(
        total=len(rendered),
        completed_count=len(completed),
        required_count=sum(1 for s in rendered if s.priority == "required"),
        scope_summary=doc.scope_summary,
        playbooks=list(doc.playbooks),
        has_data=True,
        completed=completed,
        open=open_,
        all=rendered,
    )


def _suggestion_view(s: CaseguideSuggestion) -> _SuggestionView:
    completed_at_str = (
        s.completed_at.strftime(_DEFAULT_TS_FORMAT) if s.completed_at is not None else ""
    )
    return _SuggestionView(
        id=s.id,
        action=s.action,
        priority=s.priority,
        category=s.category,
        expected_result=s.expected_result,
        rationale=s.rationale,
        references=list(s.references),
        depends_on=list(s.depends_on),
        completed=s.completed,
        completed_at=s.completed_at,
        completed_at_str=completed_at_str,
    )


def _sessions_view(sessions: list[InscriptionSession]) -> _SessionsView:
    rendered = [_session_view(s) for s in sessions]
    return _SessionsView(
        count=len(rendered),
        all=rendered,
        completed=[s for s in rendered if not s.is_in_progress],
        in_progress=[s for s in rendered if s.is_in_progress],
    )


def _session_view(s: InscriptionSession) -> _SessionView:
    return _SessionView(
        slug=s.slug,
        name=s.name,
        started_at=s.started_at,
        ended_at=s.ended_at,
        started_at_str=s.started_at.strftime(_DEFAULT_TS_FORMAT),
        ended_at_str=s.ended_at.strftime(_DEFAULT_TS_FORMAT) if s.ended_at else "",
        event_count=s.event_count,
        step_count=s.step_count,
        path=s.path,
        is_in_progress=s.is_in_progress,
    )


# --------------------------------------------------------- dict flatteners


def _to_dict(view: Any) -> dict[str, Any]:
    """Flatten a frozen-slots dataclass view to a plain dict.

    ``dataclasses.asdict`` recurses into nested dataclasses, which we
    don't want here — the parent flattener handles the nesting itself
    so each level can be inspected and serialised on its own terms.
    """
    return {f.name: getattr(view, f.name) for f in fields(view)}


def _suggestions_to_dict(view: _SuggestionsView) -> dict[str, Any]:
    return {
        "total": view.total,
        "completed_count": view.completed_count,
        "required_count": view.required_count,
        "scope_summary": view.scope_summary,
        "playbooks": list(view.playbooks),
        "has_data": view.has_data,
        "completed": [_to_dict(s) for s in view.completed],
        "open": [_to_dict(s) for s in view.open],
        "all": [_to_dict(s) for s in view.all],
    }


def _sessions_to_dict(view: _SessionsView) -> dict[str, Any]:
    return {
        "count": view.count,
        "all": [_to_dict(s) for s in view.all],
        "completed": [_to_dict(s) for s in view.completed],
        "in_progress": [_to_dict(s) for s in view.in_progress],
    }
