"""Report rendering: fill DOCX templates with case data.

CaseForge owns the case data (``case.json``, custody, examiner) and
already enumerates the Inscription sessions under each case dir. This
package adds a fourth surface — taking those data sources, plus
CaseGuide's ``suggestions.json`` if present, and rendering them into a
DOCX template the examiner provides.

Templates use ``docxtpl``'s Jinja2 syntax (``{{ token }}`` for
substitution, ``{% for s in suggestions.completed %} ... {% endfor %}``
for iteration). The full token vocabulary is documented in
:mod:`caseforge.report.context`.

Phase 1 ships the renderer and a CLI. The UI surface (a Reports tab
in CaseForge) lands separately so the renderer can be tested headless
and adopted from scripts before the GUI work.
"""

from __future__ import annotations

from caseforge.report.context import ReportContext, build_context
from caseforge.report.render import RenderError, render_report

__all__ = ["RenderError", "ReportContext", "build_context", "render_report"]
