#!/usr/bin/env bash
# Braving — Release Mode Source Preparation Script
# Enforces strict Release Mode determinism:
#   BRAVE_VERSION -> exact matching brave-core release -> exact pinned Chromium revision
#   NO arbitrary overrides permitted.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BRAVE_VERSION="${1:-${BRAVE_VERSION:-}}"

echo "========================================================"
echo " Braving Source Preparation (RELEASE MODE)"
echo " Rule          : Exact brave-core -> Exact Chromium"
echo "========================================================"

# Step 0: Clean stale metadata and resolve upstream release versions
rm -f "${REPO_ROOT}/metadata/releases"/*.yaml "${REPO_ROOT}/metadata"/upstream-*.yaml "${REPO_ROOT}/build.env"
python3 "${REPO_ROOT}/scripts/core/resolve-versions.py" "${BRAVE_VERSION}" --repo-root="${REPO_ROOT}"

# Load resolved dynamic environment
# shellcheck source=/dev/null
source "${REPO_ROOT}/build.env"
BRAVE_VERSION="${DYNAMIC_BRAVE_VERSION}"
BRAVE_CORE_COMMIT="${DYNAMIC_BRAVE_CORE_COMMIT}"

WORKSPACE_DIR="${WORKSPACE_DIR:-${CI_PROJECT_DIR:-$PWD}/build-workspace}"
SRC_DIR="${WORKSPACE_DIR}/src"
BRAVE_DIR="${SRC_DIR}/brave"

echo ""
echo "Phase 1: Preparing Source in ${WORKSPACE_DIR}"
mkdir -p "${WORKSPACE_DIR}"

# Step 1: Fetch exact brave-core revision (zero history)
LOCAL_CORE="${LOCAL_BRAVE_CORE_DIR:-/run/media/pc/D/brave-core}"

fetch_brave_core() {
  local fetched=false
  if [[ -d "${LOCAL_CORE}/.git" ]]; then
    if git -C "${BRAVE_DIR}" fetch --depth 1 "${LOCAL_CORE}" "${BRAVE_CORE_COMMIT}" 2>/dev/null; then
      fetched=true
    fi
  fi
  if [[ "${fetched}" != true ]]; then
    git -C "${BRAVE_DIR}" fetch --depth 1 origin "refs/tags/v${BRAVE_VERSION}:refs/tags/v${BRAVE_VERSION}" 2>/dev/null || \
    git -C "${BRAVE_DIR}" fetch --depth 1 origin "${BRAVE_CORE_COMMIT}"
  fi
  git -C "${BRAVE_DIR}" reset --hard FETCH_HEAD
  git -C "${BRAVE_DIR}" clean -ffd
}

if [[ ! -d "${BRAVE_DIR}/.git" ]]; then
  echo "Fetching clean brave-core at exact revision with NO history..."
  mkdir -p "${BRAVE_DIR}"
  git init "${BRAVE_DIR}"
  git -C "${BRAVE_DIR}" config advice.detachedHead false
  git -C "${BRAVE_DIR}" remote add origin "https://github.com/brave/brave-core.git"
  fetch_brave_core
else
  echo "brave-core directory already exists, verifying commit..."
  CURRENT_COMMIT=$(git -C "${BRAVE_DIR}" rev-parse "HEAD^{commit}" 2>/dev/null || echo "")
  TARGET_COMMIT=$(git -C "${BRAVE_DIR}" rev-parse "${BRAVE_CORE_COMMIT}^{commit}" 2>/dev/null || echo "${BRAVE_CORE_COMMIT}")
  if [[ -n "${CURRENT_COMMIT}" && "${CURRENT_COMMIT}" == "${TARGET_COMMIT}" ]]; then
    echo "Existing brave-core is already at target revision ${CURRENT_COMMIT}, resetting to clean state..."
    git -C "${BRAVE_DIR}" reset --hard "${CURRENT_COMMIT}"
    git -C "${BRAVE_DIR}" clean -ffd
  else
    echo "Existing brave-core is at ${CURRENT_COMMIT}, fetching exact revision ${BRAVE_CORE_COMMIT}..."
    fetch_brave_core
  fi
fi

# Step 2: Apply Braving git patches to brave-core
echo ""
echo "Applying Braving patches to brave-core..."
bash "${REPO_ROOT}/scripts/core/apply-patches.sh" "${BRAVE_DIR}"

# Step 3: Apply GN-only programmatic fixes
echo ""
echo "Applying GN build fixes..."
python3 "${REPO_ROOT}/scripts/core/apply-features.py" "${BRAVE_DIR}" --strict

# Step 4: Apply Braving branding overlay and vector assets to brave-core
echo ""
bash "${REPO_ROOT}/scripts/core/apply-assets.sh" "${BRAVE_DIR}"

# Step 5: Apply Braving UI string branding across GRD/GRDP/XTB and Android XML resources
echo ""
echo "Applying Braving UI string branding..."
python3 "${REPO_ROOT}/scripts/core/apply-branding.py" "${BRAVE_DIR}" --strict

echo ""
echo "Phase 1: brave-core Source Preparation Complete."

# Step 6: Package prepared brave-core for guaranteed artifact transfer across pipeline stages
IN_CI="${CI:-false}"
if [[ -n "${GITLAB_CI:-}" || -n "${CI_JOB_ID:-}" ]]; then
  IN_CI=true
fi

if [[ "${IN_CI}" == true || "${PACKAGE_BRAVE_ARCHIVE:-false}" == true ]]; then
  rm -f "${WORKSPACE_DIR}"/brave-src-*.tar.gz
  BRAVE_ARCHIVE="${WORKSPACE_DIR}/brave-src-${DYNAMIC_BRAVE_VERSION}.tar.gz"
  echo ""
  echo "Packaging prepared brave-core to ${BRAVE_ARCHIVE}..."
  tar --exclude='.git' --exclude='node_modules' -czf "${BRAVE_ARCHIVE}" -C "${SRC_DIR}" brave
  echo "brave-core packaged successfully ($(du -h "${BRAVE_ARCHIVE}" | cut -f1))."
fi


