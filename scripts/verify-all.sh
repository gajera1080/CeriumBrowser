#!/usr/bin/env bash
# Braving Master Verification Suite
# Runs all tests, linters, patch verifiers, and build dry-runs in a single pass.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================"
echo " Starting Braving Master Verification Suite"
echo "========================================================"

echo ""
echo "=== Step 1/5: Manifest & Upstream Metadata Validation ==="
python3 "${REPO_ROOT}/tests/test_manifest.py"

echo ""
echo "=== Step 2/5: Patch Format & Syntax Verification ==="
python3 "${REPO_ROOT}/tests/test_patches.py"

echo ""
echo "=== Step 3/5: Isolated Upstream Patch Application ==="
"${REPO_ROOT}/scripts/verify-patches.sh" "1.94.120"

echo ""
echo "=== Step 4/5: Branding & Asset Verification ==="
"${REPO_ROOT}/scripts/verify-branding.sh"

echo ""
echo "=== Step 5/5: Android Build Orchestration Dry-Run ==="
"${REPO_ROOT}/scripts/build-android.sh" --manifest="${REPO_ROOT}/metadata/releases/1.94.120.yaml" --arch=arm64 --release --dry-run

echo ""
echo "========================================================"
echo " ALL VERIFICATION STEPS PASSED SUCCESSFULLY (5/5)"
echo " Ready for GitLab CI/CD Pipeline Execution"
echo "========================================================"
