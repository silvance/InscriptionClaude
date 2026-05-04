#!/usr/bin/env bash
# Install the air-gapped Inscription suite bundle to a permanent
# location on this Linux workstation.
#
# Mirrors install.ps1 (Windows). Run from inside the bundle directory
# (e.g. /media/usb/InscriptionSuite-Airgapped/) on the offline
# workstation. Copies the bundle to a stable per-user path and creates
# a .desktop launcher entry.
#
# No root required -- everything goes under $HOME. To install
# system-wide (multiple users), pass --install-root /opt/InscriptionSuite
# and run with sudo.
#
# User configuration / saved cases are NOT touched -- those live under
# $XDG_DATA_HOME (or ~/.local/share/Inscription, ~/.local/share/CaseGuide,
# ~/.local/share/CaseForge), and wherever the operator chose to keep
# case folders. Re-running the installer with --force overwrites the
# binaries but preserves all of that.
#
# Usage:
#     ./install.sh                              # default per-user
#     ./install.sh --desktop-shortcut           # also drop a desktop file
#     ./install.sh --force                      # overwrite without prompting
#     ./install.sh --install-root /opt/InscriptionSuite  # system-wide
#     ./install.sh --skip-verify                # skip the SHA-256 check

set -euo pipefail

DEFAULT_INSTALL_ROOT="${HOME}/.local/share/InscriptionSuite"
INSTALL_ROOT="$DEFAULT_INSTALL_ROOT"
FORCE=0
DESKTOP_SHORTCUT=0
SKIP_VERIFY=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install-root)
            INSTALL_ROOT="$(realpath -m "$2")"
            shift 2
            ;;
        --force)
            FORCE=1
            shift
            ;;
        --desktop-shortcut)
            DESKTOP_SHORTCUT=1
            shift
            ;;
        --skip-verify)
            SKIP_VERIFY=1
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

BUNDLE_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

write_step() {
    echo
    echo "==> $1"
}

# 1. Verify we are inside a real bundle --------------------------------------

write_step "Checking bundle integrity"
EXPECTED=("Inscription" "CaseForge" "CaseGuide" "ollama" "models" "start-suite.sh")
for item in "${EXPECTED[@]}"; do
    if [[ ! -e "$BUNDLE_SRC/$item" ]]; then
        echo "ERROR: install.sh must run from inside the bundle directory." >&2
        echo "       Missing: $item" >&2
        echo "       Are you inside InscriptionSuite-Airgapped/?" >&2
        exit 1
    fi
done
echo "  Bundle source: $BUNDLE_SRC"

# 1a. Refuse same/overlapping source and destination ------------------------
# Stops "right-click install.sh from inside an existing install" from
# wiping the bundle out from under itself.
bundle_resolved="$(realpath "$BUNDLE_SRC")"
install_normalised="$(realpath -m "$INSTALL_ROOT")"
if [[ "$bundle_resolved" == "$install_normalised" ]]; then
    echo "ERROR: source ($BUNDLE_SRC) and --install-root ($INSTALL_ROOT) are the same path." >&2
    echo "       Re-run install.sh from the original bundle (e.g. on USB), or pass a different --install-root." >&2
    exit 1
fi
case "$install_normalised/" in
    "$bundle_resolved"/*)
        echo "ERROR: --install-root is inside the bundle. Pick a destination outside it." >&2
        exit 1 ;;
esac
case "$bundle_resolved/" in
    "$install_normalised"/*)
        echo "ERROR: bundle is inside --install-root. Pick a destination that's not a parent of the bundle." >&2
        exit 1 ;;
esac

# 1b. Verify SHA-256 manifest -----------------------------------------------
# A USB transfer can occasionally truncate or corrupt a file; the
# bundle ships with a manifest.json (sha256 of every file as written
# by prepare-bundle.sh) so we can detect that before installing.
# Older bundles built before this feature have no manifest -- fall
# through with a warning rather than a hard error.

manifest_path="$BUNDLE_SRC/manifest.json"
version_path="$BUNDLE_SRC/version.json"

if (( SKIP_VERIFY )); then
    write_step "Skipping bundle integrity check (per --skip-verify)"
elif [[ ! -f "$manifest_path" ]]; then
    write_step "No manifest.json in bundle -- skipping integrity check"
    echo "  (Bundles built before manifest support went in. Rebuild with prepare-bundle.sh to get one.)"
else
    write_step "Verifying bundle integrity (SHA-256)"
    # Use python3 for JSON parsing -- jq isn't universally installed
    # on forensic Linux boxes, but Python is. The Python script writes
    # one "<expected>  <relative-path>" line per file, which sha256sum
    # reads in --check mode for the actual hash compare.
    sha_list="$(mktemp)"
    expected_paths="$(mktemp)"
    trap 'rm -f "$sha_list" "$expected_paths"' EXIT

    python3 - "$manifest_path" "$expected_paths" > "$sha_list" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    manifest = json.load(f)

paths_out = open(sys.argv[2], "w", encoding="utf-8")
for rel, h in manifest.get("files", {}).items():
    if not h.startswith("sha256:"):
        sys.stderr.write(f"manifest.json: bad hash format for {rel}\n")
        sys.exit(1)
    print(f"{h[len('sha256:'):]}  {rel}")
    paths_out.write(rel.lower() + "\n")
PY

    # sha256sum --check expects a relative-path file; cd into the
    # bundle so the paths in $sha_list resolve correctly. --quiet
    # only prints lines for failures, and the trailing summary
    # ("WARNING: N computed checksum did NOT match") is on stderr.
    if ! ( cd "$BUNDLE_SRC" && sha256sum --check --quiet "$sha_list" ) > /tmp/install-sh-check.log 2>&1; then
        # Each FAILED file produces one "<path>: FAILED" line on stdout;
        # the summary "WARNING:" line is on stderr but ends up in the
        # same file because of 2>&1. Count only the FAILED lines.
        bad_count=$(grep -c ': FAILED$' /tmp/install-sh-check.log || true)
        echo
        echo "Bundle integrity check failed:" >&2
        cat /tmp/install-sh-check.log >&2
        echo
        echo "ERROR: Bundle is corrupt or tampered -- $bad_count file(s) failed verification." >&2
        echo "       Rebuild and re-copy onto the USB." >&2
        exit 1
    fi
    file_count=$(wc -l < "$sha_list")

    # Pass 2: every file actually present is in the manifest. Drops
    # an extra-file attack on the bundle (and surfaces a sloppy
    # hand-edit). manifest.json itself isn't in the manifest by
    # design -- exclude it explicitly. Computed in Python to keep
    # the path-comparison readable and to handle non-ASCII paths
    # without grep flag tuning.
    unexpected_count=$(python3 - "$expected_paths" "$BUNDLE_SRC" <<'PY'
import os
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    expected = {line.strip() for line in f if line.strip()}

bundle_root = sys.argv[2]
unexpected = []
for dirpath, _, filenames in os.walk(bundle_root):
    for name in filenames:
        full = os.path.join(dirpath, name)
        rel = os.path.relpath(full, bundle_root).replace(os.sep, "/")
        if rel == "manifest.json":
            continue
        if rel.lower() not in expected:
            unexpected.append(rel)

for u in unexpected:
    print(f"  unexpected file (not in manifest): {u}", file=sys.stderr)
print(len(unexpected))
PY
)
    if (( unexpected_count > 0 )); then
        echo
        echo "ERROR: bundle has $unexpected_count file(s) not listed in the manifest." >&2
        echo "       Rebuild from a clean checkout." >&2
        exit 1
    fi
    echo "  OK ($file_count files verified, no unexpected files)"
    trap - EXIT
    rm -f "$sha_list" "$expected_paths"
fi

# 1c. Surface bundle version -------------------------------------------------
if [[ -f "$version_path" ]]; then
    sha=$(python3 -c "
import json, sys
try:
    with open('$version_path', encoding='utf-8') as f:
        v = json.load(f)
    g = v.get('git_sha', 'unknown') or 'unknown'
    print(g[:8])
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")
    built=$(python3 -c "
import json, sys
try:
    with open('$version_path', encoding='utf-8') as f:
        v = json.load(f)
    print(v.get('build_timestamp', 'unknown') or 'unknown')
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")
    echo "  Bundle version: $sha (built $built)"
fi

# 2. Confirm + clear destination ---------------------------------------------

if [[ -d "$INSTALL_ROOT" ]]; then
    if (( FORCE == 0 )); then
        echo
        echo "$INSTALL_ROOT already exists."
        read -r -p "Overwrite? (y/N) " reply
        case "$reply" in
            [yY]*) ;;
            *) echo "Cancelled. Existing install left untouched."; exit 0 ;;
        esac
    fi
fi

# 3. Stage the new copy to a sibling directory, then atomic swap ------------
# Same two-phase pattern install.ps1 uses: copy to <root>.new, swap
# the old aside to <root>.old, rename the new in. A copy failure
# mid-stream (USB unplugged, disk full) leaves the previous install
# intact rather than wiping it before the new one is fully landed.

staging_root="${INSTALL_ROOT}.new"
rollback_root="${INSTALL_ROOT}.old"
if [[ -d "$staging_root" ]]; then
    write_step "Removing leftover staging dir from a prior aborted install"
    rm -rf "$staging_root"
fi
if [[ -d "$rollback_root" ]]; then
    write_step "Removing leftover rollback dir from a prior aborted install"
    rm -rf "$rollback_root"
fi

write_step "Staging new install to $staging_root"
parent="$(dirname "$INSTALL_ROOT")"
if [[ ! -d "$parent" ]]; then
    mkdir -p "$parent"
fi
if ! cp -r "$BUNDLE_SRC" "$staging_root"; then
    rm -rf "$staging_root" 2>/dev/null || true
    echo "ERROR: copy to staging dir failed. The previous install at $INSTALL_ROOT is untouched." >&2
    exit 1
fi

# Ensure the executable bits made the trip; cp -r preserves them on
# Linux but be explicit so a fat-fs source (e.g. exFAT USB) can't
# silently strip them.
chmod +x "$staging_root/start-suite.sh" 2>/dev/null || true
for app in Inscription/Inscription CaseForge/CaseForge CaseGuide/CaseGuide ollama/bin/ollama; do
    if [[ -f "$staging_root/$app" ]]; then
        chmod +x "$staging_root/$app" 2>/dev/null || true
    fi
done

total_bytes=$(du -sb "$staging_root" | awk '{print $1}')
total_gb=$(python3 -c "print(f'{${total_bytes}/(1024**3):.2f}')")
echo "  Staged $total_gb GB."

write_step "Swapping new install in"
if [[ -d "$INSTALL_ROOT" ]]; then
    if ! mv "$INSTALL_ROOT" "$rollback_root"; then
        rm -rf "$staging_root"
        echo "ERROR: failed to move the old install aside. Previous install at $INSTALL_ROOT is intact." >&2
        exit 1
    fi
fi
if ! mv "$staging_root" "$INSTALL_ROOT"; then
    # Roll back: try to restore the old install we just moved aside.
    if [[ -d "$rollback_root" ]] && [[ ! -d "$INSTALL_ROOT" ]]; then
        mv "$rollback_root" "$INSTALL_ROOT" 2>/dev/null || true
    fi
    echo "ERROR: failed to swap the new install in. Previous install should still be at $INSTALL_ROOT." >&2
    exit 1
fi
if [[ -d "$rollback_root" ]]; then
    rm -rf "$rollback_root" 2>/dev/null || true
fi

# 4. Create the .desktop launcher entry -------------------------------------

write_step "Writing .desktop launcher entry"
desktop_dir="${HOME}/.local/share/applications"
mkdir -p "$desktop_dir"
desktop_file="${desktop_dir}/inscription-suite.desktop"
icon_path="${INSTALL_ROOT}/Inscription/Inscription"
cat > "$desktop_file" <<EOF
[Desktop Entry]
Type=Application
Name=Inscription Suite
Comment=Inscription Suite air-gapped launcher (Inscription / CaseForge / CaseGuide)
Exec=${INSTALL_ROOT}/start-suite.sh
Icon=${icon_path}
Terminal=true
Categories=Utility;Development;
EOF
chmod 644 "$desktop_file"
echo "  $desktop_file"

# update-desktop-database is best-effort; absence of the tool is
# fine -- the file is still picked up on next desktop-environment
# refresh.
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$desktop_dir" 2>/dev/null || true
fi

# 5. Optional desktop shortcut ----------------------------------------------

if (( DESKTOP_SHORTCUT )); then
    write_step "Creating Desktop shortcut"
    desktop_root="${XDG_DESKTOP_DIR:-${HOME}/Desktop}"
    if [[ -d "$desktop_root" ]]; then
        desktop_shortcut="${desktop_root}/Inscription Suite.desktop"
        cp "$desktop_file" "$desktop_shortcut"
        chmod +x "$desktop_shortcut"
        echo "  $desktop_shortcut"
    else
        echo "  $desktop_root does not exist; skipping desktop shortcut."
    fi
fi

# 6. Final report ------------------------------------------------------------

echo
echo "Inscription Suite installed."
echo "  Location:       $INSTALL_ROOT"
echo "  App menu:       Look for 'Inscription Suite' in your applications launcher."
if (( DESKTOP_SHORTCUT )); then
    echo "  Desktop icon:   'Inscription Suite' on your desktop"
fi
echo
echo "Note: Inscription on Linux ships in degraded form -- case management,"
echo "step rewriting, and exports work; UIA capture is Windows-only."
