#!/usr/bin/env bash
# Braving — Release Mode Source Preparation Script
# Enforces strict Release Mode determinism:
#   BRAVE_VERSION -> exact matching brave-core release -> exact pinned Chromium revision
#   NO arbitrary overrides permitted.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BRAVE_VERSION="${1:-${BRAVE_VERSION:-}}"

if [[ -z "${BRAVE_VERSION}" ]]; then
  echo "BRAVE_VERSION not set. Fetching latest stable release from GitHub..."
  RELEASE_INFO=$(python3 -c "
import sys, json, urllib.request

def get_latest_version():
    # 1. Try releases/latest (fastest, official latest stable release, ~200KB vs 12MB)
    try:
        req = urllib.request.Request(
            'https://api.github.com/repos/brave/brave-browser/releases/latest',
            headers={'User-Agent': 'Braving-CI', 'Accept': 'application/vnd.github+json'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            tag = data.get('tag_name', '').lstrip('v')
            name = (data.get('name') or '').strip()
            chromium = ''
            if '(Chromium ' in name:
                chromium = name.split('(Chromium ')[1].rstrip(') ')
            if tag:
                return tag, chromium
    except Exception as e:
        print(f'Note: releases/latest lookup failed: {e}', file=sys.stderr)

    # 2. Fallback: query first 10 releases
    try:
        req = urllib.request.Request(
            'https://api.github.com/repos/brave/brave-browser/releases?per_page=10',
            headers={'User-Agent': 'Braving-CI', 'Accept': 'application/vnd.github+json'}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if isinstance(data, list):
                for r in data:
                    name = (r.get('name') or '').strip()
                    if name.startswith('Release '):
                        tag = r['tag_name'].lstrip('v')
                        chromium = ''
                        if '(Chromium ' in name:
                            chromium = name.split('(Chromium ')[1].rstrip(') ')
                        return tag, chromium
    except Exception as e:
        print(f'Note: releases list lookup failed: {e}', file=sys.stderr)

    return '', ''

tag, cr = get_latest_version()
if tag:
    print(f'{tag}|{cr}')
" 2>/dev/null || echo "")

  if [[ -n "${RELEASE_INFO}" ]]; then
    BRAVE_VERSION=$(echo "${RELEASE_INFO}" | cut -d'|' -f1)
    GITHUB_CHROMIUM_VERSION=$(echo "${RELEASE_INFO}" | cut -d'|' -f2)
    echo "Resolved latest stable: Brave v${BRAVE_VERSION} (Chromium ${GITHUB_CHROMIUM_VERSION})"
  fi

  # Fallback to local metadata if GitHub fetch failed
  if [[ -z "${BRAVE_VERSION}" ]]; then
    LATEST_META=$(ls -t "${REPO_ROOT}/metadata/upstream-"*.yaml "${REPO_ROOT}/metadata/releases"/*.yaml 2>/dev/null | head -n 1 || true)
    if [[ -n "${LATEST_META}" ]]; then
      BRAVE_VERSION=$(basename "${LATEST_META}" | sed 's/upstream-//;s/\.yaml//')
      echo "GitHub fetch failed. Using local metadata: ${BRAVE_VERSION}"
    else
      echo "ERROR: Could not resolve BRAVE_VERSION from GitHub or local metadata." >&2
      echo "Usage: $0 <BRAVE_VERSION>" >&2
      exit 1
    fi
  fi
fi

# Strip leading 'v' if present (e.g. v<version> -> <version>)
BRAVE_VERSION="${BRAVE_VERSION#v}"

# Write build.env immediately so CI dotenv artifact is always present
echo "DYNAMIC_BRAVE_VERSION=${BRAVE_VERSION}" > "${REPO_ROOT}/build.env"

echo "========================================================"
echo " Braving Source Preparation (RELEASE MODE)"
echo " BRAVE_VERSION : ${BRAVE_VERSION}"
echo " Rule          : Exact brave-core -> Exact Chromium"
echo " Overrides     : NONE (Strict Determinism)"
echo "========================================================"

# Strict Resolution: BRAVE_VERSION -> brave-core tag -> package.json -> Chromium revision
# If we already got the Chromium version from the GitHub release name, pass it through
export GITHUB_CHROMIUM_VERSION="${GITHUB_CHROMIUM_VERSION:-}"
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

# Use Chromium version from GitHub release name if available (avoids package.json fetch)
if not chromium_version:
    chromium_version = os.environ.get('GITHUB_CHROMIUM_VERSION', '') or None

local_brave = os.environ.get('BRAVE_CORE_DIR', '')

# 1. Resolve exact brave-core release tag commit
if not brave_core_commit:
    # Check local git
    if local_brave and os.path.isdir(os.path.join(local_brave, '.git')):
        try:
            brave_core_commit = subprocess.check_output(
                ['git', '-C', local_brave, 'rev-parse', f'refs/tags/v{version}^{{commit}}'],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            pass

    # Fast GitHub REST lookup for tag commit
    if not brave_core_commit:
        try:
            req = urllib.request.Request(
                f'https://api.github.com/repos/brave/brave-core/git/ref/tags/v{version}',
                headers={'User-Agent': 'Braving-CI', 'Accept': 'application/vnd.github+json'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                obj = data.get('object', {})
                if obj.get('type') == 'tag' and obj.get('url'):
                    tag_req = urllib.request.Request(
                        obj.get('url'),
                        headers={'User-Agent': 'Braving-CI', 'Accept': 'application/vnd.github+json'}
                    )
                    with urllib.request.urlopen(tag_req, timeout=10) as tag_resp:
                        tag_data = json.loads(tag_resp.read().decode('utf-8'))
                        brave_core_commit = tag_data.get('object', {}).get('sha')
                else:
                    brave_core_commit = obj.get('sha')
        except Exception:
            pass

    # Remote lookup fallback for exact release tag
    if not brave_core_commit:
        try:
            ls_out = subprocess.check_output(
                ['git', 'ls-remote', 'https://github.com/brave/brave-core.git', f'refs/tags/v{version}'],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            if ls_out:
                # Annotated tags have a peeled ^{} version pointing to the actual commit
                for line in ls_out.split('\n'):
                    if line.endswith('^{}'):
                        brave_core_commit = line.split()[0]
                        break
                if not brave_core_commit:
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
    # Fast Gitiles REST API lookup (instant, avoids reading 500k refs via ls-remote)
    try:
        req = urllib.request.Request(
            f'https://chromium.googlesource.com/chromium/src/+/refs/tags/{chromium_version}?format=JSON',
            headers={'User-Agent': 'Braving-CI'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('utf-8')
            if raw.startswith(\")]}'\"):
                raw = raw[4:].strip()
            data = json.loads(raw)
            chromium_commit = data.get('commit')
    except Exception:
        pass

    # Remote lookup fallback for Chromium tag
    if not chromium_commit:
        try:
            ls_out = subprocess.check_output(
                ['git', 'ls-remote', 'https://chromium.googlesource.com/chromium/src.git', f'refs/tags/{chromium_version}'],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            if ls_out:
                for line in ls_out.split('\n'):
                    if line.endswith('^{}'):
                        chromium_commit = line.split()[0]
                        break
                if not chromium_commit:
                    chromium_commit = ls_out.split()[0]
        except Exception as e:
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
    disable_android_lint: true
    target_android_output_format: "aab"
    enable_resource_allowlist_generation: true

EOF
echo " [OK] Recorded ${UPSTREAM_META_FILE}"

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

build_arguments:
  target_os: "android"
  target_cpu: "arm64"
  is_debug: false
  is_official_build: true
  is_component_build: false
  chrome_public_manifest_package: "org.braving.browser"
  disable_android_lint: true
  target_android_output_format: "aab"
  enable_resource_allowlist_generation: true
EOF

echo ""
echo "Successfully generated release manifest: ${RELEASE_MANIFEST}"

WORKSPACE_DIR="${WORKSPACE_DIR:-${CI_PROJECT_DIR:-$PWD}/build-workspace}"
SRC_DIR="${WORKSPACE_DIR}/src"
BRAVE_DIR="${SRC_DIR}/brave"

echo ""
echo "Phase 1: Preparing Source in ${WORKSPACE_DIR}"

mkdir -p "${WORKSPACE_DIR}"

# 1. Fetch exact brave-core revision (zero history)
if [[ ! -d "${BRAVE_DIR}/.git" ]]; then
  echo "Fetching clean brave-core at exact revision with NO history..."
  mkdir -p "${BRAVE_DIR}"
  git init "${BRAVE_DIR}"
  git -C "${BRAVE_DIR}" config advice.detachedHead false
  git -C "${BRAVE_DIR}" remote add origin "https://github.com/brave/brave-core.git"
  LOCAL_CORE="${LOCAL_BRAVE_CORE_DIR:-/run/media/pc/D/brave-core}"
  FETCHED=false
  if [[ -d "${LOCAL_CORE}/.git" ]]; then
    if git -C "${BRAVE_DIR}" fetch --depth 1 "${LOCAL_CORE}" "${BRAVE_CORE_COMMIT}" 2>/dev/null; then
      FETCHED=true
    fi
  fi
  if [[ "${FETCHED}" != true ]]; then
    git -C "${BRAVE_DIR}" fetch --depth 1 origin "refs/tags/v${BRAVE_VERSION}:refs/tags/v${BRAVE_VERSION}" 2>/dev/null || \
    git -C "${BRAVE_DIR}" fetch --depth 1 origin "${BRAVE_CORE_COMMIT}"
  fi
  git -C "${BRAVE_DIR}" reset --hard FETCH_HEAD
  git -C "${BRAVE_DIR}" clean -ffd
else
  echo "brave-core directory already exists, verifying commit..."
  CURRENT_BRAVE_COMMIT=$(git -C "${BRAVE_DIR}" rev-parse "HEAD^{commit}" 2>/dev/null || echo "")
  TARGET_BRAVE_COMMIT=$(git -C "${BRAVE_DIR}" rev-parse "${BRAVE_CORE_COMMIT}^{commit}" 2>/dev/null || echo "${BRAVE_CORE_COMMIT}")
  if [[ -n "${CURRENT_BRAVE_COMMIT}" && "${CURRENT_BRAVE_COMMIT}" == "${TARGET_BRAVE_COMMIT}" ]]; then
    echo "Existing brave-core is already at target revision ${CURRENT_BRAVE_COMMIT}, resetting to clean state..."
    git -C "${BRAVE_DIR}" reset --hard "${CURRENT_BRAVE_COMMIT}"
    git -C "${BRAVE_DIR}" clean -ffd
  else
    echo "Existing brave-core is at ${CURRENT_BRAVE_COMMIT}, fetching exact revision ${BRAVE_CORE_COMMIT}..."
    LOCAL_CORE="${LOCAL_BRAVE_CORE_DIR:-/run/media/pc/D/brave-core}"
    FETCHED=false
    if [[ -d "${LOCAL_CORE}/.git" ]]; then
      if git -C "${BRAVE_DIR}" fetch --depth 1 "${LOCAL_CORE}" "${BRAVE_CORE_COMMIT}" 2>/dev/null; then
        FETCHED=true
      fi
    fi
    if [[ "${FETCHED}" != true ]]; then
      git -C "${BRAVE_DIR}" fetch --depth 1 origin "${BRAVE_CORE_COMMIT}"
    fi
    git -C "${BRAVE_DIR}" reset --hard FETCH_HEAD
    git -C "${BRAVE_DIR}" clean -ffd
  fi
fi

# 2. Apply Braving git patches to brave-core
PATCH_DIR="${REPO_ROOT}/patches"
echo ""
echo "Applying Braving patches to brave-core..."

PATCHES=()
if [[ -d "${PATCH_DIR}" ]]; then
  while IFS= read -r -d $'\0' file; do
    PATCHES+=("$file")
  done < <(find "${PATCH_DIR}" -name "*.patch" -print0 | sort -z)
fi

if [[ ${#PATCHES[@]} -eq 0 ]]; then
  echo " - No patches found in ${PATCH_DIR} (all modifications handled via mutators)."
else
  for patch in "${PATCHES[@]}"; do
    pname="${patch#${PATCH_DIR}/}"
    echo " - Applying ${pname}..."
    if git -C "${BRAVE_DIR}" apply --check --reverse "$patch" 2>/dev/null || \
       git -C "${BRAVE_DIR}" apply -C1 --check --reverse "$patch" 2>/dev/null; then
      echo "   [OK] Patch ${pname} already applied."
    elif git -C "${BRAVE_DIR}" apply --check "$patch" 2>/dev/null; then
      git -C "${BRAVE_DIR}" apply "$patch"
      echo "   [OK] Patch ${pname} successfully applied."
    elif git -C "${BRAVE_DIR}" apply -C1 --check "$patch" 2>/dev/null; then
      git -C "${BRAVE_DIR}" apply -C1 "$patch"
      echo "   [OK] Patch ${pname} successfully applied (with -C1 context)."
    else
      echo "ERROR: Patch ${pname} failed to apply and is not already applied. Aborting to fail closed." >&2
      git -C "${BRAVE_DIR}" apply --check -v "$patch" >&2 || true
      exit 1
    fi
  done
fi

# 3. Apply GN-only programmatic fixes (these handle conditional GN array modifications
#    that standard patches cannot do safely across upstream version bumps)
echo ""
echo "Applying GN build fixes..."
python3 "${REPO_ROOT}/scripts/android/apply-features.py" "${BRAVE_DIR}" --strict

# 4. Apply Braving branding overlay and vector assets to brave-core
echo ""
bash "${REPO_ROOT}/scripts/android/apply-assets.sh" "${BRAVE_DIR}"

# 5. Apply Braving UI string branding across GRD/GRDP/XTB and Android XML resources
echo ""
echo "Applying Braving UI string branding..."
python3 "${REPO_ROOT}/scripts/android/apply-branding.py" "${BRAVE_DIR}" --strict

echo "Phase 1: Source Preparation Complete."

