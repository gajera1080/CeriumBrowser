#!/bin/bash
set -euo pipefail

if [[ -z "${CI_API_V4_URL:-}" || -z "${CI_JOB_TOKEN:-}" || -z "${CI_PROJECT_ID:-}" ]]; then
  echo "GitLab CI API variables not set. Skipping cache download."
  exit 0
fi

if [[ -z "${DYNAMIC_BRAVE_VERSION:-}" && -z "${BRAVE_VERSION:-}" ]]; then
  echo "ERROR: Neither DYNAMIC_BRAVE_VERSION nor BRAVE_VERSION are set."
  exit 1
fi

TARGET_ARCH="${TARGET_ARCH:-arm64}"
CACHE_VERSION="${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION}}-${TARGET_ARCH}"
PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-cache/${CACHE_VERSION}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
WORKSPACE_DIR="${WORKSPACE_DIR:-${CI_PROJECT_DIR:-${REPO_ROOT}}/build-workspace}"
OUT_DIR="${WORKSPACE_DIR}/src/out"

echo "=========================================="
echo " Restoring Chromium Cache for ${CACHE_VERSION}"
echo "=========================================="

DOWNLOAD_TMP_DIR=$(mktemp -d /tmp/cache-download-XXXXXX)
trap 'rm -rf "${DOWNLOAD_TMP_DIR}"' EXIT
cd "${DOWNLOAD_TMP_DIR}"

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
# Use -m to touch extracted files to extraction time
cat chunk.tar.gz.* | tar -xzmf - -C "${OUT_DIR}"

# Clean the process lock file
rm -f "${OUT_DIR}/Release/.siso_lock"

# CRITICAL: Delete build.ninja.d to prevent Siso from auto-triggering gn gen.
# build.ninja.d is a depfile listing all .gn/.gni files that were inputs to gn gen.
# When Siso starts, it checks if any file listed in build.ninja.d is newer than
# build.ninja. Since source files were freshly checked out on this runner with
# current timestamps, the check would ALWAYS trigger a gn gen regeneration,
# which would overwrite the cached build.ninja and invalidate ALL command hashes
# in .siso_deps/.ninja_log, causing a full rebuild.
# By deleting build.ninja.d, Siso skips the manifest staleness check entirely
# and trusts the existing build.ninja as authoritative.
rm -f "${OUT_DIR}/Release/build.ninja.d"

# Ensure timestamp hierarchy: T_source <= T_manifest < T_outputs
# This prevents Siso's mtime check (inmtime.After(outmtime)) from marking
# pre-built outputs dirty, while keeping build.ninja newer than source files.
echo "Synchronizing build graph and artifact timestamps to prevent Siso dirty cache invalidation..."

# 1. Touch build manifest files to current time (newer than all freshly checked out source files)
for manifest_file in "${OUT_DIR}/Release/build.ninja" "${OUT_DIR}/Release/build.ninja.stamp" "${OUT_DIR}/Release/args.gn"; do
  if [[ -f "${manifest_file}" ]]; then
    touch "${manifest_file}"
  fi
done

# 2. Ensure a timestamp separation so outputs are strictly newer than manifest
sleep 1

# 3. Touch all pre-compiled object files and generated outputs to ensure outmtime > inmtime
# This covers obj/ (compiled .o files), gen/ (generated headers/sources), and
# other intermediate build artifacts that Siso checks timestamps on.
if [[ -d "${OUT_DIR}/Release/obj" || -d "${OUT_DIR}/Release/gen" ]]; then
  echo "Touching cached obj/ and gen/ artifacts to preserve up-to-date state..."
  find "${OUT_DIR}/Release/obj" "${OUT_DIR}/Release/gen" -type f -exec touch {} + 2>/dev/null || true
fi

# 4. Write a marker file so build-android.sh can detect cache presence and skip gn gen
touch "${OUT_DIR}/Release/.cache_restored"

# Verify restored Siso state
# NOTE: .ninja_deps is NOT checked because Siso (use_siso=true) uses its own
# .siso_deps/.siso_fs_state for dependency tracking and never writes .ninja_deps.
echo "Restored Siso state files:"
for f in ".siso_fs_state" ".siso_deps" ".ninja_log"; do
  if [[ -f "${OUT_DIR}/Release/${f}" ]]; then
    echo "  [RESTORED] ${f} ($(stat -c%s "${OUT_DIR}/Release/${f}" 2>/dev/null || stat -f%z "${OUT_DIR}/Release/${f}" 2>/dev/null || echo "present") bytes)"
  else
    echo "  [WARNING] ${f} missing after restore"
  fi
done

if [[ -d "${OUT_DIR}/Release/.siso_local_cache" ]]; then
  echo "  [RESTORED] .siso_local_cache directory"
fi

RESTORED_SIZE=$(du -sh "${OUT_DIR}/Release" 2>/dev/null | cut -f1 || echo "unknown")
echo "Cache restore complete! Restored ${RESTORED_SIZE} into ${OUT_DIR}/Release."
echo " [NOTE] Siso reports reused cached targets under 'skip:'."
echo "        The 'cache:' metric is for remote cloud RBE and is expected to be 0 for local builds."
