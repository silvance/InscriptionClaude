#!/usr/bin/env bash
# Inscription dev helper (Linux / macOS).
#
# Usage:
#   ./scripts/dev.sh                # lint + format check + typecheck + test
#   ./scripts/dev.sh install        # install package with dev extras
#   ./scripts/dev.sh lint           # ruff check
#   ./scripts/dev.sh format         # ruff format (writes changes)
#   ./scripts/dev.sh format-check   # ruff format --check (read-only)
#   ./scripts/dev.sh typecheck      # mypy strict
#   ./scripts/dev.sh test           # pytest with coverage
#   ./scripts/dev.sh run            # launch the app from source
#   ./scripts/dev.sh build          # PyInstaller one-folder build
#   ./scripts/dev.sh clean          # remove build artefacts and caches
#   ./scripts/dev.sh all            # lint + format-check + typecheck + test

set -euo pipefail

# Resolve repo root regardless of cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

# ANSI colours (skipped if stdout isn't a terminal).
if [[ -t 1 ]]; then
    C_CYAN="\033[36m"
    C_GREEN="\033[32m"
    C_RED="\033[31m"
    C_RESET="\033[0m"
else
    C_CYAN=""; C_GREEN=""; C_RED=""; C_RESET=""
fi

step() {
    echo ""
    echo -e "${C_CYAN}>>> $1${C_RESET}"
}

ok() {
    echo -e "${C_GREEN}$1${C_RESET}"
}

fail() {
    echo -e "${C_RED}$1${C_RESET}" >&2
    exit 1
}

cmd_install() {
    step "pip install -e .[dev]"
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev]"
}

cmd_lint() {
    step "ruff check"
    ruff check src tests
}

cmd_format() {
    step "ruff format"
    ruff format src tests
}

cmd_format_check() {
    step "ruff format --check"
    ruff format --check src tests
}

cmd_typecheck() {
    step "mypy (strict)"
    mypy src tests
}

cmd_test() {
    export QT_QPA_PLATFORM=offscreen
    step "pytest"
    pytest --cov=inscription --cov-report=term
}

cmd_run() {
    step "python -m inscription"
    python -m inscription
}

cmd_build() {
    step "pyinstaller"
    pyinstaller packaging/inscription.spec --noconfirm
    echo ""
    ok "Build output: dist/Inscription/Inscription (or Inscription.exe on Windows)"
}

cmd_clean() {
    step "clean"
    rm -rf build dist .pytest_cache .mypy_cache .ruff_cache \
           coverage.xml .coverage htmlcov
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
    ok "Cleaned."
}

cmd_all() {
    cmd_lint
    cmd_format_check
    cmd_typecheck
    cmd_test
    echo ""
    ok "All checks passed."
}

# Dispatch.
CMD="${1:-all}"
case "${CMD}" in
    install)        cmd_install ;;
    lint)           cmd_lint ;;
    format)         cmd_format ;;
    format-check)   cmd_format_check ;;
    typecheck)      cmd_typecheck ;;
    test)           cmd_test ;;
    run)            cmd_run ;;
    build)          cmd_build ;;
    clean)          cmd_clean ;;
    all)            cmd_all ;;
    *)
        fail "Unknown command: ${CMD}
Usage: $0 {install|lint|format|format-check|typecheck|test|run|build|clean|all}"
        ;;
esac
