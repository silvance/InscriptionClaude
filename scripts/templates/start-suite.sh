#!/usr/bin/env bash
# First-run launcher for the air-gapped Inscription suite bundle (Linux).
#
# Mirrors start-suite.ps1. Lives at the root of the
# InscriptionSuite-Airgapped folder. It:
#   1. Points Ollama at the bundled models directory.
#   2. Starts the bundled Ollama server on a DEDICATED port
#      (127.0.0.1:11435 -- not the Ollama default 11434) so it
#      never collides with or silently reuses a system-wide Ollama
#      install on this machine.
#   3. Exports SUITE_LLM_BASE_URL so Inscription / CaseGuide
#      connect to our bundled instance, not the default.
#   4. Waits until /api/tags answers 200.
#   5. If more than one model is bundled, asks which one to use
#      and exports SUITE_LLM_MODEL.
#   6. Opens a small picker -- Inscription / CaseForge / CaseGuide.
#
# Quitting the picker stops the Ollama server. Re-run this script
# to bring everything back up; the model question fires every run
# so you can switch without restarting the workstation.
#
# Linux note: there's no UAC equivalent, so unlike the Windows
# launcher this script does not self-elevate. Inscription's UIA
# capture isn't available on Linux anyway (pywinauto is Windows-
# only), so no integrity-level concerns to work around.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --------------------------------------------------------------- environment

# Bundled Ollama runs on a dedicated, non-default port so we never
# accidentally reuse a system-wide Ollama install (which has its own
# model store and could silently produce different output -- bad for
# reproducibility in a forensic context).
BUNDLED_OLLAMA_PORT=11435
BUNDLED_OLLAMA_HOST="127.0.0.1:${BUNDLED_OLLAMA_PORT}"

export OLLAMA_MODELS="${ROOT}/models"
export OLLAMA_HOST="${BUNDLED_OLLAMA_HOST}"
# OLLAMA_KEEP_ALIVE keeps the loaded weights resident in RAM between
# requests so the first AI Rewrite click pays the model-load cost
# only once per session.
export OLLAMA_KEEP_ALIVE="10m"
# Tell the suite apps where our Ollama lives. Inscription and
# CaseGuide both read SUITE_LLM_BASE_URL when their per-user QSettings
# hasn't overridden it.
export SUITE_LLM_BASE_URL="http://${BUNDLED_OLLAMA_HOST}/v1"

OLLAMA_BIN="${ROOT}/ollama/bin/ollama"
if [[ ! -x "$OLLAMA_BIN" ]]; then
    echo "ERROR: bundled ollama binary not found or not executable at $OLLAMA_BIN" >&2
    echo "       The bundle is incomplete." >&2
    exit 1
fi

# Make Ollama's bundled runner libraries discoverable. The Linux
# tarball ships shared libs under lib/ollama/ that the binary loads
# at runtime; pointing LD_LIBRARY_PATH at it ensures we use the
# bundled libs rather than whatever the host workstation has.
export LD_LIBRARY_PATH="${ROOT}/ollama/lib/ollama${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

# ----------------------------------------------------- ollama lifecycle

ollama_up() {
    # curl --fail returns non-zero on HTTP 4xx/5xx; --max-time bounds
    # the probe so a totally unresponsive port doesn't hang the loop.
    curl --silent --fail --max-time 1 \
        "http://${BUNDLED_OLLAMA_HOST}/api/tags" > /dev/null 2>&1
}

OUR_OLLAMA_PID=""
cleanup() {
    if [[ -n "$OUR_OLLAMA_PID" ]] && kill -0 "$OUR_OLLAMA_PID" 2>/dev/null; then
        echo
        echo "Stopping bundled Ollama server..."
        kill "$OUR_OLLAMA_PID" 2>/dev/null || true
        # Give it a graceful 2s before SIGKILL.
        for _ in 1 2 3 4; do
            kill -0 "$OUR_OLLAMA_PID" 2>/dev/null || break
            sleep 0.5
        done
        if kill -0 "$OUR_OLLAMA_PID" 2>/dev/null; then
            kill -9 "$OUR_OLLAMA_PID" 2>/dev/null || true
        fi
    fi
}
trap cleanup EXIT INT TERM

if ollama_up; then
    echo "Ollama already responding on ${BUNDLED_OLLAMA_HOST} (our dedicated port) -- reusing."
else
    echo "Starting bundled Ollama server..."
    # Suppress Ollama's own log output to keep the picker prompt
    # readable. Ollama writes to stderr; ~/.ollama/logs/ holds the
    # full log if the operator needs to debug.
    "$OLLAMA_BIN" serve > /dev/null 2>&1 &
    OUR_OLLAMA_PID=$!

    deadline=$(( SECONDS + 60 ))
    while (( SECONDS < deadline )); do
        sleep 0.5
        if ollama_up; then
            break
        fi
    done
    if ! ollama_up; then
        echo "ERROR: Bundled Ollama did not become ready on ${BUNDLED_OLLAMA_HOST} within 60s." >&2
        echo "       Check that ${OLLAMA_BIN} runs on this machine, and that nothing" >&2
        echo "       else is bound to port ${BUNDLED_OLLAMA_PORT}." >&2
        exit 1
    fi
    echo "Bundled Ollama ready on ${BUNDLED_OLLAMA_HOST}."
fi

# ------------------------------------------------------- pick a model

# Walk the bundled manifest tree to find every model:tag the bundle
# ships. The launcher exports SUITE_LLM_MODEL before launching the
# apps so both Inscription and CaseGuide pick up the operator's choice.
list_bundled_models() {
    local lib_root="${ROOT}/models/manifests/registry.ollama.ai/library"
    if [[ ! -d "$lib_root" ]]; then
        return
    fi
    # Each model's tags are stored as files under <model_name>/<tag>.
    # Print them one per line as "name:tag", sorted.
    local name_dir tag_file
    for name_dir in "$lib_root"/*/; do
        [[ -d "$name_dir" ]] || continue
        local name
        name=$(basename "$name_dir")
        for tag_file in "$name_dir"/*; do
            [[ -f "$tag_file" ]] || continue
            local tag
            tag=$(basename "$tag_file")
            echo "${name}:${tag}"
        done
    done | sort
}

mapfile -t BUNDLED_MODELS < <(list_bundled_models)

if (( ${#BUNDLED_MODELS[@]} == 0 )); then
    echo "No bundled models found under ./models -- the apps will fall back to their built-in default."
elif (( ${#BUNDLED_MODELS[@]} == 1 )); then
    export SUITE_LLM_MODEL="${BUNDLED_MODELS[0]}"
    echo "Using bundled model: ${BUNDLED_MODELS[0]}"
else
    echo
    echo "Bundled models"
    echo "=============="
    for i in "${!BUNDLED_MODELS[@]}"; do
        marker=""
        if (( i == 0 )); then marker=" (default)"; fi
        printf "  [%d] %s%s\n" $(( i + 1 )) "${BUNDLED_MODELS[$i]}" "$marker"
    done
    echo
    read -r -p "Pick a model (Enter for default): " pick
    chosen="${BUNDLED_MODELS[0]}"
    if [[ -n "$pick" ]]; then
        if [[ "$pick" =~ ^[0-9]+$ ]] && (( pick >= 1 )) && (( pick <= ${#BUNDLED_MODELS[@]} )); then
            chosen="${BUNDLED_MODELS[$(( pick - 1 ))]}"
        else
            echo "Unknown selection -- falling back to default."
        fi
    fi
    export SUITE_LLM_MODEL="$chosen"
    echo "Using bundled model: $chosen"
fi

# ----------------------------------------------------------------- the menu

# (key, label, relative-path) flat array, : as separator.
APPS=(
    "1:Inscription (capture a workflow):Inscription/Inscription"
    "2:CaseForge (case intake / report):CaseForge/CaseForge"
    "3:CaseGuide (suggestion coach):CaseGuide/CaseGuide"
)

while true; do
    echo
    echo "Inscription suite -- air-gapped"
    echo "==============================="
    for entry in "${APPS[@]}"; do
        IFS=':' read -r key label _exe <<< "$entry"
        printf "  [%s] %s\n" "$key" "$label"
    done
    echo "  [Q] Quit (also stops the bundled Ollama server)"
    echo
    read -r -p "Pick: " choice

    case "${choice,,}" in
        q) break ;;
        "") continue ;;
    esac

    matched=""
    for entry in "${APPS[@]}"; do
        IFS=':' read -r key _label exe_rel <<< "$entry"
        if [[ "$choice" == "$key" ]]; then
            matched="$exe_rel"
            break
        fi
    done
    if [[ -z "$matched" ]]; then
        echo "Unknown selection: $choice"
        continue
    fi
    exe_path="${ROOT}/${matched}"
    if [[ ! -x "$exe_path" ]]; then
        echo "Missing or non-executable: ${exe_path} -- bundle is incomplete."
        continue
    fi
    # SUITE_LLM_MODEL is already in the script's environment; the
    # spawned process inherits it. Detach so the picker stays
    # responsive while the app runs.
    "$exe_path" > /dev/null 2>&1 &
    disown
done
