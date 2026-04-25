"""Entrypoint for ``python -m caseguide``."""

from __future__ import annotations

from caseguide.app import main

if __name__ == "__main__":
    raise SystemExit(main())
