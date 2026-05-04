"""Per-platform capability flags for Inscription.

A small static module that lives alongside the platform-backend
factories. The single source of truth for "is this capability
available on this OS?" so the UI doesn't sprinkle ``os.name`` checks
across half a dozen files.

Currently just one flag: automated step capture, which depends on the
Windows UI Automation API via ``pywinauto`` and has no Linux
equivalent. The rest of the app (case management, step rewriting,
exports) is platform-neutral.
"""

from __future__ import annotations

import os
from typing import Final

#: True when the host OS supports the full automated capture pipeline:
#: UIA-resolved click targets, foreground-window inspection, and the
#: keyboard / mouse hooks pynput uses to record events. Today that
#: means Windows -- pywinauto is Windows-only and there's no
#: equivalent Linux/macOS UIA backend that produces forensic-grade
#: element identity.
CAPTURE_FULLY_SUPPORTED: Final = os.name == "nt"

#: Operator-facing one-line explanation. Surfaced as a tooltip on the
#: greyed-out Record button and as a status-bar message at startup
#: when capture isn't supported. Kept short -- the longer story lives
#: in AIR_GAPPED.md's Linux section.
CAPTURE_UNAVAILABLE_REASON: Final = (
    "Automated step capture is Windows-only. Case management, step "
    "rewriting, and exports work fully on this platform; only live "
    "capture is disabled."
)
