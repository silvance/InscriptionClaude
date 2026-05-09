"""Guide exporters.

Four formats today:

- HTML: a polished, self-contained webpage.
- Markdown: drops cleanly into tickets, wikis, PR descriptions.
- Forensic notes (HTML): a Time/Date · Action · Result table that
  matches the layout examiners use on paper, with a case-metadata
  header and a sign-off footer.
- PDF: the forensic-notes content rendered to a self-contained PDF
  with per-page headers (case + examiner) and footers (page X of Y
  + generated-at timestamp). Drops directly into a discovery
  package without an HTML asset directory.

All formats stage crop+highlighted screenshots into a sibling
assets folder (PDF inlines them via a temp dir at render time so
the output is a single file).
"""

from inscription.export.forensic import export_forensic_notes
from inscription.export.html import export_html
from inscription.export.markdown import export_markdown
from inscription.export.pdf import export_pdf

__all__ = ["export_forensic_notes", "export_html", "export_markdown", "export_pdf"]
