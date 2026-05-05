#!/usr/bin/env bash
# Produce a self-contained InscriptionSuite folder for air-gapped
# Linux deployment. Mirror of package-airgapped.ps1 (Windows).
#
# Output: dist/InscriptionSuite-Airgapped-Linux/ (or wherever
# --output-root points) -- copy the whole folder to a USB stick,
# drop it onto the air-gapped Linux workstation, and run install.sh.
#
# The bundle contains:
#     Inscription/         Inscription one-folder PyInstaller bundle (ELF)
#     CaseForge/           CaseForge one-folder bundle
#     CaseGuide/           CaseGuide one-folder bundle
#     ollama/              Bundled Ollama Linux runtime (bin/ + lib/)
#     models/              Pre-pulled Ollama model blobs and manifests
#     start-suite.sh       First-run launcher
#     install.sh           Per-user installer
#     README.txt           Operator notes
#
# Prerequisites on this (connected) Linux build machine:
#     - PyInstaller-capable venv with all four packages installed
#       editable (see SETUP.md).
#     - Ollama models already pulled to a local store.
#     - The ollama-linux-amd64.tgz tarball downloaded and extracted
#       to a directory; pass --ollama-bundle <that-directory>.
#       Get it from https://github.com/ollama/ollama/releases.
#
# Usage:
#     ./scripts/package-airgapped.sh \
#         --ollama-bundle ~/Downloads/ollama-linux-amd64
#     ./scripts/package-airgapped.sh \
#         --ollama-bundle ~/Downloads/ollama-linux-amd64 \
#         --models qwen2.5:7b-instruct-q5_K_M --skip-build
#     ./scripts/package-airgapped.sh \
#         --ollama-bundle ~/Downloads/ollama-linux-amd64 \
#         --output-root /media/usb/

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Defaults.
MODELS=("gemma4:latest" "granite4:tiny-h")
OLLAMA_MODELS_ROOT="${HOME}/.ollama/models"
OLLAMA_BUNDLE_SRC=""
OUTPUT_ROOT=""
SKIP_BUILD=0

write_step() {
    echo
    echo "==> $1"
}

# Refuse to stage onto a FAT32 destination -- 4 GB single-file
# limit blocks the model blobs (qwen 7B is ~5.4 GB, qwen 14B is
# ~9 GB) and surfaces as a misleading "no space left" mid-copy.
check_destination_filesystem() {
    local path="$1"
    [[ -n "$path" ]] || return 0
    command -v findmnt >/dev/null 2>&1 || return 0
    local probe="$path"
    while [[ -n "$probe" && ! -e "$probe" ]]; do
        probe=$(dirname "$probe")
    done
    [[ -n "$probe" ]] || return 0
    local fstype
    fstype=$(findmnt -no FSTYPE -T "$probe" 2>/dev/null || true)
    case "$fstype" in
        vfat|msdos|fat|fat16|fat32)
            echo "ERROR: destination $path is on a $fstype (FAT32-family) volume." >&2
            echo "       FAT32 caps individual files at 4 GB; the bundled model blobs" >&2
            echo "       are larger (qwen 7B is ~5.4 GB, qwen 14B is ~9 GB)." >&2
            echo "       Reformat as exFAT or ext4 (warning: wipes the volume) then re-run." >&2
            exit 1
            ;;
    esac
}

# Parse args. --models takes a comma-separated value; everything else
# is a single token.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --models)
            IFS=',' read -r -a MODELS <<< "$2"
            shift 2
            ;;
        --ollama-bundle)
            OLLAMA_BUNDLE_SRC="$(realpath -m "$2")"
            shift 2
            ;;
        --ollama-models-root)
            OLLAMA_MODELS_ROOT="$(realpath -m "$2")"
            shift 2
            ;;
        --output-root)
            OUTPUT_ROOT="$(realpath -m "$2")"
            shift 2
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        -h|--help)
            sed -n '2,33p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if [[ -z "$OLLAMA_BUNDLE_SRC" ]]; then
    echo "ERROR: --ollama-bundle is required." >&2
    echo "       Download ollama-linux-amd64.tgz from" >&2
    echo "       https://github.com/ollama/ollama/releases, extract it" >&2
    echo "       (tar -xzf ollama-linux-amd64.tgz -C /tmp/ollama-linux-amd64)," >&2
    echo "       and pass --ollama-bundle /tmp/ollama-linux-amd64." >&2
    exit 2
fi

if [[ -n "$OUTPUT_ROOT" ]]; then
    mkdir -p "$OUTPUT_ROOT"
    BUNDLE_ROOT="${OUTPUT_ROOT}/InscriptionSuite-Airgapped-Linux"
else
    BUNDLE_ROOT="${REPO_ROOT}/dist/InscriptionSuite-Airgapped-Linux"
fi

# 1. Sanity checks ----------------------------------------------------------

write_step "Verifying prerequisites"

# FAT32 staging would fail mid-blob-copy with a misleading
# "no space left" error; refuse up front instead.
check_destination_filesystem "$BUNDLE_ROOT"

if [[ ! -d "$OLLAMA_BUNDLE_SRC" ]]; then
    echo "ERROR: --ollama-bundle path does not exist: $OLLAMA_BUNDLE_SRC" >&2
    exit 1
fi
if [[ ! -x "$OLLAMA_BUNDLE_SRC/bin/ollama" ]]; then
    echo "ERROR: $OLLAMA_BUNDLE_SRC/bin/ollama is missing or not executable." >&2
    echo "       Did you extract ollama-linux-amd64.tgz correctly?" >&2
    exit 1
fi
if [[ ! -d "$OLLAMA_MODELS_ROOT" ]]; then
    echo "ERROR: Ollama models dir not found: $OLLAMA_MODELS_ROOT" >&2
    echo "       Run 'ollama pull <model>' on this machine first," >&2
    echo "       or pass --ollama-models-root." >&2
    exit 1
fi
for m in "${MODELS[@]}"; do
    name="${m%%:*}"
    if [[ "$m" == *:* ]]; then
        tag="${m##*:}"
    else
        tag="latest"
    fi
    manifest="${OLLAMA_MODELS_ROOT}/manifests/registry.ollama.ai/library/${name}/${tag}"
    if [[ ! -f "$manifest" ]]; then
        echo "ERROR: model '$m' is not pulled on this machine." >&2
        echo "       Run 'ollama pull $m' and rerun this script." >&2
        exit 1
    fi
done

# 2. Build the three apps ----------------------------------------------------

if (( SKIP_BUILD == 0 )); then
    write_step "Building Inscription / CaseForge / CaseGuide"
    "${REPO_ROOT}/build.sh"
else
    echo "  Skipping build (per --skip-build)"
fi

# 3. Reset the bundle output directory --------------------------------------

write_step "Staging bundle at $BUNDLE_ROOT"
if [[ -d "$BUNDLE_ROOT" ]]; then
    rm -rf "$BUNDLE_ROOT"
fi
mkdir -p "$BUNDLE_ROOT"

# 4. Copy each app's one-folder bundle --------------------------------------

apps=(
    "inscription/dist/Inscription:Inscription"
    "caseforge/dist/CaseForge:CaseForge"
    "caseguide/dist/CaseGuide:CaseGuide"
)
for entry in "${apps[@]}"; do
    IFS=':' read -r src_rel dest_name <<< "$entry"
    src="${REPO_ROOT}/${src_rel}"
    if [[ ! -d "$src" ]]; then
        echo "ERROR: build output missing: $src. Re-run build.sh (drop --skip-build)." >&2
        exit 1
    fi
    echo "  Copying $dest_name..."
    cp -r "$src" "${BUNDLE_ROOT}/${dest_name}"
done

# 5. Copy Ollama Linux runtime ---------------------------------------------

write_step "Bundling Ollama runtime from $OLLAMA_BUNDLE_SRC"
ollama_dest="${BUNDLE_ROOT}/ollama"
cp -r "$OLLAMA_BUNDLE_SRC" "$ollama_dest"
# Defensive: tarball preserves +x but a USB-mounted exFAT source
# could strip it. Re-assert.
chmod +x "${ollama_dest}/bin/ollama" 2>/dev/null || true

# 6. Copy only the requested model blobs + manifests ----------------------

write_step "Bundling model blobs (only the requested models, to keep size down)"
models_dest="${BUNDLE_ROOT}/models"
mkdir -p "${models_dest}/blobs"
mkdir -p "${models_dest}/manifests/registry.ollama.ai/library"

# Use a temp file as a poor-man's set for blob digests so we don't
# copy the same blob twice when two models share a layer.
digests_file="$(mktemp)"
trap 'rm -f "$digests_file"' EXIT

for m in "${MODELS[@]}"; do
    name="${m%%:*}"
    if [[ "$m" == *:* ]]; then
        tag="${m##*:}"
    else
        tag="latest"
    fi

    src_manifest="${OLLAMA_MODELS_ROOT}/manifests/registry.ollama.ai/library/${name}/${tag}"
    dest_manifest_dir="${models_dest}/manifests/registry.ollama.ai/library/${name}"
    mkdir -p "$dest_manifest_dir"
    cp "$src_manifest" "${dest_manifest_dir}/${tag}"

    # Read the manifest with python3 (jq isn't universal). Print
    # config + layer digests, one per line. We push these into the
    # digests_file so we can dedup with sort -u below.
    python3 - "$src_manifest" >> "$digests_file" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    m = json.load(f)
config = m.get("config", {}) or {}
if config.get("digest"):
    print(config["digest"])
for layer in m.get("layers", []) or []:
    if layer.get("digest"):
        print(layer["digest"])
PY
    layer_count=$(python3 -c "
import json, sys
with open('$src_manifest', encoding='utf-8') as f:
    m = json.load(f)
print(len(m.get('layers', []) or []))
")
    echo "  $m -> manifest staged, $layer_count layers referenced"
done

# Dedup digest list (a layer shared between two model variants
# only needs one copy of its blob).
sort -u "$digests_file" -o "$digests_file"

blob_count=0
while IFS= read -r digest; do
    [[ -n "$digest" ]] || continue
    # Manifest format is "sha256:abc..."; the on-disk filename is
    # "sha256-abc..." (Ollama normalises across platforms).
    blob_name="${digest/sha256:/sha256-}"
    src_blob="${OLLAMA_MODELS_ROOT}/blobs/${blob_name}"
    if [[ ! -f "$src_blob" ]]; then
        echo "ERROR: manifest references blob $digest but the blob is missing at $src_blob." >&2
        echo "       Re-run 'ollama pull' for the affected model." >&2
        exit 1
    fi
    cp "$src_blob" "${models_dest}/blobs/${blob_name}"
    blob_count=$(( blob_count + 1 ))
done < "$digests_file"
echo "  Copied $blob_count unique blobs."

# 7. Drop in the launcher script + installer + README ---------------------

write_step "Writing start-suite.sh, install.sh, and README.txt"

scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

start_script="${scripts_dir}/templates/start-suite.sh"
if [[ ! -f "$start_script" ]]; then
    echo "ERROR: launcher template missing at $start_script. The repository may be incomplete." >&2
    exit 1
fi
cp "$start_script" "${BUNDLE_ROOT}/start-suite.sh"
chmod +x "${BUNDLE_ROOT}/start-suite.sh"

install_script="${scripts_dir}/templates/install.sh"
if [[ ! -f "$install_script" ]]; then
    echo "ERROR: installer template missing at $install_script. The repository may be incomplete." >&2
    exit 1
fi
cp "$install_script" "${BUNDLE_ROOT}/install.sh"
chmod +x "${BUNDLE_ROOT}/install.sh"

readme="${scripts_dir}/templates/airgapped-README-linux.txt"
if [[ -f "$readme" ]]; then
    cp "$readme" "${BUNDLE_ROOT}/README.txt"
fi

# 8. Report ---------------------------------------------------------------

total_bytes=$(du -sb "$BUNDLE_ROOT" | awk '{print $1}')
total_gb=$(python3 -c "print(f'{${total_bytes}/(1024**3):.2f}')")

echo
echo "Bundle ready at:"
echo "  $BUNDLE_ROOT"
echo "  Total size: $total_gb GB"
echo
echo "Next steps:"
echo "  1. Copy the whole folder to a USB drive."
echo "  2. On the air-gapped workstation, run install.sh from inside it."
echo "     (Or copy it anywhere with write access and run start-suite.sh"
echo "     directly to test without installing.)"
