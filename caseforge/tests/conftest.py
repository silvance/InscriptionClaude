"""Test fixtures."""

from __future__ import annotations

import os

# Force the offscreen Qt platform so headless CI can construct widgets.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
