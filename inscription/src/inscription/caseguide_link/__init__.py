"""Read-only consumer for files CaseGuide drops into a case directory.

Inscription deliberately does not import from the ``caseguide`` package —
they're sibling apps that communicate through the on-disk contract
documented in :file:`inscription/docs/integration.md`. This package
parses those files into local dataclasses so a missing or stale
CaseGuide install never breaks Inscription.
"""

from __future__ import annotations

from inscription.caseguide_link.reader import (
    CaseguideDocument,
    CaseguideSuggestion,
    SuggestionsReadError,
    read_suggestions,
    suggestions_path,
)

__all__ = [
    "CaseguideDocument",
    "CaseguideSuggestion",
    "SuggestionsReadError",
    "read_suggestions",
    "suggestions_path",
]
