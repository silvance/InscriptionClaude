"""Guide exporters.

Three formats today:

- HTML: a polished, self-contained webpage.
- Markdown: drops cleanly into tickets, wikis, PR descriptions.
- Forensic notes (HTML): a Time/Date · Action · Result table that
  matches the layout examiners use on paper, with a case-metadata
  header and a sign-off footer.

All three stage crop+highlighted screenshots into a sibling assets
folder so the output is portable as a unit.
"""

from inscription.export.forensic import export_forensic_notes
from inscription.export.html import export_html
from inscription.export.markdown import export_markdown

__all__ = ["export_forensic_notes", "export_html", "export_markdown"]
