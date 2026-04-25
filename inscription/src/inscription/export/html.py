"""HTML exporter.

Produces a self-contained ``.html`` file in the session's ``exports/``
directory. Screenshots are staged into ``exports/assets/`` so the output
folder is portable on its own.

For each step with a resolved UIA element, the staged image is a
**crop around the clicked element with a click ring drawn on it** — the
raw layer (``screenshots/event-*.png``) remains untouched, so provenance
is preserved; the exporter simply renders a tighter, annotated variant
for human consumption. Steps without a resolved bounding rect fall back
to the full screenshot.
"""

from __future__ import annotations

import html
import logging
import shutil
from typing import TYPE_CHECKING

from inscription.model import ExportDocument, utcnow
from inscription.render import crop_highlight

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
  --muted: #666;
  --rule: #e5e5e5;
  --accent: #1f6feb;
}
@media (prefers-color-scheme: dark) {
  :root { --fg: #f3f3f3; --muted: #aaa; --rule: #333; --accent: #58a6ff; }
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: var(--fg);
  max-width: 960px;
  margin: 2rem auto;
  padding: 0 1.5rem;
  line-height: 1.55;
}
header { border-bottom: 1px solid var(--rule); padding-bottom: 1rem; margin-bottom: 2rem; }
header h1 { margin: 0 0 .25rem 0; }
header .meta { color: var(--muted); font-size: .9rem; }
ol.steps { list-style: none; padding: 0; counter-reset: step; }
ol.steps > li {
  counter-increment: step;
  display: grid;
  grid-template-columns: 2.5rem 1fr;
  gap: .75rem;
  padding: 1.25rem 0;
  border-bottom: 1px solid var(--rule);
}
ol.steps > li::before {
  content: counter(step);
  font-weight: 600;
  color: var(--accent);
  font-variant-numeric: tabular-nums;
}
.step-time {
  display: inline-block;
  margin-bottom: .35rem;
  color: var(--muted);
  font-size: .8rem;
  font-variant-numeric: tabular-nums;
  letter-spacing: .03em;
}
.step-action { margin: 0 0 .35rem 0; font-weight: 500; }
.step-result {
  margin: 0 0 .5rem 0;
  padding: .25rem 0 .25rem .65rem;
  border-left: 2px solid var(--accent);
  color: var(--muted);
}
.step-shot img {
  max-width: 100%;
  border: 1px solid var(--rule);
  border-radius: 4px;
}
footer { color: var(--muted); font-size: .8rem; margin-top: 2rem; }
"""


def export_html(
    repository: SessionRepository,
    *,
    destination: Path | None = None,
) -> ExportDocument:
    """Render the session as HTML."""
    session = repository.session
    steps = repository.list_steps()
    screenshots = {s.id: s for s in repository.list_screenshots() if s.id is not None}
    events_by_id: dict[int, RawEvent] = {
        e.id: e for e in repository.list_events() if e.id is not None
    }

    if destination is None:
        destination = session.exports_dir / f"{session.root.name}.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    assets_dir = destination.parent / "assets"
    assets_dir.mkdir(exist_ok=True)

    # Small per-session cache: one resolved element can back many events.
    element_cache: dict[int, ResolvedElement | None] = {}

    def resolve(event: RawEvent) -> ResolvedElement | None:
        eid = event.resolved_element_id
        if eid is None:
            return None
        if eid not in element_cache:
            element_cache[eid] = repository.get_resolved_element(eid)
        return element_cache[eid]

    body_parts = [_render_header(session)]
    body_parts.append('<ol class="steps">')
    for step in steps:
        body_parts.append(
            _render_step(
                step=step,
                screenshots=screenshots,
                events_by_id=events_by_id,
                resolver=resolve,
                session_root=session.root,
                assets_dir=assets_dir,
            )
        )
    body_parts.append("</ol>")
    body_parts.append(_render_footer(session))

    html_doc = _wrap(title=session.info.name, body="\n".join(body_parts))
    destination.write_text(html_doc, encoding="utf-8")
    logger.info("Exported %s to %s", session.info.name, destination)

    return ExportDocument(
        session_name=session.info.name,
        format="html",
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


def _render_header(session: Session) -> str:
    info = session.info
    started = info.started_at.strftime("%Y-%m-%d %H:%M")
    ended = info.ended_at.strftime("%Y-%m-%d %H:%M") if info.ended_at else "in progress"
    return (
        "<header>\n"
        f"<h1>{html.escape(info.name)}</h1>\n"
        f'<div class="meta">Recorded {html.escape(started)} &ndash; {html.escape(ended)}</div>\n'
        "</header>\n"
    )


def _render_footer(session: Session) -> str:
    version = session.info.recorder_version or "unknown"
    return f"<footer>\nGenerated by Inscription (recorder {html.escape(version)}).\n</footer>\n"


def _primary_event(step: DraftStep, events_by_id: dict[int, RawEvent]) -> RawEvent | None:
    """Pick the source event whose screenshot the step is displaying.

    Most steps have exactly one source event, so this is usually trivial.
    When a step was merged from several (rapid clicks on the same target),
    we prefer the event that contributed the screenshot — that's the one
    whose click point the crop needs.
    """
    for eid in step.source_event_ids:
        event = events_by_id.get(eid)
        if event is None:
            continue
        if step.screenshot_id is not None and event.screenshot_id == step.screenshot_id:
            return event
    # Fall back to the first resolvable source event.
    for eid in step.source_event_ids:
        event = events_by_id.get(eid)
        if event is not None:
            return event
    return None


def _render_step(
    *,
    step: DraftStep,
    screenshots: dict[int, ScreenshotArtifact],
    events_by_id: dict[int, RawEvent],
    resolver: Callable[[RawEvent], ResolvedElement | None],
    session_root: Path,
    assets_dir: Path,
) -> str:
    primary = _primary_event(step, events_by_id)
    action_text = html.escape(step.action).replace("\n", "<br>")
    parts = ["<li>", '<div class="step-body">']
    if primary is not None:
        ts = html.escape(primary.occurred_at.astimezone().strftime("%H:%M:%S"))
        parts.append(f'<div class="step-time">{ts}</div>')
    parts.append(f'<p class="step-action">{action_text}</p>')
    if step.result.strip():
        result_text = html.escape(step.result).replace("\n", "<br>")
        parts.append(f'<p class="step-result">{result_text}</p>')
    shot = screenshots.get(step.screenshot_id) if step.screenshot_id else None
    if shot is not None:
        element = resolver(primary) if primary else None
        src = _stage_step_asset(
            step=step,
            shot=shot,
            primary_event=primary,
            element=element,
            session_root=session_root,
            assets_dir=assets_dir,
        )
        alt = html.escape(step.action)[:120]
        parts.append(f'<div class="step-shot"><img src="{html.escape(src)}" alt="{alt}"></div>')
    parts.append("</div>")
    parts.append("</li>")
    return "\n".join(parts)


def _stage_step_asset(
    *,
    step: DraftStep,
    shot: ScreenshotArtifact,
    primary_event: RawEvent | None,
    element: ResolvedElement | None,
    session_root: Path,
    assets_dir: Path,
) -> str:
    """Write a crop+marker PNG for this step and return the relative URL.

    Falls back to a plain copy of the raw screenshot when no bounding rect
    is available.
    """
    src_path = session_root / shot.relative_path
    step_id = step.id if step.id is not None else step.sequence
    target = assets_dir / f"step-{step_id:05d}.png"

    try:
        raw_bytes = src_path.read_bytes()
    except OSError as exc:
        logger.warning("Could not read source screenshot %s: %s", src_path, exc)
        return shot.relative_path

    rect = element.bounding_rect if element is not None else None
    click = (
        (primary_event.x, primary_event.y)
        if primary_event is not None and primary_event.x is not None and primary_event.y is not None
        else None
    )

    if rect is None:
        # No UIA target — stage the raw PNG unchanged.
        try:
            shutil.copyfile(src_path, target)
        except OSError as exc:
            logger.warning("Could not stage asset %s: %s", src_path, exc)
            return shot.relative_path
        return f"assets/{target.name}"

    rendered = crop_highlight(raw_bytes, bounding_rect=rect, click_point=click)
    target.write_bytes(rendered)
    return f"assets/{target.name}"
