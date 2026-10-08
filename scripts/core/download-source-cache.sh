#!/usr/bin/env bash
# ==============================================================================
# Braving — Tier 1 Source Cache Downloader (GitLab Generic Package Registry)
# Downloads and restores pre-patched brave-core, depot_tools, and base Chromium archive:
#   ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-source/${DYNAMIC_BRAVE_VERSION}
# ==============================================================================
set -euo pipefail

if [[ -z "${CI_API_V4_URL:-}" || -z "${CI_JOB_TOKEN:-}" || -z "${CI_PROJECT_ID:-}" ]]; then
  echo "GitLab CI API variables not set. Skipping source cache download."
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
PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-source/${DYNAMIC_BRAVE_VERSION}"

echo "=========================================="
echo " Restoring Source Cache for ${DYNAMIC_BRAVE_VERSION}"
echo " Package URL: ${PKG_URL}"
echo "=========================================="

DOWNLOAD_TMP_DIR=$(mktemp -d /tmp/source-cache-download-XXXXXX)
trap 'rm -rf "${DOWNLOAD_TMP_DIR}"' EXIT
cd "${DOWNLOAD_TMP_DIR}"

echo "Fetching checksums from ${PKG_URL}/checksums.sha256..."
HTTP_CODE=$(curl -sL -o checksums.sha256 -w "%{http_code}" --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/checksums.sha256" || echo "000")

if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "No source cache found for ${DYNAMIC_BRAVE_VERSION} (HTTP ${HTTP_CODE}). Starting cold source setup."
  exit 0
fi

echo "Source cache manifest found (HTTP ${HTTP_CODE}):"
cat checksums.sha256

for file in $(awk '{print $2}' checksums.sha256); do
  echo "Downloading ${file}..."
  curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/${file}" -o "${file}"
done

echo "Verifying SHA256 checksums..."
if ! sha256sum -c checksums.sha256; then
  echo "ERROR: Checksum validation failed! Source cache is corrupted." >&2
  exit 1
fi

mkdir -p "${WORKSPACE_DIR}/src"

for file in $(awk '{print $2}' checksums.sha256); do
  case "${file}" in
    brave-src-*.tar.xz)
      echo "Extracting brave-core to ${WORKSPACE_DIR}/src/brave..."
      tar -xf "${file}" -C "${WORKSPACE_DIR}/src"
      ;;
    depot-tools.tar.xz)
      echo "Extracting depot_tools to ${WORKSPACE_DIR}/depot_tools..."
      tar -xf "${file}" -C "${WORKSPACE_DIR}"
      ;;
    chromium-src-*.tar.xz)
      echo "Placing ${file} in ${WORKSPACE_DIR}..."
      cp -f "${file}" "${WORKSPACE_DIR}/${file}"
      ;;
    *)
      echo "Skipping unknown file in source cache package: ${file}"
      ;;
  esac
done

echo "Source cache restored successfully for ${DYNAMIC_BRAVE_VERSION}!"
