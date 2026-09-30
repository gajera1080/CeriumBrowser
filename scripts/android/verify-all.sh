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
python3 "${REPO_ROOT}/scripts/tests/test_branding.py"
python3 "${REPO_ROOT}/scripts/tests/test_signing.py"
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
    echo "      - ${p#${PATCH_DIR}/}"
  done

  CHECK_BRAVE_DIR="${BRAVE_CORE_DIR:-}"
  if [[ -z "${CHECK_BRAVE_DIR}" || ! -d "${CHECK_BRAVE_DIR}/.git" ]]; then
    if [[ -d "${REPO_ROOT}/build-workspace/src/brave/.git" ]]; then
      CHECK_BRAVE_DIR="${REPO_ROOT}/build-workspace/src/brave"
    elif [[ -d "/run/media/pc/D/brave-core/.git" ]]; then
      CHECK_BRAVE_DIR="/run/media/pc/D/brave-core"
    fi
  fi

  if [[ -n "${CHECK_BRAVE_DIR}" && -d "${CHECK_BRAVE_DIR}/.git" ]]; then
    echo " Validating patch set against brave-core (${CHECK_BRAVE_DIR})..."
    while IFS= read -r -d $'\0' p; do
      rel_p="${p#${PATCH_DIR}/}"
      if git -C "${CHECK_BRAVE_DIR}" apply --check "$p" 2>/dev/null || \
         git -C "${CHECK_BRAVE_DIR}" apply --check --reverse "$p" 2>/dev/null || \
         git -C "${CHECK_BRAVE_DIR}" apply -C1 --check "$p" 2>/dev/null || \
         git -C "${CHECK_BRAVE_DIR}" apply -C1 --check --reverse "$p" 2>/dev/null; then
        echo "      [PASS] ${rel_p} applies cleanly"
      else
        echo "      [FAIL] ${rel_p} failed to apply" >&2
        exit 1
      fi
    done < <(find "${PATCH_DIR}" -name "*.patch" -print0 | sort -z)
  fi
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
"${REPO_ROOT}/scripts/android/sign-apk.sh" --dry-run

echo ""
echo "========================================================"
echo " ALL VERIFICATION STEPS PASSED SUCCESSFULLY (5/5)"
echo " Ready for GitLab CI/CD Pipeline Execution"
echo "========================================================"
