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

# Bail early when the env can't run PyInstaller, printing the exact
# commands to fix it. The bare `No module named PyInstaller` from
# invoking `python -m PyInstaller` later is too cryptic to act on.
#
# Order matters: PyInstaller importing is the only thing the build
# actually requires. Venv-active and Python-version checks are
# *guidance* for the dominant local-checkout failure mode, but they
# must NOT reject a working setup -- CI installs Python via
# actions/setup-python without a venv, and any contributor who sets
# things up unconventionally (pyenv-managed system Python, conda,
# nix shell, etc.) has likely got PyInstaller importable already.
preflight() {
    local py_major py_minor
    if ! command -v python >/dev/null 2>&1; then
        echo "ERROR: 'python' is not on PATH." >&2
        echo >&2
        echo "Install Python 3.12+ first (e.g. on Fedora: sudo dnf install python3.12)," >&2
        echo "then create and activate a venv:" >&2
        echo "    cd $REPO_ROOT" >&2
        echo "    python3.12 -m venv .venv" >&2
        echo "    source .venv/bin/activate" >&2
        echo "    python -m pip install -e suite_common \\" >&2
        echo "        -e inscription[dev] -e caseforge[dev] -e caseguide[dev]" >&2
        exit 1
    fi

    # Fast accept: PyInstaller already importable -> we're set up.
    # Skips the venv check so unconventional setups (CI, conda,
    # system-Python pip --user) work without complaint.
    if python -c "import PyInstaller" >/dev/null 2>&1; then
        return
    fi

    # PyInstaller missing -- now graduate the guidance based on
    # how the environment looks.
    py_major=$(python -c 'import sys; print(sys.version_info[0])' 2>/dev/null || echo 0)
    py_minor=$(python -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo 0)
    if (( py_major < 3 || (py_major == 3 && py_minor < 12) )); then
        echo "ERROR: Python 3.12+ required, found ${py_major}.${py_minor}." >&2
        echo >&2
        echo "Install Python 3.12+ (e.g. on Fedora: sudo dnf install python3.12)" >&2
        echo "and create a venv with it:" >&2
        echo "    cd $REPO_ROOT" >&2
        echo "    python3.12 -m venv .venv" >&2
        echo "    source .venv/bin/activate" >&2
        echo "    python -m pip install -e suite_common \\" >&2
        echo "        -e inscription[dev] -e caseforge[dev] -e caseguide[dev]" >&2
        exit 1
    fi

    if [[ -z "${VIRTUAL_ENV:-}" ]]; then
        echo "ERROR: PyInstaller is not installed and no virtual environment is active." >&2
        echo >&2
        if [[ -f "${REPO_ROOT}/.venv/bin/activate" ]]; then
            echo "Activate the existing venv first:" >&2
            echo "    source ${REPO_ROOT}/.venv/bin/activate" >&2
            echo >&2
            echo "Then re-run this script. (If PyInstaller still isn't found," >&2
            echo "the venv is missing the [dev] extras -- see the install line below.)" >&2
            echo "    python -m pip install -e suite_common \\" >&2
            echo "        -e inscription[dev] -e caseforge[dev] -e caseguide[dev]" >&2
        else
            echo "Create and activate one, then install the [dev] extras:" >&2
            echo "    cd $REPO_ROOT" >&2
            echo "    python3.12 -m venv .venv" >&2
            echo "    source .venv/bin/activate" >&2
            echo "    python -m pip install -e suite_common \\" >&2
            echo "        -e inscription[dev] -e caseforge[dev] -e caseguide[dev]" >&2
        fi
        exit 1
    fi

    echo "ERROR: PyInstaller is not installed in the active venv." >&2
    echo "       (\$VIRTUAL_ENV = ${VIRTUAL_ENV})" >&2
    echo >&2
    echo "Install the [dev] extras (which include PyInstaller):" >&2
    echo "    cd $REPO_ROOT" >&2
    echo "    python -m pip install -e suite_common \\" >&2
    echo "        -e inscription[dev] -e caseforge[dev] -e caseguide[dev]" >&2
    exit 1
}

preflight

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
