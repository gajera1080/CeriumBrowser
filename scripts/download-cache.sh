#!/bin/bash
set -euo pipefail

CACHE_VERSION="${BRAVE_VERSION}-${TARGET_ARCH}-${CI_PIPELINE_ID}"
PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-cache/${CACHE_VERSION}"
OUT_DIR="${CI_PROJECT_DIR}/build-workspace/src/out"

echo "=========================================="
echo " Restoring Chromium Cache for ${CACHE_VERSION}"
echo "=========================================="

mkdir -p /tmp/cache-download
cd /tmp/cache-download

echo "Fetching checksums..."
# If checksums file doesn't exist, this means no cache was found. Fail gracefully.
HTTP_CODE=$(curl -s -o checksums.sha256 -w "%{http_code}" --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/checksums.sha256")

if [[ "${HTTP_CODE}" != "200" ]]; then
  echo "No cache found for ${CACHE_VERSION} (HTTP ${HTTP_CODE}). Starting cold build."
  exit 0
fi

echo "Cache manifest found:"
cat checksums.sha256

for chunk in $(awk '{print $2}' checksums.sha256); do
  echo "Downloading ${chunk}..."
  curl --fail --silent --show-error --header "JOB-TOKEN: ${CI_JOB_TOKEN}" "${PKG_URL}/${chunk}" -o "${chunk}"
done

echo "Verifying SHA256 checksums..."
if ! sha256sum -c checksums.sha256; then
  echo "ERROR: Checksum validation failed! Cache is corrupted."
  exit 1
fi

echo "Extracting cache to ${OUT_DIR}..."
mkdir -p "${OUT_DIR}"
cat chunk.tar.gz.* | tar -xzmf - -C "${OUT_DIR}"
rm -f chunk.tar.gz.*

echo "Cache restore complete!"
