"""Prompt construction and response parsing for the LLM rewriter.

The model is asked to produce a strict-JSON object with one key,
``"steps"``, whose value is an array of
``{"action": ..., "result": ..., "source_event_ids": [...]}`` entries.
``parse_response`` tolerates minor deviations — markdown code fences,
a leading ``"json"`` language tag — and validates that every referenced
event id exists before returning.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from inscription.llm.client import LLMResponseError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from inscription.model import DraftStep, RawEvent, ResolvedElement

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are an expert technical writer turning a Windows desktop workflow
into a forensic-style procedural log. The output goes into a three-column
notes table — Time/Date, Action, Result — so each step is split into
what the examiner DID and what they OBSERVED.

Rules:
- "action" is one imperative sentence starting with an action verb
  (Open, Click, Type, Save, Press, Choose, Select, etc.) describing what
  the examiner did.
- "result" is what was observed or produced afterwards — a short
  factual statement ("Hash verified", "Processing completed in 1h 23m",
  "No evidentiary results found"). Leave "result" as an empty string
  when nothing observable happened (most pure UI clicks).
- Merge related consecutive events into one step when they describe a
  single user intent (e.g. clicking File then Save As then naming the
  file → action "Save the file as <name>.txt using File → Save As").
- Drop events that don't advance the procedure: window-focus events
  that are side effects of a click, taskbar clicks whose destination
  is visible from the next event, clicks on the recording tool itself.
- **Never invent actions that aren't in the input timeline.** Only
  describe scrolling if a "scroll" event is present; only describe
  switching tabs if you see distinct click events on different tabs;
  only describe typing if a key_press or text event is present. If
  several minutes pass between two events with no events in between,
  do not fabricate "navigated through tabs" or "scrolled around" or
  "explored the page" — just produce the step for the next event.
- Never invent results. If the timeline does not show an outcome,
  leave "result" empty. Do not say "verified successfully" or
  "completed without errors" unless the input contains evidence.
- Preserve the original event IDs — every step's "source_event_ids"
  must contain at least one id from the input timeline.
- Never invent details (filenames, button names, URLs) not present in
  the input.
- Keep any steps marked "manual_edit" in the existing draft verbatim;
  their text is already approved by the user.

Output format: a single JSON object with one key, "steps". No prose
before or after the JSON. Each step has:
  - "action": string. One imperative sentence.
  - "result": string. May be empty.
  - "source_event_ids": non-empty array of integers.

Return at most as many steps as input events.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class RewrittenStep:
    """One step parsed out of the LLM's JSON response."""

    action: str
    result: str
    source_event_ids: tuple[int, ...]


def build_user_prompt(
    *,
    session_name: str,
    events: Iterable[RawEvent],
    resolved_by_id: dict[int, ResolvedElement],
    existing_steps: Iterable[DraftStep],
) -> str:
    """Build the user message: session metadata + events + manual edits."""
    event_payload = [_event_to_dict(e, resolved_by_id) for e in events]
    manual = [
        {
            "action": s.action,
            "result": s.result,
            "source_event_ids": list(s.source_event_ids),
        }
        for s in existing_steps
        if s.manual_edit and not s.suppressed
    ]
    payload = {
        "session": session_name,
        "events": event_payload,
        "manual_edits": manual,
    }
    return (
        "Session workflow timeline follows.\n\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False)}\n\n"
        "Produce the rewritten guide as specified."
    )


def parse_response(text: str, *, valid_event_ids: set[int]) -> list[RewrittenStep]:
    """Parse the assistant's JSON content into :class:`RewrittenStep` list.

    Tolerates markdown code fences around the JSON. Drops any step whose
    ``source_event_ids`` references no real event — the alternative is
    silently inventing links back into the raw layer, which would break
    the guide's provenance.
    """
    body = _strip_code_fences(text.strip())
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        msg = f"LLM content was not valid JSON: {body[:200]!r}"
        raise LLMResponseError(msg) from exc

    if not isinstance(data, dict) or "steps" not in data:
        msg = f"LLM content missing top-level 'steps' key: {data!r}"
        raise LLMResponseError(msg)

    raw_steps = data["steps"]
    if not isinstance(raw_steps, list):
        msg = f"LLM 'steps' must be an array, got {type(raw_steps).__name__}"
        raise LLMResponseError(msg)

    out: list[RewrittenStep] = []
    for i, item in enumerate(raw_steps):
        step = _coerce_step(item, index=i, valid_event_ids=valid_event_ids)
        if step is not None:
            out.append(step)
    if not out:
        msg = "LLM returned zero usable steps"
        raise LLMResponseError(msg)
    return out


# -------------------------------------------------------------- internals


def _event_to_dict(
    event: RawEvent, resolved_by_id: dict[int, ResolvedElement]
) -> dict[str, object]:
    resolved: ResolvedElement | None = None
    if event.resolved_element_id is not None:
        resolved = resolved_by_id.get(event.resolved_element_id)
    payload: dict[str, object] = {
        "id": event.id,
        "kind": event.kind.value,
    }
    if event.button:
        payload["button"] = event.button
    if event.key:
        payload["key"] = event.key
    if event.text:
        payload["text"] = event.text
    if event.window_title:
        payload["window_title"] = event.window_title
    if event.process_name:
        payload["process_name"] = event.process_name
    if resolved is not None:
        r: dict[str, object] = {}
        if resolved.name:
            r["name"] = resolved.name
        if resolved.control_type:
            r["control_type"] = resolved.control_type
        if resolved.owner_process_name:
            r["owner_process"] = resolved.owner_process_name
        if r:
            payload["element"] = r
    return payload


def _strip_code_fences(text: str) -> str:
    if not text.startswith("```"):
        return text
    # ```json\n...\n```  or  ```\n...\n```
    first_nl = text.find("\n")
    if first_nl == -1:
        return text
    inner = text[first_nl + 1 :]
    if inner.endswith("```"):
        inner = inner[:-3]
    return inner.strip()


def _coerce_step(item: object, *, index: int, valid_event_ids: set[int]) -> RewrittenStep | None:
    if not isinstance(item, dict):
        logger.warning("LLM step %d is not an object: %r", index, item)
        return None
    # Tolerate the legacy single-"text" shape so a stale model output
    # still produces something usable; we treat it as an action with no
    # observed result.
    action = item.get("action")
    if action is None:
        action = item.get("text")
    result = item.get("result", "")
    ids = item.get("source_event_ids")
    if not isinstance(action, str) or not action.strip():
        logger.warning("LLM step %d missing action: %r", index, item)
        return None
    if not isinstance(result, str):
        logger.warning("LLM step %d non-string result; coercing: %r", index, result)
        result = ""
    if not isinstance(ids, list) or not ids:
        logger.warning("LLM step %d missing source_event_ids: %r", index, item)
        return None

    coerced_ids: list[int] = []
    for raw_id in ids:
        try:
            value = int(raw_id)
        except (TypeError, ValueError):
            logger.debug("LLM step %d: non-int id %r", index, raw_id)
            continue
        if value in valid_event_ids:
            coerced_ids.append(value)
    if not coerced_ids:
        logger.warning("LLM step %d references no known event ids: %r", index, ids)
        return None
    return RewrittenStep(
        action=action.strip(),
        result=result.strip(),
        source_event_ids=tuple(coerced_ids),
    )
