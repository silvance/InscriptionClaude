"""Guide exporters.

Two formats today: HTML for sharing as a self-contained webpage, and
Markdown for landing in tickets / wikis / PR descriptions. Both stage
crop+highlighted screenshots into a sibling assets folder so the
output is portable as a unit.
"""

from inscription.export.html import export_html
from inscription.export.markdown import export_markdown

__all__ = ["export_html", "export_markdown"]
