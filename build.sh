#!/usr/bin/env bash
# Build Inscription, CaseForge, and CaseGuide as standalone Linux executables.
#
# Mirrors build.ps1 (Windows). Runs PyInstaller for each sub-package and
# places the one-folder bundles at:
#     inscription/dist/Inscription/Inscription
#     caseforge/dist/CaseForge/CaseForge
#     caseguide/dist/CaseGuide/CaseGuide
#
# Prerequisites -- from the repo root, activate the shared venv then run:
#     source .venv/bin/activate
#     python -m pip install -e suite_common -e inscription[dev] \
#         -e caseforge[dev] -e caseguide[dev]
#     ./build.sh
#
# The [dev] extras include PyInstaller. The suite_common package is the
# shared LLM client + JSON helpers all three apps depend on.
#
# Inscription on Linux ships in degraded form: case management, step
# rewriting, and exports work; pywinauto-driven UIA capture does not
# (no Linux equivalent for the Windows UI Automation API).
#
# Usage:
#     ./build.sh                       # all three
#     ./build.sh --app inscription     # one
#     ./build.sh --clean               # wipe dist/ first
#     ./build.sh --app caseforge --clean

set -euo pipefail

APP="all"
CLEAN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --app)
            APP="$2"
            shift 2
            ;;
        --clean)
            CLEAN=1
            shift
            ;;
        -h|--help)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: $0 [--app inscription|caseforge|caseguide|all] [--clean]" >&2
            exit 2
            ;;
    esac
done

case "$APP" in
    inscription|caseforge|caseguide|all) ;;
    *)
        echo "Invalid --app: $APP. Expected: inscription, caseforge, caseguide, all." >&2
        exit 2
        ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# (sub_dir, spec_name, label) triples — bash 3 / 4 compatible flat array.
BUILDS=(
    "inscription:inscription.spec:Inscription"
    "caseforge:caseforge.spec:CaseForge"
    "caseguide:caseguide.spec:CaseGuide"
)

invoke_build() {
    local sub_dir="$1"
    local spec_name="$2"
    local label="$3"

    local target="$REPO_ROOT/$sub_dir"
    echo
    echo "=== Building $label ==="

    pushd "$target" > /dev/null
    if [[ "$CLEAN" -eq 1 && -d dist ]]; then
        echo "  Removing dist/..."
        rm -rf dist
    fi
    # Invoke through `python -m` so we don't depend on the venv's
    # Scripts/bin being on PATH -- mirrors build.ps1's reasoning.
    python -m PyInstaller "packaging/$spec_name" --noconfirm
    popd > /dev/null

    echo "=== ${label}: OK ==="
}

for entry in "${BUILDS[@]}"; do
    IFS=':' read -r sub_dir spec_name label <<< "$entry"
    if [[ "$APP" == "all" || "$APP" == "$sub_dir" ]]; then
        invoke_build "$sub_dir" "$spec_name" "$label"
    fi
done

echo
echo "Build complete."
for entry in "${BUILDS[@]}"; do
    IFS=':' read -r sub_dir spec_name label <<< "$entry"
    if [[ "$APP" == "all" || "$APP" == "$sub_dir" ]]; then
        bin="$REPO_ROOT/$sub_dir/dist/$label/$label"
        if [[ -x "$bin" ]]; then
            echo "  $bin"
        fi
    fi
done
