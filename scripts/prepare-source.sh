#!/usr/bin/env bash
# Braving — Release Mode Source Preparation Script
# Enforces strict Release Mode determinism:
#   BRAVE_VERSION -> exact matching brave-core release -> exact pinned Chromium revision
#   NO arbitrary overrides permitted.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BRAVE_VERSION="${1:-${BRAVE_VERSION:-}}"

if [[ -z "${BRAVE_VERSION}" ]]; then
  LATEST_UPSTREAM=$(ls -t "${REPO_ROOT}/metadata/upstream-"*.yaml 2>/dev/null | head -n 1 || true)
  if [[ -n "${LATEST_UPSTREAM}" ]]; then
    BRAVE_VERSION=$(basename "${LATEST_UPSTREAM}" | sed 's/upstream-//;s/\.yaml//')
    echo "Notice: BRAVE_VERSION not explicitly set. Using latest release definition: ${BRAVE_VERSION}"
  else
    echo "ERROR: BRAVE_VERSION is required." >&2
    echo "Usage: $0 <BRAVE_VERSION>" >&2
    exit 1
  fi
fi

# Strip leading 'v' if present (e.g. v1.94.120 -> 1.94.120)
BRAVE_VERSION="${BRAVE_VERSION#v}"

echo "========================================================"
echo " Braving Source Preparation (RELEASE MODE)"
echo " BRAVE_VERSION : ${BRAVE_VERSION}"
echo " Rule          : Exact brave-core -> Exact Chromium"
echo " Overrides     : NONE (Strict Determinism)"
echo "========================================================"

# Strict Resolution: BRAVE_VERSION -> brave-core tag -> package.json -> Chromium revision
RESOLVED_DATA=$(python3 -c "
import os, sys, yaml, json, urllib.request, subprocess

version = '${BRAVE_VERSION}'
repo_root = '${REPO_ROOT}'
metadata_path = os.path.join(repo_root, f'metadata/upstream-{version}.yaml')

data = {}
if os.path.isfile(metadata_path):
    with open(metadata_path, 'r') as f:
        data = yaml.safe_load(f) or {}

brave_core_commit = data.get('repositories', {}).get('brave_core', {}).get('commit')
chromium_commit = data.get('repositories', {}).get('chromium', {}).get('commit')
chromium_version = data.get('repositories', {}).get('chromium', {}).get('version')

local_brave = os.environ.get('BRAVE_CORE_DIR', '')

# 1. Resolve exact brave-core release tag commit
if not brave_core_commit:
    # Check local git
    if os.path.isdir(os.path.join(local_brave, '.git')):
        try:
            brave_core_commit = subprocess.check_output(
                ['git', '-C', local_brave, 'rev-parse', f'refs/tags/v{version}^{{commit}}'],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            pass

    # Remote lookup for exact release tag
    if not brave_core_commit:
        try:
            ls_out = subprocess.check_output(
                ['git', 'ls-remote', 'https://github.com/brave/brave-core.git', f'refs/tags/v{version}'],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            if ls_out:
                brave_core_commit = ls_out.split()[0]
        except Exception as e:
            pass

if not brave_core_commit:
    print(f'ERROR: Exact brave-core release tag v{version} does not exist.', file=sys.stderr)
    sys.exit(1)

# 2. Resolve exact Chromium revision from that release package.json
if not chromium_version:
    local_pkg = os.path.join(local_brave, 'package.json')
    if os.path.isfile(local_pkg):
        try:
            with open(local_pkg, 'r') as f:
                pkg_data = json.load(f)
            if pkg_data.get('version') == version:
                chromium_version = pkg_data.get('config', {}).get('projects', {}).get('chrome', {}).get('tag')
        except Exception:
            pass

    if not chromium_version:
        pkg_url = f'https://raw.githubusercontent.com/brave/brave-core/v{version}/package.json'
        try:
            req = urllib.request.Request(pkg_url, headers={'User-Agent': 'Braving-Source-Prep'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                pkg_data = json.loads(resp.read().decode())
                chromium_version = pkg_data.get('config', {}).get('projects', {}).get('chrome', {}).get('tag')
        except Exception as e:
            print(f'ERROR: Failed to fetch package.json for Brave {version}: {e}', file=sys.stderr)
            sys.exit(1)

if not chromium_version:
    print(f'ERROR: Could not resolve pinned Chromium revision from Brave {version} package.json', file=sys.stderr)
    sys.exit(1)

# 3. Resolve exact Chromium commit
if not chromium_commit:
    try:
        ls_out = subprocess.check_output(
            ['git', 'ls-remote', 'https://chromium.googlesource.com/chromium/src.git', f'refs/tags/{chromium_version}'],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        if ls_out:
            chromium_commit = ls_out.split()[0]
    except Exception:
        pass

if not chromium_commit:
    chromium_commit = chromium_version

print(f'{brave_core_commit}|{chromium_version}|{chromium_commit}')
")

BRAVE_CORE_COMMIT=$(echo "${RESOLVED_DATA}" | cut -d'|' -f1)
CHROMIUM_VERSION=$(echo "${RESOLVED_DATA}" | cut -d'|' -f2)
CHROMIUM_COMMIT=$(echo "${RESOLVED_DATA}" | cut -d'|' -f3)

echo ""
echo "Exact Pinned Specification:"
echo " - brave-core release tag : v${BRAVE_VERSION}"
echo " - brave-core commit      : ${BRAVE_CORE_COMMIT}"
echo " - Pinned Chromium tag    : ${CHROMIUM_VERSION}"
echo " - Pinned Chromium commit : ${CHROMIUM_COMMIT}"

mkdir -p "${REPO_ROOT}/metadata"
UPSTREAM_META_FILE="${REPO_ROOT}/metadata/upstream-${BRAVE_VERSION}.yaml"

cat <<EOF > "${UPSTREAM_META_FILE}"
# Upstream Release Metadata for Brave ${BRAVE_VERSION}
# Generated in RELEASE MODE: BRAVE_VERSION -> exact brave-core -> exact Chromium

release:
  brave_version: "${BRAVE_VERSION}"
  release_date: "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

repositories:
  brave_core:
    url: "https://github.com/brave/brave-core.git"
    tag: "refs/tags/v${BRAVE_VERSION}"
    commit: "${BRAVE_CORE_COMMIT}"
    mount_path: "src/brave"

  chromium:
    url: "https://chromium.googlesource.com/chromium/src.git"
    tag: "refs/tags/${CHROMIUM_VERSION}"
    version: "${CHROMIUM_VERSION}"
    commit: "${CHROMIUM_COMMIT}"
    mount_path: "src"

  depot_tools:
    url: "https://chromium.googlesource.com/chromium/tools/depot_tools.git"
    mount_path: "src/brave/vendor/depot_tools"
    behavior:
      disable_auto_update: true

gn_arguments:
  base:
    target_os: "android"
    target_cpu: "arm64"
    is_debug: false
    is_official_build: true
    is_component_build: false
    symbol_level: 0
    disable_fieldtrial_testing_config: true
  braving_overrides:
    chrome_public_manifest_package: "org.braving.browser"
    enable_brave_wallet: false
    enable_brave_vpn: false
    enable_brave_vpn_v1: false
    enable_brave_vpn_v2: false
    enable_ai_chat: false
    enable_brave_news: false
    enable_brave_rewards: false
    enable_brave_ads: false
    enable_brave_talk: false
    enable_brave_stats_updater: false
    enable_web_discovery: false
    enable_web_discovery_native: false
    enable_sparkle: false
EOF
echo " [OK] Recorded ${UPSTREAM_META_FILE}"

# Discover active patches
PATCH_DIR="${REPO_ROOT}/patches"
echo ""
echo "Collecting active patch set from ${PATCH_DIR}..."

PATCHES=()
while IFS= read -r -d $'\0' file; do
  PATCHES+=("$file")
done < <(find "${PATCH_DIR}" -name "*.patch" -print0 | sort -z)

for patch_file in "${PATCHES[@]}"; do
  echo " [OK] Discovered patch: $(realpath --relative-to="${REPO_ROOT}" "${patch_file}")"
done

# If local brave-core repo exists, verify patches apply cleanly against target commit
TARGET_BRAVE_DIR="${BRAVE_CORE_DIR:-/run/media/pc/D/brave-core}"
if [[ -d "${TARGET_BRAVE_DIR}/.git" ]]; then
  echo ""
  echo "Validating patch set against brave-core commit ${BRAVE_CORE_COMMIT}..."
  "${REPO_ROOT}/scripts/verify-patches.sh" "${BRAVE_CORE_COMMIT}"
fi

# Generate Release Manifest
RELEASE_MANIFEST_DIR="${REPO_ROOT}/metadata/releases"
mkdir -p "${RELEASE_MANIFEST_DIR}"
RELEASE_MANIFEST="${RELEASE_MANIFEST_DIR}/${BRAVE_VERSION}.yaml"

BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat <<EOF > "${RELEASE_MANIFEST}"
# Braving Release Manifest
# Generated in RELEASE MODE: BRAVE_VERSION -> exact brave-core -> exact Chromium

braving_version: "${BRAVE_VERSION}"
brave_version: "${BRAVE_VERSION}"
brave_core_commit: "${BRAVE_CORE_COMMIT}"
chromium_version: "${CHROMIUM_VERSION}"
chromium_commit: "${CHROMIUM_COMMIT}"
build_date: "${BUILD_DATE}"
package_id: "org.braving.browser"
target_architecture: "arm64"

applied_patches:
$(for p in "${PATCHES[@]}"; do echo "  - $(realpath --relative-to="${REPO_ROOT}" "$p")"; done)

build_arguments:
  target_os: "android"
  target_cpu: "arm64"
  is_debug: false
  is_official_build: true
  is_component_build: false
  chrome_public_manifest_package: "org.braving.browser"
  enable_brave_wallet: false
  enable_brave_vpn: false
  enable_brave_vpn_v1: false
  enable_brave_vpn_v2: false
  enable_ai_chat: false
  enable_brave_news: false
  enable_brave_rewards: false
  enable_brave_ads: false
  enable_brave_talk: false
  enable_brave_stats_updater: false
  enable_web_discovery: false
  enable_web_discovery_native: false
EOF

echo ""
echo "Successfully generated release manifest: ${RELEASE_MANIFEST}"
echo "Release Mode source preparation complete."
