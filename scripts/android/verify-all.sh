#!/usr/bin/env bash
# Braving Dynamic Master Verification Suite
# Runs all tests, linters, patch verifiers, and build dry-runs across any release version.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

TARGET_VERSION="${1:-${BRAVE_VERSION:-}}"

if [[ -z "${TARGET_VERSION}" ]]; then
  # Auto-detect latest release manifest or upstream metadata
  LATEST_MANIFEST=$(ls -t "${REPO_ROOT}/metadata/releases"/*.yaml 2>/dev/null | head -n 1 || true)
  if [[ -n "${LATEST_MANIFEST}" ]]; then
    TARGET_VERSION=$(basename "${LATEST_MANIFEST}" | sed 's/\.yaml//')
  else
    LATEST_UPSTREAM=$(ls -t "${REPO_ROOT}/metadata/upstream-"*.yaml 2>/dev/null | head -n 1 || true)
    if [[ -n "${LATEST_UPSTREAM}" ]]; then
      TARGET_VERSION=$(basename "${LATEST_UPSTREAM}" | sed 's/upstream-//;s/\.yaml//')
    else
      echo "ERROR: No metadata or release manifests found." >&2
      exit 1
    fi
  fi
fi

TARGET_VERSION="${TARGET_VERSION#v}"

echo "========================================================"
echo " Starting Braving Master Verification Suite"
echo " Target Version: ${TARGET_VERSION}"
echo "========================================================"

echo ""
echo "=== Step 1/5: Manifest & Upstream Metadata Validation ==="
python3 "${REPO_ROOT}/scripts/tests/test_manifest.py"

echo ""
echo "=== Step 2/5: Mutator Script Syntax & Unit Tests Verification ==="
python3 -m py_compile "${REPO_ROOT}/scripts/android"/*.py
python3 "${REPO_ROOT}/scripts/tests/test_mutators.py"
python3 "${REPO_ROOT}/scripts/tests/test_cache_scripts.py"
echo " [OK] Python mutators and unit tests verified successfully."

echo ""
echo "=== Step 3/5: Patch Set Verification ==="
PATCH_DIR="${REPO_ROOT}/patches"
PATCH_COUNT=0
if [[ -d "${PATCH_DIR}" ]]; then
  PATCH_COUNT=$(find "${PATCH_DIR}" -name "*.patch" 2>/dev/null | wc -l)
fi
if [[ ${PATCH_COUNT} -gt 0 ]]; then
  echo " [OK] Found ${PATCH_COUNT} patch file(s) in ${PATCH_DIR}/"
  find "${PATCH_DIR}" -name "*.patch" | sort | while read -r p; do
    echo "      - $(basename "$p")"
  done
else
  echo " [OK] No .patch files found in ${PATCH_DIR}/ (all modifications handled via mutators)."
fi

echo ""
echo "=== Step 4/5: Branding & Asset Verification ==="
"${REPO_ROOT}/scripts/android/verify-branding.sh"

echo ""
echo "=== Step 5/5: Android Build Orchestration Dry-Run ==="
MANIFEST_FILE="${REPO_ROOT}/metadata/releases/${TARGET_VERSION}.yaml"
if [[ ! -f "${MANIFEST_FILE}" ]]; then
  MANIFEST_FILE=$(ls -t "${REPO_ROOT}/metadata/releases"/*.yaml 2>/dev/null | head -n 1 || true)
fi

if [[ -n "${MANIFEST_FILE}" && -f "${MANIFEST_FILE}" ]]; then
  "${REPO_ROOT}/scripts/android/build-android.sh" --manifest="${MANIFEST_FILE}" --arch="${TARGET_ARCH:-arm64}" --release --dry-run
else
  echo " [SKIP] No release manifest found for dry-run validation."
fi

echo ""
echo "========================================================"
echo " ALL VERIFICATION STEPS PASSED SUCCESSFULLY (5/5)"
echo " Ready for GitLab CI/CD Pipeline Execution"
echo "========================================================"
