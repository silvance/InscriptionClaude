"""Shared pytest configuration.

Forces Qt to use the offscreen platform plugin for headless CI runs. Must run
before any test module imports PySide6 widget classes.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
