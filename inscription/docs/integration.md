# Inscription integration surface

Inscription is the capture / notes tool inside a planned multi-tool
forensic-exam suite:

| Tool         | Role                                                                         |
|--------------|------------------------------------------------------------------------------|
| **CaseForge**   | Builds the case folder, captures examiner identity / org / exam metadata. |
| **CaseGuide**   | Reads the customer scope, generates a best-practice action checklist that Inscription surfaces as suggestions. |
| **Inscription** | Records the examiner's actual desktop work into editable, exportable steps. |
| **Tool 3**      | Pulls evidentiary-marked notes from Inscription + admin data from CaseForge into the final report template. |

This document is the contract Inscription exposes to the other tools.
As long as the rules below hold, the rest of the suite can integrate
against Inscription's filesystem layout and SQLite schema directly —
no IPC, no shared library, no cross-process calls required.

---

## How the tools meet on the filesystem

The simple, robust integration model: the three tools share a **case
directory** on disk. CaseForge creates it; Inscription writes session
folders inside it; the report builder reads both.

```
<case-root>/
├── case.json                        ← written by CaseForge (admin metadata)
├── .caseguide/
│   └── suggestions.json             ← written by CaseGuide (recommended actions)
├── <session-slug>/                  ← one folder per Inscription session
│   ├── session.db                   ← SQLite — see "Schema" below
│   ├── manifest.json
│   ├── screenshots/
│   ├── exports/
│   └── .inscription/session.lock
├── <another-session-slug>/
└── …
```

### Launching Inscription against a case directory

Inscription accepts a `--case-dir` flag:

```powershell
python -m inscription --case-dir "C:\Cases\HSV-2026-0317"
```

This makes the case directory the workspace_root for the run — every
session created during the run lands inside it. The flag is **per-run**;
it does not persist to `config.ini`, so a fresh `python -m inscription`
without the flag uses the default workspace.

CaseForge should launch Inscription with this flag pointed at the case
directory it created. The window title will show `Case: <basename>`
while the flag is in effect.

### `case.json` (CaseForge owns this)

Inscription **does not write** to `case.json`. It does not currently
read it either, but is reserving the filename for the future "Case:
<name>" indicator to pull a friendlier title from. CaseForge is free
to define the schema for this file; Tool 3 reads it for admin metadata
when assembling the report.

### `.caseguide/suggestions.json` (CaseGuide owns this)

CaseGuide is the LLM-assisted exam coach: it reads the customer scope
out of `case.json`, picks the relevant procedural playbooks (NIST
SP 800-86, SWGDE, vendor-specific guides, internal SOPs, …), and
emits a tailored checklist of recommended actions. Inscription reads
this file **read-only** and surfaces the entries as a "Suggested next
actions" panel in the workspace; clicking a suggestion creates a
pre-filled draft step in the open session.

The contract:

- **Path**: `<case-root>/.caseguide/suggestions.json`. The hidden
  `.caseguide/` directory is reserved for this tool, the same way
  `.inscription/` is reserved for Inscription's per-session lock.
- **Inscription never writes** to this directory. CaseGuide may
  rewrite the file when scope changes (e.g. additional evidence
  found mid-exam); Inscription should re-read on file change.
- **Missing file is fine**. Inscription's suggestions panel is
  optional UI that hides itself when the file isn't present, so a
  case that runs without CaseGuide just looks like the regular
  Inscription experience.

#### File schema

```json
{
  "schema_version": 2,
  "generated_at": "2026-04-25T14:30:00+00:00",
  "scope_summary": "CSAM possession; Windows 11 laptop; full-disk image acquired.",
  "playbooks": ["NIST SP 800-86", "Internal SOP DF-CSAM-2024"],
  "suggestions": [
    {
      "id": "verify-image-hash",
      "category": "verification",
      "priority": "required",
      "action": "Verify the SHA-256 of the acquired E01 against the acquisition log.",
      "expected_result": "Hash matches the value recorded at acquisition time.",
      "rationale": "Establishes evidence integrity before any analysis touches the image.",
      "references": ["NIST SP 800-86 §5.2.2"],
      "depends_on": [],
      "completed": true,
      "completed_at": "2026-04-25T15:02:11+00:00"
    },
    {
      "id": "export-registry-hives",
      "category": "acquisition",
      "priority": "recommended",
      "action": "Export SYSTEM, SOFTWARE, NTUSER.DAT, and UsrClass.dat for offline analysis.",
      "expected_result": "Hives written to <case-root>/derived/registry/ with SHA-256 logged.",
      "rationale": "Registry artefacts feed timeline reconstruction and user-activity analysis.",
      "references": ["SWGDE Best Practices for Computer Forensic Acquisitions §4.7"],
      "depends_on": ["verify-image-hash"],
      "completed": false,
      "completed_at": null
    }
  ]
}
```

Field-by-field:

| Field | Type | Notes |
|-------|------|-------|
| `schema_version` | int | Bumps when this contract changes. v2 today (added per-suggestion `completed` / `completed_at`). |
| `generated_at` | ISO 8601 string | When CaseGuide produced this file. |
| `scope_summary` | string | Short, human-readable; shown as the panel header. |
| `playbooks` | string[] | Display-only; identifies which standards / SOPs the suggestions came from. |
| `suggestions[].id` | string | Stable across regenerations; used by completion tracking (see below). |
| `suggestions[].category` | string | Free-form bucket for grouping (`acquisition`, `verification`, `analysis`, `reporting`, …). |
| `suggestions[].priority` | enum | `required` \| `recommended` \| `optional`. Drives visual weight. |
| `suggestions[].action` | string | Imperative sentence — drops directly into the step's Action field. |
| `suggestions[].expected_result` | string | Optional placeholder for the step's Result field; the examiner overwrites with the real observation. |
| `suggestions[].rationale` | string | Optional one-liner the panel can show as a tooltip / expandable. |
| `suggestions[].references` | string[] | Optional citations to the standard / SOP / vendor doc. |
| `suggestions[].depends_on` | string[] | Optional list of other `id`s. Inscription may grey out a suggestion until its dependencies are completed. |
| `suggestions[].completed` | bool | True after the examiner marks the step done in CaseGuide; defaults to `false`. Both fields default to `false`/`null` on legacy v1 files. |
| `suggestions[].completed_at` | ISO 8601 string \| null | When the examiner marked it complete; `null` while incomplete. |

#### Completion tracking

CaseGuide owns completion state via the `completed` / `completed_at`
fields on each suggestion. The examiner ticks "Mark complete" in the
suggestions panel; the row dims and strikes through, and CaseGuide's
LLM Refine pass leaves completed entries untouched (so re-running
Refine doesn't undo verified work). Inscription, as a read-only
consumer, mirrors the same visual treatment — completed rows render
with strikeout text and a muted foreground colour.

#### Inscription's consumer

Inscription's panel lives in `inscription.ui.suggestions_panel` and
reads suggestions.json via `inscription.caseguide_link.read_suggestions`.
The reader is deliberately tolerant: missing file → `None` (panel
hides), unparseable file → logged + `None` (panel hides), unknown
fields → ignored (forward-compat with v3+).

A `QFileSystemWatcher` on `<case-root>/.caseguide/suggestions.json`
plus its parent directory means a refresh after CaseGuide's atomic
write (.tmp + rename) lands in Inscription within a Qt event-loop
tick — no polling.

Each row has a "Draft as step" button: clicking it appends a new
`DraftStep` to the open session (`action` ← suggestion.action,
`result` ← suggestion.expected_result, `manual_edit=True` so the
next Regenerate-Steps pass leaves it alone).

---

## Session folder layout

Each Inscription session is a self-contained directory. Every file
listed below is stable across sessions of the same `schema_version`
and the layout is the integration point Tool 3 reads against.

```
<session-slug>/
├── session.db          SQLite — see "Schema"
├── manifest.json       summary for the session picker (lightweight, regenerated on save)
├── screenshots/        PNGs referenced by raw_events
│   └── event-YYYYMMDDTHHMMSS-UUUUUU.png
├── exports/            generated guides (HTML today, MD/PDF/DOCX later)
│   └── assets/         per-step cropped + click-marked images
└── .inscription/
    └── session.lock    PID-based; ignore from outside
```

The slug is a filesystem-safe form of the session name (e.g.
`"Reset AWS password"` → `Reset-AWS-password`).

### `manifest.json`

```json
{
  "name": "Reset AWS password",
  "started_at": "2026-04-24T07:21:50.123456+00:00",
  "ended_at": "2026-04-24T07:24:11.987654+00:00",
  "event_count": 42,
  "step_count": 17,
  "schema_version": 4,
  "tags": []
}
```

Derived from the SQLite tables; safe to ignore if you're querying the
database directly. Useful for tools that want a quick listing without
opening every database.

---

## Schema (SQLite, version 4)

Inscription persists each session in a single `session.db`. The
on-disk schema is forward-only: every increment ships with an
ALTER-TABLE migration in `inscription.storage.schema.MIGRATIONS`, and
opening an older database transparently brings it up to the latest
version. Older sessions stay readable forever.

```sql
session_info       (one row, id = 1)
  id                 INTEGER PRIMARY KEY CHECK (id = 1)
  name               TEXT NOT NULL                 -- the session's display name
  started_at         TEXT NOT NULL                 -- ISO 8601 with offset
  ended_at           TEXT                          -- NULL until the session is closed
  recorder_version   TEXT NOT NULL DEFAULT ''      -- the version of Inscription that created it
  schema_version     INTEGER NOT NULL              -- = SCHEMA_VERSION at create time

raw_events         (the timeline; never edited after capture)
  id                   INTEGER PRIMARY KEY AUTOINCREMENT
  sequence             INTEGER NOT NULL             -- 1-based, monotonically increasing
  occurred_at          TEXT NOT NULL
  kind                 TEXT NOT NULL                -- "click" | "double_click" | "key_press" | "scroll" | "window_focus" | "marker"
  button               TEXT                         -- mouse button name when kind ∈ click/double_click
  x, y                 INTEGER                      -- screen coords when applicable
  key                  TEXT                         -- milestone key name when kind = key_press
  text                 TEXT                         -- free-form payload (marker note, scroll descriptor, …)
  window_title         TEXT                         -- foreground at capture time
  process_name         TEXT                         -- foreground process exe name
  screenshot_id        INTEGER REFERENCES screenshot_artifacts(id)
  resolved_element_id  INTEGER REFERENCES resolved_elements(id)

resolved_elements  (UIA metadata for clicks)
  id                  INTEGER PRIMARY KEY AUTOINCREMENT
  name                TEXT                          -- e.g. "Save"
  control_type        TEXT                          -- e.g. "Button"
  automation_id       TEXT
  class_name          TEXT
  role                TEXT
  confidence          REAL NOT NULL DEFAULT 0       -- 0..1 (UIA = 0.9, foreground-only fallback = 0.3)
  method              TEXT NOT NULL DEFAULT 'none'  -- "uia" | "foreground-only" | "none"
  bounding_rect       TEXT                          -- JSON [left, top, right, bottom] in screen px
  owner_process_name  TEXT                          -- the process that owns the element (taskbar/shell ≠ foreground)

screenshot_artifacts
  id              INTEGER PRIMARY KEY AUTOINCREMENT
  relative_path   TEXT NOT NULL UNIQUE              -- e.g. "screenshots/event-….png"
  captured_at     TEXT NOT NULL
  width, height   INTEGER NOT NULL
  sha256          TEXT NOT NULL DEFAULT ''          -- of the PNG bytes; verifiable
  highlight_rect  TEXT                              -- post-hoc user highlight, JSON

draft_steps        (the editable guide layer)
  id                INTEGER PRIMARY KEY AUTOINCREMENT
  sequence          INTEGER NOT NULL                -- display order (gaps are OK)
  action            TEXT NOT NULL DEFAULT ''        -- imperative: what the examiner did
  result            TEXT NOT NULL DEFAULT ''        -- outcome / observation; may be empty
  source_event_ids  TEXT NOT NULL DEFAULT '[]'      -- JSON list of raw_events.id this step covers
  screenshot_id     INTEGER REFERENCES screenshot_artifacts(id)
  suppressed        INTEGER NOT NULL DEFAULT 0      -- soft-delete; excluded from export
  manual_edit       INTEGER NOT NULL DEFAULT 0      -- examiner edited a field or merged/split
  evidentiary       INTEGER NOT NULL DEFAULT 0      -- ★ Tool 3's primary filter ★
```

The `action` / `result` split mirrors the two-column layout of paper
forensic exam notes (Time/Date · Action · Result). The `action`
column is the imperative description; `result` is what was observed
afterwards and is often empty for pure UI clicks.

### The two layers

The data model is deliberately split into two layers and Tool 3 should
respect that split:

- **Capture layer** (`raw_events`, `resolved_elements`,
  `screenshot_artifacts`) — what Inscription observed, frozen at
  capture time. Never mutated after recording. Carries SHA-256 of each
  screenshot for verifiability.
- **Guide layer** (`draft_steps`) — the editable, examiner-curated
  derivative. Steps reference back to the capture layer via
  `source_event_ids` and `screenshot_id`. Manual edits and structural
  ops (merge / split) set `manual_edit = 1`.

For a court-defensible report, Tool 3 can show *both*: the polished
step text *and* the raw events it was derived from.

---

## What Tool 3 should query

The primary integration query: **all evidentiary, non-suppressed steps
in the order the examiner left them**.

```sql
SELECT
  s.id,
  s.sequence,
  s.action,
  s.result,
  s.source_event_ids,
  sh.relative_path AS screenshot_path,
  sh.sha256        AS screenshot_sha256
FROM draft_steps s
LEFT JOIN screenshot_artifacts sh ON sh.id = s.screenshot_id
WHERE s.evidentiary = 1 AND s.suppressed = 0
ORDER BY s.sequence;
```

For each evidentiary step, Tool 3 can also walk back to the capture
layer if it needs the raw context (e.g. for an audit-trail appendix):

```sql
-- For each step, look up the raw events it was derived from. (Drop into
-- application code; sqlite has no JSON_EACH on TEXT-as-JSON without the
-- json1 extension. Easiest is to load the row, json.loads(source_event_ids),
-- and SELECT * FROM raw_events WHERE id IN (...).)
```

The `screenshot_path` is relative to the session directory. Resolve
it as `<session-slug>/<screenshot_path>`.

The `screenshot_sha256` was computed at capture time; if Tool 3 needs
to assert tamper-evident provenance, hash the file on disk and
compare.

---

## Stability promise

Inscription bumps `SCHEMA_VERSION` (and ships an ALTER-TABLE migration)
when it adds a column. Existing columns and table names are stable
across versions; *removing* or *renaming* a column would also be a
schema bump.

Tool 3 should read the `schema_version` from `session_info` and only
attempt to use columns it knows that version supports. The current
schema is **v5** as of this writing. Past version surfaces:

| Version | Added |
|---------|-------|
| 1 | Initial schema. |
| 2 | `resolved_elements.bounding_rect` (UIA element bbox in screen px). |
| 3 | `resolved_elements.owner_process_name` (for cross-process click context). |
| 4 | `draft_steps.evidentiary` (the integration flag for Tool 3). |
| 5 | `draft_steps.action` + `draft_steps.result` (replaces `draft_steps.text` to match the Time/Date · Action · Result notes layout). |

---

## What Inscription does NOT do

- Write to `case.json` (CaseForge's territory).
- Write to `.caseguide/` (CaseGuide's territory; reads only, and the
  panel hides itself when no `suggestions.json` is present).
- Move sessions between case directories. CaseForge or a separate tool
  should handle this if it's ever needed.
- Listen on a network port. All integration is via the filesystem.

If the tools need richer interaction in the future (live notification,
shared cache, etc.), this document is the place to revise — but the
filesystem boundary is intentionally the simplest thing that works.
