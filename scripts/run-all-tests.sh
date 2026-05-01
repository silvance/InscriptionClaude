#!/usr/bin/env bash
# Run pytest against all four test suites in sequence -- POSIX twin
# of run-all-tests.ps1. See that file's header for the rationale.

set -u
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SUITES=(suite_common inscription caseforge caseguide)
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"

failed=()
for suite in "${SUITES[@]}"; do
    echo
    echo "=== $suite ==="
    if ! (cd "$REPO_ROOT/$suite" && python -m pytest tests); then
        failed+=("$suite")
    fi
done

echo
if [ "${#failed[@]}" -gt 0 ]; then
    echo "FAILED: ${failed[*]}"
    exit 1
fi
echo "All suites passed."
