#!/usr/bin/env bash
# CaseForge dev helper.
#
# Usage:
#   ./scripts/dev.sh                  # runs lint + typecheck + test
#   ./scripts/dev.sh install          # install package with dev extras
#   ./scripts/dev.sh lint             # ruff check
#   ./scripts/dev.sh format           # ruff format (writes changes)
#   ./scripts/dev.sh format-check     # ruff format --check (read-only)
#   ./scripts/dev.sh typecheck        # mypy strict
#   ./scripts/dev.sh test             # pytest
#   ./scripts/dev.sh run              # launch the app from source
#   ./scripts/dev.sh build            # build with PyInstaller
#   ./scripts/dev.sh all              # lint + typecheck + test (CI parity)

set -euo pipefail

cmd="${1:-all}"

step() {
  echo
  echo ">>> $1"
}

case "$cmd" in
  install)
    step "pip install -e .[dev]"
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
    ;;
  lint)
    step "ruff check"
    python -m ruff check src tests
    ;;
  format)
    step "ruff format"
    python -m ruff format src tests
    ;;
  format-check)
    step "ruff format --check"
    python -m ruff format --check src tests
    ;;
  typecheck)
    step "mypy"
    python -m mypy src tests
    ;;
  test)
    step "pytest"
    python -m pytest -q
    ;;
  run)
    step "python -m caseforge"
    python -m caseforge
    ;;
  build)
    step "pyinstaller"
    pyinstaller packaging/caseforge.spec --noconfirm
    echo "Build output: dist/CaseForge/CaseForge"
    ;;
  all)
    "$0" lint
    "$0" format-check
    "$0" typecheck
    "$0" test
    echo
    echo "All checks passed."
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    exit 2
    ;;
esac
