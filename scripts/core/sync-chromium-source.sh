#!/usr/bin/env bash
# ==============================================================================
# Braving — Base Chromium & Toolchain Source Synchronizer
# Syncs base Chromium archive and pre-bootstrapped depot_tools with GitLab
# Generic Package Registry:
#   ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-chromium-source/${CHROMIUM_VERSION}
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DOWNLOAD_ONLY=false
FORCE_REBUILD=false

for arg in "$@"; do
  case "$arg" in
    --download-only)
      DOWNLOAD_ONLY=true
      shift
      ;;
    --force)
      FORCE_REBUILD=true
      shift
      ;;
  esac
done

BUILD_ENV_FILE="${BUILD_ENV_FILE:-${REPO_ROOT}/build.env}"
if [[ -f "${BUILD_ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${BUILD_ENV_FILE}"
fi

WORKSPACE_DIR="${WORKSPACE_DIR:-${CI_PROJECT_DIR:-${REPO_ROOT}}/build-workspace}"
SRC_DIR="${WORKSPACE_DIR}/src"
DEPOT_TOOLS_DIR="${WORKSPACE_DIR}/depot_tools"

CHROMIUM_VERSION="${DYNAMIC_CHROMIUM_VERSION:-${CHROMIUM_VERSION:-}}"
if [[ -z "${CHROMIUM_VERSION}" && -f "${SRC_DIR}/chrome/VERSION" ]]; then
  CHROMIUM_VERSION=$(grep -E '^(MAJOR|MINOR|BUILD|PATCH)=' "${SRC_DIR}/chrome/VERSION" | cut -d= -f2 | paste -sd.)
fi

if [[ -z "${CHROMIUM_VERSION}" ]]; then
  echo "ERROR: CHROMIUM_VERSION could not be determined." >&2
  exit 1
fi

CHROMIUM_COMMIT="${DYNAMIC_CHROMIUM_COMMIT:-${CHROMIUM_COMMIT:-}}"
CHROMIUM_ARCHIVE="${WORKSPACE_DIR}/chromium-src-${CHROMIUM_VERSION}.tar.xz"
DEPOT_ARCHIVE="${WORKSPACE_DIR}/depot-tools.tar.xz"

# Check if GitLab CI Package Registry API is available
IN_CI=false
if [[ -n "${CI_API_V4_URL:-}" && -n "${CI_JOB_TOKEN:-}" && -n "${CI_PROJECT_ID:-}" ]]; then
  IN_CI=true
  PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-chromium-source/${CHROMIUM_VERSION}"
fi

echo "=========================================="
echo " Base Chromium Synchronizer"
echo " Chromium Version: ${CHROMIUM_VERSION}"
if [[ "${IN_CI}" == true ]]; then
  echo " Package URL     : ${PKG_URL}"
fi
echo " Download Only   : ${DOWNLOAD_ONLY}"
echo "=========================================="

# Try restoring from GitLab Generic Package Registry
if [[ "${IN_CI}" == true && "${FORCE_REBUILD}" != true ]]; then
  echo "Checking registry for package braving-chromium-source (${CHROMIUM_VERSION})..."
  HTTP_CODE=$(curl -sL -o /dev/null -w "%{http_code}" --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/checksums.sha256" || echo "000")
  if [[ "${HTTP_CODE}" == "200" ]]; then
    echo "Found braving-chromium-source (${CHROMIUM_VERSION}) in registry (HTTP 200). Restoring..."
    TMP_DIR=$(mktemp -d /tmp/chromium-sync-XXXXXX)
    trap 'rm -rf "${TMP_DIR}"' EXIT

    curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/checksums.sha256" -o "${TMP_DIR}/checksums.sha256"
    echo "Registry manifest:"
    cat "${TMP_DIR}/checksums.sha256"

    for file in $(awk '{print $2}' "${TMP_DIR}/checksums.sha256"); do
      echo "Downloading ${file}..."
      curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/${file}" -o "${TMP_DIR}/${file}"
    done

    echo "Verifying SHA256 checksums..."
    (cd "${TMP_DIR}" && sha256sum -c checksums.sha256)

    for file in $(awk '{print $2}' "${TMP_DIR}/checksums.sha256"); do
      case "${file}" in
        chromium-src-*.tar.xz)
          if [[ ! -d "${SRC_DIR}/.git" ]]; then
            echo "Unpacking base Chromium to ${WORKSPACE_DIR}..."
            tar -xf "${TMP_DIR}/${file}" -C "${WORKSPACE_DIR}"
          fi
          ;;
        depot-tools.tar.xz)
          if [[ ! -d "${DEPOT_TOOLS_DIR}" ]]; then
            echo "Unpacking depot_tools to ${WORKSPACE_DIR}..."
            tar -xf "${TMP_DIR}/${file}" -C "${WORKSPACE_DIR}"
          fi
          ;;
      esac
    done
    rm -f "${WORKSPACE_DIR}"/chromium-src-*.tar.xz "${WORKSPACE_DIR}"/depot-tools.tar.xz

    echo "Base Chromium and depot_tools restored successfully from registry."
    exit 0
  fi
  echo "braving-chromium-source (${CHROMIUM_VERSION}) not found in registry (HTTP ${HTTP_CODE})."
fi

if [[ "${DOWNLOAD_ONLY}" == true ]]; then
  if [[ -f "${CHROMIUM_ARCHIVE}" && -d "${DEPOT_TOOLS_DIR}" ]]; then
    echo "Local archives found. Proceeding with existing local source."
    if [[ ! -d "${SRC_DIR}/.git" ]]; then
      tar -xf "${CHROMIUM_ARCHIVE}" -C "${WORKSPACE_DIR}"
      rm -f "${CHROMIUM_ARCHIVE}"
    fi
    exit 0
  fi
  if [[ -d "${SRC_DIR}/.git" && -d "${DEPOT_TOOLS_DIR}" ]]; then
    echo "Unpacked Chromium source and depot_tools found. Proceeding."
    exit 0
  fi
  echo "ERROR: --download-only requested but package was not found in registry." >&2
  exit 1
fi

echo ""
echo "Fetching and constructing base Chromium source (${CHROMIUM_VERSION})..."

mkdir -p "${WORKSPACE_DIR}"
if [[ ! -d "${SRC_DIR}/.git" ]]; then
  mkdir -p "${SRC_DIR}"
  git init "${SRC_DIR}"
  git -C "${SRC_DIR}" config advice.detachedHead false
  git -C "${SRC_DIR}" remote add origin "https://chromium.googlesource.com/chromium/src.git" 2>/dev/null || git -C "${SRC_DIR}" remote set-url origin "https://chromium.googlesource.com/chromium/src.git"
  git -C "${SRC_DIR}" fetch --depth 1 origin "refs/tags/${CHROMIUM_VERSION}:refs/tags/${CHROMIUM_VERSION}" 2>/dev/null || \
  git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
  git -C "${SRC_DIR}" reset --hard FETCH_HEAD
  git -C "${SRC_DIR}" clean -ffd -e brave -e out
else
  git -C "${SRC_DIR}" reset --hard HEAD
  git -C "${SRC_DIR}" clean -ffd -e brave -e out
fi

echo "Pre-syncing Linux host compiler toolchains..."
python3 "${SRC_DIR}/tools/clang/scripts/update.py"
python3 "${SRC_DIR}/tools/rust/update_rust.py"

mkdir -p "${SRC_DIR}/buildtools/linux64"
if command -v cipd >/dev/null 2>&1 && [[ ! -x "${SRC_DIR}/buildtools/linux64/gn" ]]; then
  cipd install "gn/gn/linux-amd64" "git_revision:c7ffaf80713afbe5a4f4d95a605c0a98084374de" -root "${SRC_DIR}/buildtools/linux64" || true
  chmod +x "${SRC_DIR}/buildtools/linux64/gn" 2>/dev/null || true
fi

echo "Setting up depot_tools..."
if [[ ! -d "${DEPOT_TOOLS_DIR}" ]]; then
  git clone --depth 1 "https://chromium.googlesource.com/chromium/tools/depot_tools.git" "${DEPOT_TOOLS_DIR}"
fi
export PATH="${DEPOT_TOOLS_DIR}:${DEPOT_TOOLS_DIR}/.cipd_bin:${PATH}"
export DEPOT_TOOLS_UPDATE=0

# Ensure CIPD packages (including luci-auth) are bootstrapped synchronously
if [[ -f "${DEPOT_TOOLS_DIR}/cipd_bin_setup.sh" ]]; then
  (
    # shellcheck source=/dev/null
    source "${DEPOT_TOOLS_DIR}/cipd_bin_setup.sh"
    cipd_bin_setup >/dev/null 2>&1 || true
  )
fi
"${DEPOT_TOOLS_DIR}/ensure_bootstrap" >/dev/null 2>&1 || "${DEPOT_TOOLS_DIR}/update_depot_tools" >/dev/null 2>&1 || true

rm -rf "${SRC_DIR}/.git/logs" "${SRC_DIR}/.git/hooks" 2>/dev/null || true

XZ_COMPRESS_LEVEL="${XZ_COMPRESS_LEVEL:--7}"

echo "Compressing base Chromium to ${CHROMIUM_ARCHIVE} (level ${XZ_COMPRESS_LEVEL})..."
tar --exclude='src/brave' \
    --exclude='src/out' \
    --exclude='src/.git/logs' \
    --exclude='src/.git/hooks' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    -cf - -C "${WORKSPACE_DIR}" src | xz -T0 "${XZ_COMPRESS_LEVEL}" --memlimit-compress=75% > "${CHROMIUM_ARCHIVE}"

echo "Compressing depot_tools to ${DEPOT_ARCHIVE} (level ${XZ_COMPRESS_LEVEL})..."
tar --exclude='depot_tools/.git/logs' \
    --exclude='depot_tools/.git/hooks' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    -cf - -C "${WORKSPACE_DIR}" depot_tools | xz -T0 "${XZ_COMPRESS_LEVEL}" --memlimit-compress=75% > "${DEPOT_ARCHIVE}"

if [[ "${IN_CI}" == true ]]; then
  echo "Checking registry before upload (idempotent guard)..."
  UPLOAD_CHECK=$(curl -sL -o /dev/null -w "%{http_code}" --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/checksums.sha256" || echo "000")
  if [[ "${UPLOAD_CHECK}" == "200" && "${FORCE_REBUILD}" != true ]]; then
    echo "Package already uploaded by concurrent runner. Skipping redundant upload."
    rm -f "${CHROMIUM_ARCHIVE}" "${DEPOT_ARCHIVE}"
    exit 0
  fi

  UPLOAD_TMP=$(mktemp -d /tmp/chromium-upload-XXXXXX)
  trap 'rm -rf "${UPLOAD_TMP}"' EXIT
  cd "${UPLOAD_TMP}"

  cp "${CHROMIUM_ARCHIVE}" "$(basename "${CHROMIUM_ARCHIVE}")"
  cp "${DEPOT_ARCHIVE}" "$(basename "${DEPOT_ARCHIVE}")"

  FILES=("$(basename "${CHROMIUM_ARCHIVE}")" "$(basename "${DEPOT_ARCHIVE}")")
  sha256sum "${FILES[@]}" > checksums.sha256

  for file in "${FILES[@]}"; do
    echo "Uploading ${file} ($(du -h "${file}" | cut -f1)) to Generic Package Registry..."
    curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file "${file}" "${PKG_URL}/${file}"
  done

  echo "Uploading checksums.sha256..."
  curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file checksums.sha256 "${PKG_URL}/checksums.sha256"
  echo "braving-chromium-source upload complete for ${CHROMIUM_VERSION}!"
else
  echo "Not running in CI environment (no CI_JOB_TOKEN). Local preparation complete."
fi

echo "Cleaning up local source archives to free runner disk space..."
rm -f "${CHROMIUM_ARCHIVE}" "${DEPOT_ARCHIVE}"
