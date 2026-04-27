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

#: Cap on the body excerpt we surface to the user when JSON parsing
#: fails. Long enough to identify the kind of failure (markdown
#: preamble vs. pure prose vs. truncated reply), short enough to fit
#: in a Qt message box without scrolling.
_ERROR_SNIPPET_LIMIT = 200


SYSTEM_PROMPT = """\
OUTPUT ONLY a JSON object. No prose, no markdown, no explanation.
Start with { and end with }. Nothing before or after.

Example (copy this structure exactly):
{"steps":[{"action":"Open the case folder.","result":"","source_event_ids":[1]}]}

Task: convert a Windows workflow event timeline into a forensic notes table \
(Action + Result columns).

action rules:
- One imperative sentence starting with a verb: Open, Click, Type, Save, \
Press, Select, etc.
- Merge consecutive events that form one user intent (File → Save As → \
filename → Enter = one "Save the file as <name> using File → Save As" step).
- Drop noise: window-focus events caused by a nearby click; clicks on the \
recording tool itself; taskbar transitions whose target is shown in the next \
event.
- Only describe scrolling if a scroll event is present; only describe \
tab-switching if distinct tab-click events exist; only describe typing if a \
key_press or text event is present. Never invent actions not in the timeline.

result rules:
- What the examiner observed or the software produced, e.g. "Hash verified", \
"Processing completed in 1h 23m". Use "" when nothing observable happened.
- Never fabricate results. No "completed successfully" unless the input shows \
evidence of it.

source_event_ids rules:
- Non-empty array of integer event ids from the input. Never invent ids.

manual_edit steps:
- Reproduce them verbatim. Do not rewrite approved text.
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
        "Reply with the JSON object only. Start with {, end with }, nothing else."
    )


def parse_response(text: str, *, valid_event_ids: set[int]) -> list[RewrittenStep]:
    """Parse the assistant's JSON content into :class:`RewrittenStep` list.

    Tolerates markdown code fences around the JSON, and tolerates
    smaller models that prepend a sentence of commentary before the
    JSON object — extracts the first balanced ``{...}`` block as a
    fallback. Drops any step whose ``source_event_ids`` references no
    real event — the alternative is silently inventing links back
    into the raw layer, which would break the guide's provenance.
    """
    body = _strip_code_fences(text.strip())
    data = _parse_json_lenient(body)
    if data is None:
        snippet = body[:_ERROR_SNIPPET_LIMIT] + (
            "…" if len(body) > _ERROR_SNIPPET_LIMIT else ""
        )
        msg = (
            "LLM did not return JSON. The configured model may be "
            "ignoring the json_object response_format directive — try "
            "a stronger / instruction-tuned model in Edit → Settings → LLM. "
            f"First chars of reply: {snippet!r}"
        )
        raise LLMResponseError(msg)

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


def _parse_json_lenient(body: str) -> object | None:
    """Try strict JSON first; fall back to extracting the first ``{...}``.

    Smaller / weakly instruction-tuned models routinely prepend a
    sentence of commentary before the JSON object even when asked
    not to ("Sure! Here's the JSON: { ... }"). Extracting the first
    balanced brace block recovers those cases without inventing
    structure that wasn't present. Returns ``None`` when neither
    strategy yields valid JSON.
    """
    try:
        parsed: object = json.loads(body)
    except json.JSONDecodeError:
        pass
    else:
        return parsed
    candidate = _extract_first_json_object(body)
    if candidate is None:
        return None
    try:
        recovered: object = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return recovered


def _extract_first_json_object(body: str) -> str | None:
    """Return the first balanced ``{...}`` substring in ``body``, or None.

    Walks the string tracking brace depth, ignoring braces inside
    string literals (with escape-aware handling). Stops at the first
    well-formed object and returns its source text.
    """
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(body):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                return body[start : i + 1]
    return None


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
