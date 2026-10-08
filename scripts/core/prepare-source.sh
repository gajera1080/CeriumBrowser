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

# Step 6: Pre-install brave-core node dependencies so they are cached for downstream runners
if command -v pnpm >/dev/null 2>&1 && [[ -f "${BRAVE_DIR}/package.json" ]]; then
  echo ""
  echo "Pre-installing brave-core node dependencies..."
  (cd "${BRAVE_DIR}" && pnpm install --frozen-lockfile)
fi

# Step 7: Bootstrap depot_tools in workspace for caching
DEPOT_TOOLS_DIR="${WORKSPACE_DIR}/depot_tools"
if [[ ! -d "${DEPOT_TOOLS_DIR}" ]]; then
  echo ""
  echo "Bootstrapping depot_tools in ${DEPOT_TOOLS_DIR}..."
  git clone --depth 1 "https://chromium.googlesource.com/chromium/tools/depot_tools.git" "${DEPOT_TOOLS_DIR}"
  "${DEPOT_TOOLS_DIR}/ensure_bootstrap" || "${DEPOT_TOOLS_DIR}/update_depot_tools"
fi
export PATH="${DEPOT_TOOLS_DIR}:${PATH}"
export DEPOT_TOOLS_UPDATE=0

# Step 8: Prepare versioned base Chromium archive
CHROMIUM_VERSION="${DYNAMIC_CHROMIUM_VERSION}"
CHROMIUM_COMMIT="${DYNAMIC_CHROMIUM_COMMIT}"
CHROMIUM_ARCHIVE="${WORKSPACE_DIR}/chromium-src-${CHROMIUM_VERSION}.tar.xz"

# Purge older archives from different versions to preserve cache space
find "${WORKSPACE_DIR}" -maxdepth 1 -name "chromium-src-*.tar.xz" ! -name "chromium-src-${CHROMIUM_VERSION}.tar.xz" -delete 2>/dev/null || true

if [[ -f "${CHROMIUM_ARCHIVE}" ]]; then
  echo ""
  echo "Found existing base Chromium archive: ${CHROMIUM_ARCHIVE}"
  echo "Skipping Chromium download and compression (cache hit)."
else
  echo ""
  echo "Fetching clean base Chromium (${CHROMIUM_VERSION} @ ${CHROMIUM_COMMIT})..."
  if [[ ! -d "${SRC_DIR}/.git" ]]; then
    mkdir -p "${SRC_DIR}"
    git init "${SRC_DIR}"
    git -C "${SRC_DIR}" config advice.detachedHead false
    git -C "${SRC_DIR}" remote add origin "https://chromium.googlesource.com/chromium/src.git" 2>/dev/null || git -C "${SRC_DIR}" remote set-url origin "https://chromium.googlesource.com/chromium/src.git"
    git -C "${SRC_DIR}" fetch --depth 1 origin "refs/tags/${CHROMIUM_VERSION}:refs/tags/${CHROMIUM_VERSION}" 2>/dev/null || \
    git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
    git -C "${SRC_DIR}" reset --hard FETCH_HEAD
    git -C "${SRC_DIR}" clean -ffd
  else
    git -C "${SRC_DIR}" reset --hard HEAD
    git -C "${SRC_DIR}" clean -ffd
  fi

  echo "Pre-syncing Linux host compiler toolchains..."
  python3 "${SRC_DIR}/tools/clang/scripts/update.py"
  python3 "${SRC_DIR}/tools/rust/update_rust.py"

  # Pre-install GN binary into buildtools/linux64
  mkdir -p "${SRC_DIR}/buildtools/linux64"
  if command -v cipd >/dev/null 2>&1 && [[ ! -x "${SRC_DIR}/buildtools/linux64/gn" ]]; then
    cipd install "gn/gn/linux-amd64" "git_revision:c7ffaf80713afbe5a4f4d95a605c0a98084374de" -root "${SRC_DIR}/buildtools/linux64" || true
    chmod +x "${SRC_DIR}/buildtools/linux64/gn" 2>/dev/null || true
  fi

  echo "Compressing base Chromium and toolchains into ${CHROMIUM_ARCHIVE}..."
  tar --exclude='src/brave' -cf - -C "${WORKSPACE_DIR}" src | xz -T0 -3 > "${CHROMIUM_ARCHIVE}"
  echo "Chromium archive complete: $(du -h "${CHROMIUM_ARCHIVE}" | cut -f1)"
fi

echo ""
echo "Phase 1: Source Preparation Complete."
