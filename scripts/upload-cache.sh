#!/bin/bash
set -euo pipefail

# Inputs expected from environment:
# BRAVE_VERSION, TARGET_ARCH, CI_API_V4_URL, CI_PROJECT_ID, CI_JOB_TOKEN, CI_PROJECT_DIR

if [[ -z "${CI_API_V4_URL:-}" || -z "${CI_JOB_TOKEN:-}" || -z "${CI_PROJECT_ID:-}" ]]; then
  echo "GitLab CI API variables not set. Skipping cache upload."
  exit 0
fi

CACHE_VERSION="${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION}}-${TARGET_ARCH}-${CI_PIPELINE_ID}"
PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-cache/${CACHE_VERSION}"

OUT_DIR="${CI_PROJECT_DIR}/build-workspace/src/out"

echo "=========================================="
echo " Packaging Chromium Cache for ${CACHE_VERSION}"
echo "=========================================="

if [[ ! -d "${OUT_DIR}/Release" ]]; then
  echo "Error: ${OUT_DIR}/Release does not exist."
  exit 1
fi

mkdir -p /tmp/cache-upload
cd /tmp/cache-upload

# We only cache the specific Siso state and object files to save space
# We exclude apks, thinlto cache, args.gn (since it can change slightly between jobs but shouldn't break hashes)
echo "Compressing and splitting out/Release..."
tar -czf - -C "${OUT_DIR}" \
  --exclude="Release/apks" \
  --exclude="Release/args.gn" \
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
