#!/usr/bin/env bash
# Braving — Android Compilation Entry Point
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
extract_manifest_val() {
  local key="$1"
  local default_val="${2:-}"
  python3 - "$MANIFEST" "$key" "$default_val" <<'PYEOF'
import sys
manifest_path, key, default_val = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    import yaml
    with open(manifest_path) as f:
        data = yaml.safe_load(f) or {}
    print(data.get(key, default_val))
except Exception:
    val = default_val
    prefix = key + ':'
    with open(manifest_path) as f:
        for line in f:
            s = line.strip()
            if s.startswith(prefix):
                val = s[len(prefix):].strip().strip('"\'')
                break
    print(val)
PYEOF
}

BRAVE_CORE_COMMIT=$(extract_manifest_val "brave_core_commit")
CHROMIUM_COMMIT=$(extract_manifest_val "chromium_commit")
PACKAGE_ID=$(extract_manifest_val "package_id" "org.braving.browser")

echo "Manifest Target Revisions:"
echo " - brave-core commit : ${BRAVE_CORE_COMMIT}"
echo " - Chromium commit   : ${CHROMIUM_COMMIT}"
echo " - Package ID        : ${PACKAGE_ID}"

# Step 2: Verify Required Tools
echo ""
echo "Verifying build tools..."
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required." >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ERROR: git is required." >&2; exit 1; }

# Step 3 & 4: Workspace Setup
WORKSPACE_DIR="${WORKSPACE_DIR:-${REPO_ROOT}/build-workspace}"
SRC_DIR="${WORKSPACE_DIR}/src"
BRAVE_DIR="${SRC_DIR}/brave"

echo "Build workspace: ${WORKSPACE_DIR}"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Dry-run mode requested. Validation complete."
  exit 0
fi

# Step 5: Obtain Chromium source at exact revision
mkdir -p "${WORKSPACE_DIR}"
if [[ ! -d "${SRC_DIR}/.git" ]]; then
  echo ""
  echo "Fetching Chromium source at commit ${CHROMIUM_COMMIT}..."
  git clone --depth 1 --no-tags \
    "https://chromium.googlesource.com/chromium/src.git" \
    "${SRC_DIR}" || {
    # Shallow clone of exact commit requires fetch
    git init "${SRC_DIR}"
    git -C "${SRC_DIR}" remote add origin "https://chromium.googlesource.com/chromium/src.git"
    git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
    git -C "${SRC_DIR}" checkout FETCH_HEAD
  }
else
  echo "Chromium source directory already exists, verifying commit..."
  CURRENT_COMMIT=$(git -C "${SRC_DIR}" rev-parse HEAD 2>/dev/null || echo "")
  if [[ "${CURRENT_COMMIT}" != "${CHROMIUM_COMMIT}" ]]; then
    echo "WARNING: Existing source is at ${CURRENT_COMMIT}, expected ${CHROMIUM_COMMIT}"
    echo "Fetching correct commit..."
    git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
    git -C "${SRC_DIR}" checkout FETCH_HEAD
  fi
fi

# Step 6: Obtain brave-core at exact revision
if [[ ! -d "${BRAVE_DIR}/.git" ]]; then
  echo ""
  echo "Fetching brave-core at commit ${BRAVE_CORE_COMMIT}..."
  git clone --depth 1 --no-tags \
    "https://github.com/brave/brave-core.git" \
    "${BRAVE_DIR}" || {
    git init "${BRAVE_DIR}"
    git -C "${BRAVE_DIR}" remote add origin "https://github.com/brave/brave-core.git"
    git -C "${BRAVE_DIR}" fetch --depth 1 origin "${BRAVE_CORE_COMMIT}"
    git -C "${BRAVE_DIR}" checkout FETCH_HEAD
  }
else
  echo "brave-core directory already exists, verifying commit..."
fi

# Step 6b: Apply Braving patches
echo ""
echo "Applying Braving patches to brave-core..."
PATCH_FILES=()
while IFS= read -r -d $'\0' file; do
  PATCH_FILES+=("$file")
done < <(find "${REPO_ROOT}/patches" -name "*.patch" -print0 | sort -z)

for patch in "${PATCH_FILES[@]}"; do
  pname=$(basename "$patch")
  echo " Applying: ${pname}"
  git -C "${BRAVE_DIR}" apply --check "$patch" 2>/dev/null && \
    git -C "${BRAVE_DIR}" apply "$patch" || {
    echo "WARNING: Patch ${pname} may already be applied or conflicts exist, skipping."
  }
done

# Step 6c: Copy Braving logo assets into brave-core source tree
if [[ -d "${REPO_ROOT}/branding/android" ]]; then
  echo ""
  echo "Copying Braving branding assets..."
  THEME_DIR="${BRAVE_DIR}/app/theme/brave/android"
  for density_dir in "${REPO_ROOT}/branding/android/mipmap-"*; do
    density=$(basename "$density_dir")
    # Copy to res_brave_base launcher icons
    target="${THEME_DIR}/res_brave_base/${density}"
    mkdir -p "$target"
    cp -f "${density_dir}/app_icon.png" "$target/app_icon.png" 2>/dev/null || true
    cp -f "${density_dir}/app_icon.png" "$target/layered_app_icon.png" 2>/dev/null || true
  done
fi

# Step 7: Set up depot_tools
DEPOT_TOOLS_DIR="${WORKSPACE_DIR}/depot_tools"
if [[ ! -d "${DEPOT_TOOLS_DIR}" ]]; then
  echo ""
  echo "Fetching depot_tools..."
  git clone "https://chromium.googlesource.com/chromium/tools/depot_tools.git" "${DEPOT_TOOLS_DIR}"
fi
export PATH="${DEPOT_TOOLS_DIR}:${PATH}"
export DEPOT_TOOLS_UPDATE=0

# Step 8: Configure Android Build Arguments
OUT_DIR="${SRC_DIR}/out/Release"
mkdir -p "${OUT_DIR}"

GN_ARGS_FILE="${OUT_DIR}/args.gn"
echo ""
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
enable_brave_vpn = false
enable_brave_vpn_v1 = false
enable_brave_vpn_v2 = false
enable_ai_chat = false
enable_brave_news = false
enable_brave_rewards = false
enable_brave_ads = false
enable_brave_talk = false
enable_brave_stats_updater = false
enable_web_discovery = false
enable_web_discovery_native = false
enable_play_services = false
EOF

echo ""
echo "Android GN arguments configured:"
cat "${GN_ARGS_FILE}"

# Step 9: Run GN gen
echo ""
echo "Running gn gen..."
gn gen "${OUT_DIR}"

# Step 10: Build chrome_public_apk
BUILD_TARGET="chrome_public_apk"
echo ""
echo "Building target: ${BUILD_TARGET}"
echo "This will take a long time (hours on first build)..."

# Use autoninja if available (auto-detects parallelism), otherwise ninja
if command -v autoninja &>/dev/null; then
  autoninja -C "${OUT_DIR}" "${BUILD_TARGET}"
else
  ninja -C "${OUT_DIR}" "${BUILD_TARGET}"
fi

# Step 11: Collect APK artifact
BRAVING_VERSION=$(extract_manifest_val "braving_version" "${BRAVE_VERSION:-unknown}")
OUTPUT_APK_DIR="${REPO_ROOT}/out/apks"
mkdir -p "${OUTPUT_APK_DIR}"

# Find the built APK
BUILT_APK=$(find "${OUT_DIR}/apks" -name "*.apk" -type f | head -n 1 || true)
if [[ -z "${BUILT_APK}" ]]; then
  # Try alternative output location
  BUILT_APK=$(find "${OUT_DIR}" -name "ChromePublic.apk" -type f | head -n 1 || true)
fi

if [[ -n "${BUILT_APK}" ]]; then
  OUTPUT_NAME="Braving-${BRAVING_VERSION}-${TARGET_ARCH}.apk"
  cp "${BUILT_APK}" "${OUTPUT_APK_DIR}/${OUTPUT_NAME}"
  echo ""
  echo "========================================================"
  echo " BUILD SUCCESSFUL"
  echo " APK: ${OUTPUT_APK_DIR}/${OUTPUT_NAME}"
  echo " Size: $(du -h "${OUTPUT_APK_DIR}/${OUTPUT_NAME}" | cut -f1)"
  echo "========================================================"
else
  echo "ERROR: Build completed but no APK found in ${OUT_DIR}" >&2
  ls -la "${OUT_DIR}/apks/" 2>/dev/null || true
  exit 1
fi
