#!/usr/bin/env bash
# Cerium Dynamic Master Verification Suite
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
echo " Starting Cerium Master Verification Suite"
echo " Target Version: ${TARGET_VERSION}"
echo "========================================================"

echo ""
echo "=== Step 1/6: Manifest & Upstream Metadata Validation ==="
python3 "${REPO_ROOT}/scripts/tests/test_manifest.py"

echo ""
echo "=== Step 2/6: Mutator Script Syntax & Unit Tests Verification ==="
python3 -m py_compile "${REPO_ROOT}/scripts/core"/*.py "${REPO_ROOT}/scripts/mutators"/*.py "${REPO_ROOT}/scripts/mutators"/**/*.py
python3 "${REPO_ROOT}/scripts/tests/test_mutators.py"
python3 "${REPO_ROOT}/scripts/tests/test_cache_scripts.py"
python3 "${REPO_ROOT}/scripts/tests/test_branding.py"
echo " [OK] Python mutators and unit tests verified successfully."

echo ""
echo "=== Step 3/6: CI Automation Script Verification ==="
CI_SCRIPTS_DIR="${REPO_ROOT}/scripts/ci"
if [[ -d "${CI_SCRIPTS_DIR}" ]]; then
  for script in "${CI_SCRIPTS_DIR}"/*.sh; do
    if [[ -f "${script}" ]]; then
      bash -n "${script}"
      echo "      [PASS] $(basename "${script}") syntax OK"
    fi
  done
  python3 "${REPO_ROOT}/scripts/tests/test_ci_automation.py"
  echo " [OK] CI automation scripts and unit tests verified successfully."
else
  echo " [SKIP] No scripts/ci/ directory found."
fi

echo ""
echo "=== Step 4/6: Patch Set Verification ==="
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

  CHECK_BRAVE_DIRS=()
  if [[ -n "${BRAVE_CORE_DIR:-}" && -d "${BRAVE_CORE_DIR}/.git" ]]; then
    CHECK_BRAVE_DIRS+=("${BRAVE_CORE_DIR}")
  else
    if [[ -d "/run/media/pc/D/brave-core/.git" ]]; then
      CHECK_BRAVE_DIRS+=("/run/media/pc/D/brave-core")
    fi
    if [[ -d "${REPO_ROOT}/build-workspace/src/brave/.git" && "${REPO_ROOT}/build-workspace/src/brave" != "/run/media/pc/D/brave-core" ]]; then
      CHECK_BRAVE_DIRS+=("${REPO_ROOT}/build-workspace/src/brave")
    fi
  fi

  for target_dir in "${CHECK_BRAVE_DIRS[@]}"; do
    upstream_ver=$(git -C "${target_dir}" describe --tags 2>/dev/null || git -C "${target_dir}" log -1 --format="%h (%s)" 2>/dev/null || echo "unknown")
    echo " Validating patch set against brave-core (${target_dir} @ ${upstream_ver})..."
    "${REPO_ROOT}/scripts/core/apply-patches.sh" "${target_dir}" --check
  done
else
  echo " [OK] No .patch files found in ${PATCH_DIR}/ (all modifications handled via mutators)."
fi

echo ""
echo "=== Step 5/6: Branding & Asset Verification ==="
"${REPO_ROOT}/scripts/core/verify-branding.sh"

echo ""
echo "=== Step 6/6: Build Orchestration & Dry-Run Validation ==="
MANIFEST_FILE="${REPO_ROOT}/metadata/releases/${TARGET_VERSION}.yaml"
if [[ ! -f "${MANIFEST_FILE}" ]]; then
  MANIFEST_FILE=$(ls -t "${REPO_ROOT}/metadata/releases"/*.yaml 2>/dev/null | head -n 1 || true)
fi

if [[ -n "${MANIFEST_FILE}" && -f "${MANIFEST_FILE}" ]]; then
  "${REPO_ROOT}/scripts/platforms/android/build.sh" --manifest="${MANIFEST_FILE}" --arch="${TARGET_ARCH:-arm64}" --release --dry-run
  if [[ -f "${REPO_ROOT}/scripts/platforms/windows/build.sh" ]]; then
    "${REPO_ROOT}/scripts/platforms/windows/build.sh" --manifest="${MANIFEST_FILE}" --arch="x64" --release --dry-run
    "${REPO_ROOT}/scripts/platforms/windows/build.sh" --manifest="${MANIFEST_FILE}" --arch="arm64" --release --dry-run
  fi
  if [[ -f "${REPO_ROOT}/scripts/platforms/windows/package.sh" ]]; then
    "${REPO_ROOT}/scripts/platforms/windows/package.sh" --arch="x64" --dry-run
    "${REPO_ROOT}/scripts/platforms/windows/package.sh" --arch="arm64" --dry-run
  fi
else
  echo " [SKIP] No release manifest found for dry-run validation."
fi
"${REPO_ROOT}/scripts/platforms/android/package.sh" --dry-run

echo ""
echo "========================================================"
echo " ALL VERIFICATION STEPS PASSED SUCCESSFULLY (6/6)"
echo "========================================================"
