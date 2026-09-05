#!/usr/bin/env bash
# Braving Phase 1 — Upstream Source Preparation Script
# Usage: ./scripts/prepare-source.sh <BRAVE_VERSION>
# Example: ./scripts/prepare-source.sh 1.94.120

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

BRAVE_VERSION="${1:-}"

if [[ -z "${BRAVE_VERSION}" ]]; then
  echo "ERROR: BRAVE_VERSION is required." >&2
  echo "Usage: $0 <BRAVE_VERSION>" >&2
  exit 1
fi

METADATA_FILE="${REPO_ROOT}/metadata/upstream-${BRAVE_VERSION}.yaml"
if [[ ! -f "${METADATA_FILE}" ]]; then
  echo "ERROR: Upstream metadata file not found: ${METADATA_FILE}" >&2
  echo "No verified release definition exists for Brave version ${BRAVE_VERSION}." >&2
  exit 1
fi

echo "========================================================"
echo " Braving Source Preparation"
echo " Target Brave Version: ${BRAVE_VERSION}"
echo " Metadata: ${METADATA_FILE}"
echo "========================================================"

# Parse exact revisions using python3
BRAVE_CORE_COMMIT=$(python3 -c "
import yaml
with open('${METADATA_FILE}') as f:
    data = yaml.safe_load(f)
print(data['repositories']['brave_core']['commit'])
")

CHROMIUM_VERSION=$(python3 -c "
import yaml
with open('${METADATA_FILE}') as f:
    data = yaml.safe_load(f)
print(data['repositories']['chromium']['version'])
")

CHROMIUM_COMMIT=$(python3 -c "
import yaml
with open('${METADATA_FILE}') as f:
    data = yaml.safe_load(f)
print(data['repositories']['chromium']['commit'])
")

if [[ -z "${BRAVE_CORE_COMMIT}" || -z "${CHROMIUM_COMMIT}" ]]; then
  echo "ERROR: Failed to resolve exact revisions from metadata." >&2
  exit 1
fi

echo "Resolved Revisions:"
echo " - brave-core commit: ${BRAVE_CORE_COMMIT}"
echo " - Chromium version : ${CHROMIUM_VERSION}"
echo " - Chromium commit  : ${CHROMIUM_COMMIT}"

# Verify patch set
PATCH_DIR="${REPO_ROOT}/patches"
echo ""
echo "Validating patch set in ${PATCH_DIR}..."

PATCHES=(
  "${PATCH_DIR}/branding/0001-braving-branding-and-package-id.patch"
  "${PATCH_DIR}/build/0001-braving-android-defaults.patch"
  "${PATCH_DIR}/f-droid/0001-gate-google-play-dependencies.patch"
)

for patch_file in "${PATCHES[@]}"; do
  if [[ ! -f "${patch_file}" ]]; then
    echo "ERROR: Required patch file missing: ${patch_file}" >&2
    exit 1
  fi
  echo " [OK] Found patch: $(basename "${patch_file}")"
done

# Validate patches against the exact commit tree
TARGET_BRAVE_DIR="${BRAVE_CORE_DIR:-/run/media/pc/D/brave-core}"
if [[ -d "${TARGET_BRAVE_DIR}/.git" ]]; then
  echo ""
  echo "Validating patch set cleanly against brave-core commit ${BRAVE_CORE_COMMIT}..."
  python3 -c "
import subprocess, tempfile, os, sys

target_commit = '${BRAVE_CORE_COMMIT}'
brave_dir = '${TARGET_BRAVE_DIR}'
patches = [
$(for p in "${PATCHES[@]}"; do echo "    '$p',"; done)
]

with tempfile.TemporaryDirectory() as td:
    subprocess.run(['git', 'init'], cwd=td, check=True, capture_output=True)
    files = [
        'app/theme/brave/android/res_brave_base/values/channel_constants.xml',
        'app/theme/brave/android/res_brave_default_base/values/channel_constants.xml',
        'app/theme/brave/android/values/channel_constants.xml',
        'build/commands/lib/buildArgs.ts',
        'build/args/android_defaults.gni',
        'build/android/config.gni',
    ]
    for f in files:
        try:
            content = subprocess.check_output(['git', '-C', brave_dir, 'cat-file', '-p', f'{target_commit}:{f}'])
            dst = os.path.join(td, f)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, 'wb') as out:
                out.write(content)
        except Exception as e:
            print(f'ERROR: Could not fetch {f} from {target_commit}: {e}', file=sys.stderr)
            sys.exit(1)
    subprocess.run(['git', 'add', '.'], cwd=td, check=True, capture_output=True)
    for p in patches:
        res = subprocess.run(['git', 'apply', '--check', p], cwd=td, capture_output=True, text=True)
        if res.returncode != 0:
            print(f'ERROR: Patch {os.path.basename(p)} failed to apply: {res.stderr}', file=sys.stderr)
            sys.exit(1)
        subprocess.run(['git', 'apply', p], cwd=td, check=True)
        print(f' [OK] Patch applies cleanly: {os.path.basename(p)}')
"
fi

# Generate Release Manifest
RELEASE_MANIFEST_DIR="${REPO_ROOT}/metadata/releases"
mkdir -p "${RELEASE_MANIFEST_DIR}"
RELEASE_MANIFEST="${RELEASE_MANIFEST_DIR}/${BRAVE_VERSION}.yaml"

BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat <<EOF > "${RELEASE_MANIFEST}"
# Braving Release Manifest
# Generated deterministically by scripts/prepare-source.sh

braving_version: "1.94.120"
brave_version: "${BRAVE_VERSION}"
brave_core_commit: "${BRAVE_CORE_COMMIT}"
chromium_version: "${CHROMIUM_VERSION}"
chromium_commit: "${CHROMIUM_COMMIT}"
build_date: "${BUILD_DATE}"
package_id: "org.braving.browser"
target_architecture: "arm64"

applied_patches:
$(for p in "${PATCHES[@]}"; do echo "  - $(basename "$p")"; done)

build_arguments:
  target_os: "android"
  target_cpu: "arm64"
  is_debug: false
  is_official_build: true
  is_component_build: false
  chrome_public_manifest_package: "org.braving.browser"
  enable_brave_wallet: false
  enable_brave_rewards: false
  enable_brave_ads: false
  enable_brave_vpn: false
  enable_ai_chat: false
  enable_brave_news: false
  enable_play_services: false
EOF

echo ""
echo "Successfully generated release manifest: ${RELEASE_MANIFEST}"
echo "Phase 1 source preparation complete."
