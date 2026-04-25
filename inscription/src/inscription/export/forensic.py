"""Forensic-notes exporter.

Produces a self-contained HTML file laid out the way examiner notes
look on paper: a three-column **Time/Date · Action · Result** table
with the date carried only on the first row of each calendar day, a
header block carrying the case / examiner / session metadata, and a
footer for sign-off.

Screenshots, when present, are inlined into the Action cell underneath
the action text. The same crop+highlight rendering used by the regular
HTML export is reused so the output is consistent across formats.
"""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from inscription.export.html import _primary_event, _stage_step_asset
from inscription.model import ExportDocument, utcnow

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from inscription.model import (
        DraftStep,
        RawEvent,
        ResolvedElement,
        ScreenshotArtifact,
        Session,
    )
    from inscription.storage import SessionRepository

logger = logging.getLogger(__name__)


_CSS = """
:root {
  color-scheme: light dark;
  --fg: #111;
  --muted: #6b6b6b;
  --rule: #d8d8d8;
  --rule-strong: #999;
  --accent: #1f6feb;
  --header-bg: #f6f6f6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fg: #ececec; --muted: #a8a8a8; --rule: #3a3a3a; --rule-strong: #555;
    --accent: #58a6ff; --header-bg: #232323;
  }
}
@page { margin: 1.5cm; }
body {
  font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "SF Pro Text",
               Roboto, sans-serif;
  color: var(--fg);
  max-width: 1100px;
  margin: 1.5rem auto;
  padding: 0 1.25rem;
  line-height: 1.5;
}
header.case-header {
  border: 1px solid var(--rule-strong);
  background: var(--header-bg);
  padding: .9rem 1.1rem;
  margin-bottom: 1.2rem;
}
header.case-header h1 {
  margin: 0 0 .35rem 0;
  font-size: 1.4rem;
  letter-spacing: .01em;
}
header.case-header dl {
  display: grid;
  grid-template-columns: max-content 1fr max-content 1fr;
  gap: .25rem 1rem;
  margin: 0;
  font-size: .9rem;
}
header.case-header dt { color: var(--muted); }
header.case-header dd { margin: 0; }
table.notes {
  border-collapse: collapse;
  width: 100%;
  font-size: .92rem;
  table-layout: fixed;
}
table.notes thead th {
  text-align: left;
  background: var(--header-bg);
  border: 1px solid var(--rule-strong);
  padding: .55rem .7rem;
  font-weight: 600;
  font-size: .85rem;
  letter-spacing: .03em;
  text-transform: uppercase;
  color: var(--muted);
}
table.notes thead th:nth-child(1) { width: 14%; }
table.notes thead th:nth-child(2) { width: 47%; }
table.notes thead th:nth-child(3) { width: 39%; }
table.notes td {
  border: 1px solid var(--rule);
  padding: .65rem .75rem;
  vertical-align: top;
  word-wrap: break-word;
}
table.notes td.time {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: var(--muted);
}
table.notes td.time .date {
  display: block;
  color: var(--fg);
  font-weight: 600;
  margin-bottom: .15rem;
}
table.notes tr.evidentiary td { background: rgba(255, 200, 0, 0.08); }
table.notes tr.evidentiary td:first-child {
  border-left: 3px solid #c79100;
}
.action-text { margin: 0 0 .5rem 0; }
.action-shot {
  margin: .35rem 0 0 0;
  border: 1px solid var(--rule);
  border-radius: 3px;
  max-width: 100%;
}
.result-text { margin: 0; white-space: pre-wrap; }
.result-empty { color: var(--muted); font-style: italic; }
footer.sign-off {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2rem;
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--rule);
  color: var(--muted);
  font-size: .85rem;
}
footer.sign-off .signature {
  border-top: 1px solid var(--rule-strong);
  margin-top: 2.2rem;
  padding-top: .25rem;
  color: var(--fg);
}
"""


def export_forensic_notes(
    repository: SessionRepository,
    *,
    destination: Path | None = None,
    examiner: str | None = None,
    case_reference: str | None = None,
) -> ExportDocument:
    """Render the session as a forensic-notes HTML document.

    ``examiner`` and ``case_reference`` are optional metadata for the
    header block. When omitted, the rendered cells just show ``—``.
    """
    session = repository.session
    steps = repository.list_steps()
    screenshots = {s.id: s for s in repository.list_screenshots() if s.id is not None}
    events_by_id: dict[int, RawEvent] = {
        e.id: e for e in repository.list_events() if e.id is not None
    }

    if destination is None:
        destination = session.exports_dir / f"{session.root.name}-notes.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    assets_dir = destination.parent / f"{destination.stem}-assets"
    assets_dir.mkdir(exist_ok=True)

    element_cache: dict[int, ResolvedElement | None] = {}

    def resolve(event: RawEvent) -> ResolvedElement | None:
        eid = event.resolved_element_id
        if eid is None:
            return None
        if eid not in element_cache:
            element_cache[eid] = repository.get_resolved_element(eid)
        return element_cache[eid]

    body_parts = [
        _render_case_header(
            session=session,
            examiner=examiner,
            case_reference=case_reference,
        ),
        '<table class="notes">',
        "<thead><tr><th>Time/Date</th><th>Action</th><th>Result</th></tr></thead>",
        "<tbody>",
    ]
    last_date_label: str | None = None
    for step in steps:
        row, last_date_label = _render_row(
            step=step,
            screenshots=screenshots,
            events_by_id=events_by_id,
            resolver=resolve,
            session_root=session.root,
            assets_dir=assets_dir,
            assets_dirname=assets_dir.name,
            last_date_label=last_date_label,
        )
        body_parts.append(row)
    body_parts.append("</tbody></table>")
    body_parts.append(_render_sign_off(session=session, examiner=examiner))

    html_doc = _wrap(title=f"{session.info.name} — Forensic notes", body="\n".join(body_parts))
    destination.write_text(html_doc, encoding="utf-8")
    logger.info("Exported forensic notes for %s to %s", session.info.name, destination)

    return ExportDocument(
        session_name=session.info.name,
        format="forensic-notes",
        path=destination,
        generated_at=utcnow(),
    )


# -------------------------------------------------------------- rendering


def _wrap(*, title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _render_case_header(
    *,
    session: Session,
    examiner: str | None,
    case_reference: str | None,
) -> str:
    info = session.info
    started = info.started_at.astimezone().strftime("%d %B %Y · %H:%M")
    ended = (
        info.ended_at.astimezone().strftime("%d %B %Y · %H:%M") if info.ended_at else "in progress"
    )
    return (
        '<header class="case-header">\n'
        f"<h1>{html.escape(info.name)}</h1>\n"
        "<dl>\n"
        f"<dt>Examiner</dt><dd>{html.escape(examiner or '—')}</dd>\n"
        f"<dt>Case reference</dt><dd>{html.escape(case_reference or '—')}</dd>\n"
        f"<dt>Started</dt><dd>{html.escape(started)}</dd>\n"
        f"<dt>Ended</dt><dd>{html.escape(ended)}</dd>\n"
        "</dl>\n"
        "</header>\n"
    )


def _render_row(
    *,
    step: DraftStep,
    screenshots: dict[int, ScreenshotArtifact],
    events_by_id: dict[int, RawEvent],
    resolver: Callable[[RawEvent], ResolvedElement | None],
    session_root: Path,
    assets_dir: Path,
    assets_dirname: str,
    last_date_label: str | None,
) -> tuple[str, str | None]:
    """Render one ``<tr>`` row plus the updated date-rollover state."""
    primary = _primary_event(step, events_by_id)
    when = primary.occurred_at.astimezone() if primary is not None else None
    date_label = when.strftime("%d %b %Y") if when is not None else None
    time_label = when.strftime("%H:%M:%S") if when is not None else "—"

    new_date: str | None = last_date_label
    if date_label and date_label != last_date_label:
        time_cell = (
            f'<td class="time"><span class="date">{html.escape(date_label)}</span>'
            f"{html.escape(time_label)}</td>"
        )
        new_date = date_label
    else:
        time_cell = f'<td class="time">{html.escape(time_label)}</td>'

    action_cell = _render_action_cell(
        step=step,
        screenshots=screenshots,
        primary_event=primary,
        resolver=resolver,
        session_root=session_root,
        assets_dir=assets_dir,
        assets_dirname=assets_dirname,
    )
    result_cell = _render_result_cell(step)

    classes = "evidentiary" if step.evidentiary else ""
    open_tr = f'<tr class="{classes}">' if classes else "<tr>"
    return (
        f"{open_tr}{time_cell}{action_cell}{result_cell}</tr>",
        new_date,
    )


def _render_action_cell(
    *,
    step: DraftStep,
    screenshots: dict[int, ScreenshotArtifact],
    primary_event: RawEvent | None,
    resolver: Callable[[RawEvent], ResolvedElement | None],
    session_root: Path,
    assets_dir: Path,
    assets_dirname: str,
) -> str:
    text = html.escape(step.action).replace("\n", "<br>") or "<em>(empty)</em>"
    parts = [f'<p class="action-text">{text}</p>']
    shot = screenshots.get(step.screenshot_id) if step.screenshot_id else None
    if shot is not None:
        element = resolver(primary_event) if primary_event else None
        rel = _stage_step_asset(
            step=step,
            shot=shot,
            primary_event=primary_event,
            element=element,
            session_root=session_root,
            assets_dir=assets_dir,
        )
        # _stage_step_asset returns a path relative to the destination
        # directory ("assets/foo.png") under the regular export layout,
        # but here our assets dir is named differently. Rewrite the
        # leading directory if it doesn't match.
        rel = _retarget_asset_url(rel, assets_dirname)
        alt = html.escape(step.action)[:120]
        parts.append(f'<img class="action-shot" src="{html.escape(rel)}" alt="{alt}">')
    return f"<td>{''.join(parts)}</td>"


def _render_result_cell(step: DraftStep) -> str:
    if step.result.strip():
        body = html.escape(step.result).replace("\n", "<br>")
        return f'<td><p class="result-text">{body}</p></td>'
    return '<td><p class="result-text result-empty">—</p></td>'


def _retarget_asset_url(rel: str, assets_dirname: str) -> str:
    """Swap the leading ``assets/`` segment for our differently-named dir."""
    if "/" not in rel:
        return rel
    _, _, tail = rel.partition("/")
    return f"{assets_dirname}/{tail}"


def _render_sign_off(*, session: Session, examiner: str | None) -> str:
    version = session.info.recorder_version or "unknown"
    return (
        '<footer class="sign-off">\n'
        "<div>\n"
        f"<div>Examiner: {html.escape(examiner or '')}</div>\n"
        '<div class="signature">Signature</div>\n'
        "</div>\n"
        "<div>\n"
        "<div>Date</div>\n"
        '<div class="signature">&nbsp;</div>\n'
        "</div>\n"
        "</footer>\n"
        f"<p style='font-size:.75rem;color:var(--muted);margin-top:1.5rem'>"
        f"Generated by Inscription (recorder {html.escape(version)}).</p>\n"
    )
