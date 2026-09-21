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

CACHE_VERSION="${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION}}-${TARGET_ARCH}-${CI_COMMIT_REF_SLUG}"
PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-cache/${CACHE_VERSION}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${WORKSPACE_DIR:-${CI_PROJECT_DIR:-${REPO_ROOT}}/build-workspace}/src/out"

echo "=========================================="
echo " Packaging Chromium Cache for ${CACHE_VERSION}"
echo "=========================================="

if [[ ! -d "${OUT_DIR}/Release" ]]; then
  echo "Error: ${OUT_DIR}/Release does not exist."
  exit 1
fi

mkdir -p /tmp/cache-upload
cd /tmp/cache-upload

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
  curl --fail --silent --show-error --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file "${chunk}" "${PKG_URL}/${chunk}"
done

echo "Uploading checksums.sha256..."
curl --fail --silent --show-error --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file checksums.sha256 "${PKG_URL}/checksums.sha256"

echo "Cache upload complete!"
