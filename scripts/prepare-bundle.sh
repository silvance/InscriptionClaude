#!/usr/bin/env bash
# Pull models, build the InscriptionSuite air-gapped bundle, and
# (optionally) stage it onto an external drive in one shot. Linux
# equivalent of prepare-bundle.ps1.
#
# On the connected build machine: pulls the requested LLM model
# tags via Ollama, runs package-airgapped.sh to assemble the bundle
# (apps + Ollama runtime + model blobs + launcher), and either
# leaves the bundle in dist/InscriptionSuite-Airgapped-Linux/ or
# copies it to a destination (e.g. an external drive) for transfer.
#
# Default model set: gemma4:latest + granite4:tiny-h, matching the
# Windows build. Override with --models if you need different tags.
#
# Required: --ollama-bundle <path> to a directory laid out as
# bin/ollama + lib/ollama/. Easiest paths to one:
#
#   1. (Recommended.) Install Ollama on this build machine the normal way
#      and point at /usr/local -- the layout matches:
#        curl -fsSL https://ollama.com/install.sh | sh
#        --ollama-bundle /usr/local
#
#   2. Extract the standalone Linux runtime archive (Ollama ships it as
#      a Zstandard-compressed tar -- not .tgz):
#        curl -LO https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst
#        mkdir -p /tmp/ollama-linux-amd64
#        tar --zstd -xf ollama-linux-amd64.tar.zst -C /tmp/ollama-linux-amd64
#        --ollama-bundle /tmp/ollama-linux-amd64
#
# Usage:
#     ./scripts/prepare-bundle.sh \
#         --ollama-bundle /usr/local
#     ./scripts/prepare-bundle.sh \
#         --ollama-bundle /usr/local \
#         --destination /media/usb/
#     ./scripts/prepare-bundle.sh \
#         --ollama-bundle /tmp/ollama-linux-amd64 \
#         --models gemma4:latest --skip-pull --destination /media/usb/

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Defaults match prepare-bundle.ps1 on the Windows side.
DESTINATION=""
MODELS=("gemma4:latest" "granite4:tiny-h")
OLLAMA_BUNDLE=""
SKIP_PULL=0
SKIP_BUILD=0
INCLUDE_70B=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --destination)
            DESTINATION="$(realpath -m "$2")"
            shift 2
            ;;
        --models)
            IFS=',' read -r -a MODELS <<< "$2"
            shift 2
            ;;
        --ollama-bundle)
            OLLAMA_BUNDLE="$(realpath -m "$2")"
            shift 2
            ;;
        --include-70b)
            INCLUDE_70B=1
            shift
            ;;
        --skip-pull)
            SKIP_PULL=1
            shift
            ;;
        --skip-build)
            SKIP_BUILD=1
            shift
            ;;
        -h|--help)
            sed -n '2,38p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

if [[ -z "$OLLAMA_BUNDLE" ]]; then
    cat <<'EOF' >&2
ERROR: --ollama-bundle is required.
       Pass a directory containing bin/ollama and lib/ollama/. Easiest paths:

       1. (Recommended.) Install Ollama on this build machine and point at
          /usr/local -- the curl installer lays the layout we need:
            curl -fsSL https://ollama.com/install.sh | sh
            --ollama-bundle /usr/local

       2. Extract the standalone Linux runtime archive
          (Ollama ships it as Zstandard-compressed tar, not .tgz):
            curl -LO https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst
            mkdir -p /tmp/ollama-linux-amd64
            tar --zstd -xf ollama-linux-amd64.tar.zst -C /tmp/ollama-linux-amd64
            --ollama-bundle /tmp/ollama-linux-amd64
EOF
    exit 2
fi

if (( INCLUDE_70B )); then
    have_70b=0
    for m in "${MODELS[@]}"; do
        if [[ "$m" == "llama3.3:70b-instruct-q4_K_M" ]]; then
            have_70b=1
            break
        fi
    done
    if (( have_70b == 0 )); then
        MODELS+=("llama3.3:70b-instruct-q4_K_M")
    fi
fi

# When the operator wants both a fresh build and a destination, stage
# directly at the destination so we don't need ~30 GB free locally
# (15 GB to stage + 15 GB to copy). --skip-build keeps the original
# semantics (bundle already exists in dist/, copy it to --destination)
# so we don't break the "rebuild a USB from an existing local bundle"
# flow.
in_place_build=0
if [[ -n "$DESTINATION" ]] && (( SKIP_BUILD == 0 )); then
    in_place_build=1
    BUNDLE_SRC="${DESTINATION}/InscriptionSuite-Airgapped-Linux"
else
    BUNDLE_SRC="${REPO_ROOT}/dist/InscriptionSuite-Airgapped-Linux"
fi

write_step() {
    echo
    echo "==> $1"
}

# Refuse to stage onto a FAT32 destination. FAT32 caps individual
# files at 4 GB; the bundled model blobs are larger (qwen 7B is
# ~5.4 GB, qwen 14B is ~9 GB), so a FAT32 destination fails
# mid-blob-copy with a misleading "no space left on device" error
# even when the volume has tens of GB free. findmnt is in util-linux
# on every distro we target, but be defensive in case it's missing.
check_destination_filesystem() {
    local path="$1"
    [[ -n "$path" ]] || return 0
    command -v findmnt >/dev/null 2>&1 || return 0
    # findmnt -T walks up to find the mountpoint covering $path,
    # which works even when the destination directory doesn't exist
    # yet (we just need the parent mount).
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

# 1. Sanity: Ollama on PATH (only if we're going to call it). -------------
# --skip-pull skips this; lets the operator run on an offline build
# machine when they've already pulled models in advance.

if [[ -n "$DESTINATION" ]]; then
    write_step "Checking destination filesystem"
    check_destination_filesystem "$DESTINATION"
    echo "  OK"
fi

if (( SKIP_PULL == 0 )); then
    write_step "Verifying Ollama is on PATH"
    if ! command -v ollama >/dev/null 2>&1; then
        echo "ERROR: Ollama not found on PATH." >&2
        echo "       Install from https://ollama.com/download/linux first," >&2
        echo "       or pass --skip-pull if your models are already pulled." >&2
        exit 1
    fi
fi

# 2. Pull models -----------------------------------------------------------

if (( SKIP_PULL == 0 )); then
    for m in "${MODELS[@]}"; do
        write_step "Pulling $m"
        if ! ollama pull "$m"; then
            echo "ERROR: ollama pull $m failed. Check connectivity and try again." >&2
            exit 1
        fi
    done
else
    echo "Skipping 'ollama pull' (per --skip-pull)"
fi

# 3. Build the bundle ------------------------------------------------------

if (( SKIP_BUILD == 0 )); then
    write_step "Building air-gapped bundle (${#MODELS[@]} model(s))"
    pkg_args=( --models "$(IFS=,; echo "${MODELS[*]}")" --ollama-bundle "$OLLAMA_BUNDLE" )
    if (( in_place_build )); then
        pkg_args+=( --output-root "$DESTINATION" )
    fi
    "${SCRIPTS_DIR}/package-airgapped.sh" "${pkg_args[@]}"
else
    echo "Skipping bundle build (per --skip-build)"
fi

if [[ ! -d "$BUNDLE_SRC" ]]; then
    echo "ERROR: expected bundle at $BUNDLE_SRC but it does not exist." >&2
    echo "       Did the build step run?" >&2
    exit 1
fi

# 4. Write version.json + manifest.json -----------------------------------
# Stamps the bundle with build provenance (git SHA + timestamp + model
# list) and a SHA-256 manifest of every file. install.sh verifies the
# manifest before copying onto the workstation so a bad USB transfer
# fails loudly instead of producing a silently-corrupt install.

write_step "Stamping version + writing SHA-256 manifest"

git_sha="unknown"
git_branch="unknown"
if command -v git >/dev/null 2>&1; then
    if g=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null); then git_sha="$g"; fi
    if b=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null); then git_branch="$b"; fi
fi

build_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Build version.json + manifest.json in a single Python pass so we
# don't shell out for every file. mirrors prepare-bundle.ps1 logic.
python3 - "$BUNDLE_SRC" "$git_sha" "$git_branch" "$build_timestamp" "${MODELS[@]}" <<'PY'
import hashlib
import json
import os
import sys

bundle_root = sys.argv[1]
git_sha = sys.argv[2]
git_branch = sys.argv[3]
build_timestamp = sys.argv[4]
models = list(sys.argv[5:])

version_payload = {
    "bundle_format_version": 1,
    "build_timestamp": build_timestamp,
    "git_sha": git_sha,
    "git_branch": git_branch,
    "models": models,
}
version_path = os.path.join(bundle_root, "version.json")
with open(version_path, "w", encoding="utf-8") as f:
    json.dump(version_payload, f, indent=2)
    f.write("\n")

manifest_path = os.path.join(bundle_root, "manifest.json")
files = []
for dirpath, _, filenames in os.walk(bundle_root):
    for name in filenames:
        full = os.path.join(dirpath, name)
        if os.path.realpath(full) == os.path.realpath(manifest_path):
            continue
        rel = os.path.relpath(full, bundle_root).replace(os.sep, "/")
        files.append((rel, full))
files.sort(key=lambda p: p[0])

manifest_entries = {}
for rel, full in files:
    h = hashlib.sha256()
    with open(full, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    manifest_entries[rel] = f"sha256:{h.hexdigest()}"

manifest_payload = {
    "manifest_version": 1,
    "git_sha": git_sha,
    "created_at": build_timestamp,
    "files": manifest_entries,
}
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest_payload, f, indent=2)
    f.write("\n")

print(f"  version.json: git {git_sha} (branch {git_branch})")
print(f"  manifest.json: {len(manifest_entries)} files hashed")
PY

# 5. Copy to external drive ------------------------------------------------

if [[ -n "$DESTINATION" ]]; then
    mkdir -p "$DESTINATION"
    dest_path="${DESTINATION}/InscriptionSuite-Airgapped-Linux"
    if [[ "$BUNDLE_SRC" == "$dest_path" ]]; then
        echo "  Bundle was staged in place at $dest_path; skipping copy."
    else
        if [[ -d "$dest_path" ]]; then
            write_step "Replacing existing $dest_path"
            rm -rf "$dest_path"
        fi
        write_step "Copying bundle to $dest_path"
        cp -r "$BUNDLE_SRC" "$dest_path"
    fi
    final_path="$dest_path"
else
    final_path="$BUNDLE_SRC"
fi

# 6. Report ----------------------------------------------------------------

total_bytes=$(du -sb "$final_path" | awk '{print $1}')
total_gb=$(python3 -c "print(f'{${total_bytes}/(1024**3):.2f}')")

echo
echo "Bundle ready"
echo "  Path: $final_path"
echo "  Size: $total_gb GB"
echo
echo "Next: take the folder to the air-gapped Linux workstation and run"
echo "      ./install.sh from inside it (or test in place by running"
echo "      ./start-suite.sh straight from this folder)."
