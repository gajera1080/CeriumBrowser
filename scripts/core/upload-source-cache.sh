#!/usr/bin/env bash
# ==============================================================================
# Braving — Tier 1 Source Cache Uploader (GitLab Generic Package Registry)
# Uploads pre-patched brave-core, depot_tools, and base Chromium archive to:
#   ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-source/${DYNAMIC_BRAVE_VERSION}
# ==============================================================================
set -euo pipefail

if [[ -z "${CI_API_V4_URL:-}" || -z "${CI_JOB_TOKEN:-}" || -z "${CI_PROJECT_ID:-}" ]]; then
  echo "GitLab CI API variables not set. Skipping source cache upload."
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ -f "${REPO_ROOT}/build.env" ]]; then
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/build.env"
fi

DYNAMIC_BRAVE_VERSION="${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION:-}}"
if [[ -z "${DYNAMIC_BRAVE_VERSION}" ]]; then
  echo "ERROR: Neither DYNAMIC_BRAVE_VERSION nor BRAVE_VERSION are set." >&2
  exit 1
fi

WORKSPACE_DIR="${WORKSPACE_DIR:-${CI_PROJECT_DIR:-${REPO_ROOT}}/build-workspace}"
BRAVE_DIR="${WORKSPACE_DIR}/src/brave"
DEPOT_TOOLS_DIR="${WORKSPACE_DIR}/depot_tools"

CHROMIUM_VERSION="${DYNAMIC_CHROMIUM_VERSION:-}"
if [[ -z "${CHROMIUM_VERSION}" && -f "${WORKSPACE_DIR}/src/chrome/VERSION" ]]; then
  CHROMIUM_VERSION=$(grep -E '^(MAJOR|MINOR|BUILD|PATCH)=' "${WORKSPACE_DIR}/src/chrome/VERSION" | cut -d= -f2 | paste -sd.)
fi
CHROMIUM_ARCHIVE="${WORKSPACE_DIR}/chromium-src-${CHROMIUM_VERSION}.tar.xz"

PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-source/${DYNAMIC_BRAVE_VERSION}"

echo "=========================================="
echo " Packaging Source Cache for ${DYNAMIC_BRAVE_VERSION}"
echo " Package URL: ${PKG_URL}"
echo "=========================================="

FORCE_CACHE_REBUILD="${FORCE_CACHE_REBUILD:-false}"
if [[ "${FORCE_CACHE_REBUILD}" != "true" ]]; then
  echo "Checking if source cache ${DYNAMIC_BRAVE_VERSION} already exists in registry..."
  HTTP_CODE=$(curl -sL -o /dev/null -w "%{http_code}" --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/checksums.sha256" || echo "000")
  if [[ "${HTTP_CODE}" == "200" ]]; then
    echo "Source cache for ${DYNAMIC_BRAVE_VERSION} already exists in registry (HTTP 200). Skipping upload."
    exit 0
  fi
fi

if [[ ! -d "${BRAVE_DIR}" ]]; then
  echo "ERROR: brave-core directory ${BRAVE_DIR} does not exist." >&2
  exit 1
fi

if [[ ! -f "${CHROMIUM_ARCHIVE}" ]]; then
  echo "ERROR: Base Chromium archive ${CHROMIUM_ARCHIVE} does not exist." >&2
  exit 1
fi

UPLOAD_TMP_DIR=$(mktemp -d /tmp/source-cache-upload-XXXXXX)
trap 'rm -rf "${UPLOAD_TMP_DIR}"' EXIT
cd "${UPLOAD_TMP_DIR}"

echo "Compressing brave-core..."
BRAVE_ARCHIVE="brave-src-${DYNAMIC_BRAVE_VERSION}.tar.xz"
tar -cf - -C "${WORKSPACE_DIR}/src" brave | xz -T0 -3 > "${BRAVE_ARCHIVE}"

FILES_TO_UPLOAD=("${BRAVE_ARCHIVE}")

if [[ -d "${DEPOT_TOOLS_DIR}" ]]; then
  echo "Compressing depot_tools..."
  DEPOT_ARCHIVE="depot-tools.tar.xz"
  tar -cf - -C "${WORKSPACE_DIR}" depot_tools | xz -T0 -3 > "${DEPOT_ARCHIVE}"
  FILES_TO_UPLOAD+=("${DEPOT_ARCHIVE}")
fi

cp "${CHROMIUM_ARCHIVE}" "$(basename "${CHROMIUM_ARCHIVE}")"
FILES_TO_UPLOAD+=("$(basename "${CHROMIUM_ARCHIVE}")")

echo "Generating SHA256 checksums..."
sha256sum "${FILES_TO_UPLOAD[@]}" > checksums.sha256
cat checksums.sha256

for file in "${FILES_TO_UPLOAD[@]}"; do
  echo "Uploading ${file} ($(du -h "${file}" | cut -f1)) to Generic Package Registry..."
  curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file "${file}" "${PKG_URL}/${file}"
done

echo "Uploading checksums.sha256..."
curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file checksums.sha256 "${PKG_URL}/checksums.sha256"

echo "Source cache upload complete for ${DYNAMIC_BRAVE_VERSION}!"
