#!/usr/bin/env bash
# Braving Phase 2 — Android Compilation Entry Point
# Usage: ./scripts/build-android.sh [--manifest=<path>] [--arch=arm64|arm|x86_64] [--release]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MANIFEST=""
TARGET_ARCH="arm64"
IS_RELEASE=true
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest=*)
      MANIFEST="${1#*=}"
      shift
      ;;
    --arch=*)
      TARGET_ARCH="${1#*=}"
      shift
      ;;
    --release)
      IS_RELEASE=true
      shift
      ;;
    --debug)
      IS_RELEASE=false
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Step 1: Verify Release Manifest
if [[ -z "${MANIFEST}" ]]; then
  MANIFEST=$(ls -t "${REPO_ROOT}/metadata/releases"/*.yaml 2>/dev/null | head -n 1 || true)
fi

if [[ -z "${MANIFEST}" || ! -f "${MANIFEST}" ]]; then
  echo "ERROR: Release manifest not found. Run prepare-source.sh first." >&2
  exit 1
fi

echo "========================================================"
echo " Braving Android Build"
echo " Manifest    : ${MANIFEST}"
echo " Architecture: ${TARGET_ARCH}"
echo " Release Mode: ${IS_RELEASE}"
echo "========================================================"

# Extract required revisions from manifest
BRAVE_CORE_COMMIT=$(python3 -c "
import yaml
with open('${MANIFEST}') as f:
    data = yaml.safe_load(f)
print(data.get('brave_core_commit', ''))
")

CHROMIUM_COMMIT=$(python3 -c "
import yaml
with open('${MANIFEST}') as f:
    data = yaml.safe_load(f)
print(data.get('chromium_commit', ''))
")

PACKAGE_ID=$(python3 -c "
import yaml
with open('${MANIFEST}') as f:
    data = yaml.safe_load(f)
print(data.get('package_id', 'org.braving.browser'))
")

echo "Manifest Target Revisions:"
echo " - brave-core commit : ${BRAVE_CORE_COMMIT}"
echo " - Chromium commit   : ${CHROMIUM_COMMIT}"
echo " - Package ID        : ${PACKAGE_ID}"

# Step 2: Verify Required Tools
echo ""
echo "Verifying build tools..."
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required." >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ERROR: git is required." >&2; exit 1; }

# Step 3 & 4: Workspace Verification
WORKSPACE_DIR="${WORKSPACE_DIR:-/run/media/pc/D}"
SRC_DIR="${WORKSPACE_DIR}/src"
BRAVE_DIR="${SRC_DIR}/brave"

echo "Build workspace: ${WORKSPACE_DIR}"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Dry-run mode requested. Validation complete."
  exit 0
fi

# Step 7: Configure Android Build Arguments
OUT_DIR="${SRC_DIR}/out/Release"
mkdir -p "${OUT_DIR}"

GN_ARGS_FILE="${OUT_DIR}/args.gn"
echo "Writing GN build arguments to ${GN_ARGS_FILE}..."

cat <<EOF > "${GN_ARGS_FILE}"
target_os = "android"
target_cpu = "${TARGET_ARCH}"
is_debug = false
is_official_build = true
is_component_build = false
symbol_level = 0
disable_fieldtrial_testing_config = true
chrome_public_manifest_package = "${PACKAGE_ID}"
enable_brave_wallet = false
enable_brave_rewards = false
enable_brave_ads = false
enable_brave_vpn = false
enable_ai_chat = false
enable_brave_news = false
enable_play_services = false
EOF

echo ""
echo "Android GN arguments configured successfully:"
cat "${GN_ARGS_FILE}"

# Step 8 & 9: Build Target chrome_public_apk
BUILD_TARGET="chrome_public_apk"
echo ""
echo "Ready to compile target: ${BUILD_TARGET}"
echo "Command to run: ninja -C ${OUT_DIR} ${BUILD_TARGET}"

OUTPUT_APK_DIR="${REPO_ROOT}/out/apks"
mkdir -p "${OUTPUT_APK_DIR}"

echo "Build completed configuration step."
echo "Artifacts will be written to ${OUTPUT_APK_DIR} upon ninja execution."
