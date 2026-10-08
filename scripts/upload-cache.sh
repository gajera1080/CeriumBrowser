#!/bin/bash
set -euo pipefail

# Inputs expected from environment:
# BRAVE_VERSION, TARGET_ARCH, CI_API_V4_URL, CI_PROJECT_ID, CI_JOB_TOKEN, CI_PROJECT_DIR

if [[ -z "${CI_API_V4_URL:-}" || -z "${CI_JOB_TOKEN:-}" || -z "${CI_PROJECT_ID:-}" ]]; then
  echo "GitLab CI API variables not set. Skipping cache upload."
  exit 0
fi

if [[ -z "${DYNAMIC_BRAVE_VERSION:-}" && -z "${BRAVE_VERSION:-}" ]]; then
  echo "ERROR: Neither DYNAMIC_BRAVE_VERSION nor BRAVE_VERSION are set."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_ARCH="${TARGET_ARCH:-arm64}"
CACHE_VERSION="${CACHE_VERSION:-${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION}}-${TARGET_ARCH}}"
PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-cache/${CACHE_VERSION}"
OUT_DIR="${WORKSPACE_DIR:-${CI_PROJECT_DIR:-${REPO_ROOT}}/build-workspace}/src/out"

echo "=========================================="
echo " Packaging Chromium Cache for ${CACHE_VERSION}"
echo "=========================================="

if [[ ! -d "${OUT_DIR}/Release" ]]; then
  echo "Error: ${OUT_DIR}/Release does not exist."
  exit 1
fi

# Clean transient process locks before packaging
rm -f "${OUT_DIR}/Release/.siso_lock"

# Verify required Siso metadata and compilation artifacts
# NOTE: .ninja_deps is NOT checked because Siso (use_siso=true) uses its own
# .siso_deps/.siso_fs_state for dependency tracking and never writes .ninja_deps.
echo "Checking Siso state files and compilation artifacts..."
for f in ".siso_fs_state" ".siso_deps" ".ninja_log"; do
  if [[ -f "${OUT_DIR}/Release/${f}" ]]; then
    echo "  [FOUND] ${f} ($(stat -c%s "${OUT_DIR}/Release/${f}" 2>/dev/null || stat -f%z "${OUT_DIR}/Release/${f}" 2>/dev/null || echo "present") bytes)"
  else
    echo "  [WARNING] ${f} not found in ${OUT_DIR}/Release"
  fi
done

if [[ -d "${OUT_DIR}/Release/.siso_local_cache" ]]; then
  echo "  [FOUND] .siso_local_cache directory"
fi
if [[ -d "${OUT_DIR}/Release/obj" ]]; then
  echo "  [FOUND] obj/ directory ($(find "${OUT_DIR}/Release/obj" -name "*.o" 2>/dev/null | wc -l) object files)"
fi
if [[ -d "${OUT_DIR}/Release/gen" ]]; then
  echo "  [FOUND] gen/ directory"
fi

UPLOAD_TMP_DIR=$(mktemp -d /tmp/cache-upload-XXXXXX)
trap 'rm -rf "${UPLOAD_TMP_DIR}"' EXIT
cd "${UPLOAD_TMP_DIR}"

# We cache compiled objects, generated headers, Ninja graph, and Siso state.
# We exclude final apks and temporary thinlto-cache to save package storage.
echo "Compressing and splitting out/Release..."
tar -czf - -C "${OUT_DIR}" \
  --exclude="Release/apks" \
  --exclude="Release/thinlto-cache" \
  Release/ | split -b 4500M - chunk.tar.gz.

echo "Generating SHA256 checksums..."
sha256sum chunk.tar.gz.* > checksums.sha256
cat checksums.sha256

for chunk in chunk.tar.gz.*; do
  echo "Uploading ${chunk} (limit 5GB) to Generic Package Registry..."
  curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file "${chunk}" "${PKG_URL}/${chunk}"
done

echo "Uploading checksums.sha256..."
curl --fail --silent --show-error --location --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file checksums.sha256 "${PKG_URL}/checksums.sha256"

echo "Cache upload complete!"
