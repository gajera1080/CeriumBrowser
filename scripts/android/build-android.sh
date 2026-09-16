#!/usr/bin/env bash
# Braving — Android Compilation Entry Point
# Usage: ./scripts/android/build-android.sh [--manifest=<path>] [--arch=arm64|arm|x86_64] [--release]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

MANIFEST=""
TARGET_ARCH="arm64"
IS_RELEASE=true
DRY_RUN=false
GN_ONLY=false

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
    --gn-only)
    GN_ONLY=true
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
# Resolve to absolute path so later cd commands cannot break manifest lookups
MANIFEST="$(cd "$(dirname "${MANIFEST}")" && pwd)/$(basename "${MANIFEST}")"


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
BRAVE_VERSION=$(extract_manifest_val "brave_version")
CHROMIUM_COMMIT=$(extract_manifest_val "chromium_commit")
CHROMIUM_VERSION=$(extract_manifest_val "chromium_version")
PACKAGE_ID=$(extract_manifest_val "package_id" "org.braving.browser")

echo "Manifest Target Revisions:"
echo " - brave-core version: ${BRAVE_VERSION} (${BRAVE_CORE_COMMIT})"
echo " - Chromium version  : ${CHROMIUM_VERSION} (${CHROMIUM_COMMIT})"
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

# --- TELEMETRY AND RESOURCE CHECK ---
echo "========================================================"
echo " Runner Resources Check"
echo "========================================================"
lscpu | grep -E "^CPU\(s\):|^Model name:|^Socket\(s\):|^Core\(s\) per socket:|^Thread\(s\) per core:" || true
echo ""
free -m || true
echo ""
df -h "${WORKSPACE_DIR}" || true
echo "========================================================"

T_START=$(date +%s)
T_CHECKOUT_START=${T_START}

# Phase 2: Checkout Chromium
if [[ ! -d "${BRAVE_DIR}/.git" ]]; then
  echo "ERROR: Prepared brave-core not found in ${BRAVE_DIR}." >&2
  echo "Please run scripts/android/prepare-source.sh (Phase 1) first." >&2
  exit 1
fi

if [[ ! -d "${SRC_DIR}/.git" ]]; then
  echo ""
  echo "Fetching clean Chromium at exact revision with NO history..."
  mkdir -p "${SRC_DIR}"
  git init "${SRC_DIR}"
  git -C "${SRC_DIR}" config advice.detachedHead false
  git -C "${SRC_DIR}" remote add origin "https://chromium.googlesource.com/chromium/src.git"
  git -C "${SRC_DIR}" fetch --depth 1 origin "refs/tags/${CHROMIUM_VERSION}:refs/tags/${CHROMIUM_VERSION}" 2>/dev/null || \
  git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
  git -C "${SRC_DIR}" reset --hard FETCH_HEAD
else
  echo "Chromium source directory already exists, verifying commit..."
  CURRENT_COMMIT=$(git -C "${SRC_DIR}" rev-parse HEAD 2>/dev/null || echo "")
  if [[ "${CURRENT_COMMIT}" != "${CHROMIUM_COMMIT}" ]]; then
    echo "Existing source is at ${CURRENT_COMMIT}, fetching exact revision ${CHROMIUM_COMMIT}..."
    git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
    git -C "${SRC_DIR}" reset --hard FETCH_HEAD
  fi
fi

T_SYNC_START=$(date +%s)
echo "Disk usage before gclient sync:"
du -sh "${WORKSPACE_DIR}" || true

# Step 7: Set up depot_tools
DEPOT_TOOLS_DIR="${WORKSPACE_DIR}/depot_tools"
if [[ ! -d "${DEPOT_TOOLS_DIR}" ]]; then
  echo ""
  echo "Fetching depot_tools..."
  git clone --depth 1 "https://chromium.googlesource.com/chromium/tools/depot_tools.git" "${DEPOT_TOOLS_DIR}"
fi
export PATH="${DEPOT_TOOLS_DIR}:${PATH}"

# Bootstrap depot_tools (creates python3_bin_reldir.txt, downloads cipd & gn)
echo "Bootstrapping depot_tools..."
"${DEPOT_TOOLS_DIR}/ensure_bootstrap" || "${DEPOT_TOOLS_DIR}/update_depot_tools"
export DEPOT_TOOLS_UPDATE=0

# Step 7b: Generate .gclient configuration for Android
GCLIENT_CONFIG="${WORKSPACE_DIR}/.gclient"
echo ""
echo "Writing gclient configuration to ${GCLIENT_CONFIG}..."
cat <<EOF > "${GCLIENT_CONFIG}"
solutions = [
  {
    "name": "src",
    "url": "https://chromium.googlesource.com/chromium/src.git",
    "managed": False,
    "custom_deps": {
      "src/testing/libfuzzer/fuzzers/wasm_corpus": None,
      "src/third_party/chromium-variations": None,
    },
    "custom_vars": {
      "checkout_pgo_profiles": True,
      "checkout_clang_coverage_tools": True,
      "checkout_clangd": True,
      "download_reclient": True,
      "gn_version": "git_revision:c7ffaf80713afbe5a4f4d95a605c0a98084374de",
    },
  },
  {
    "name": "src/brave",
    "url": "https://github.com/brave/brave-core.git",
    "managed": False,
  },
]
target_os = ["android"]
target_cpu = ["${TARGET_ARCH}"]
EOF

# ----------------------------------------------------
# EXACT BRAVE BUILD FLOW
# 1. gclient sync --nohooks
# 2. applyPatches
# 3. version.py update
# 4. runhooks
# 5. branding / touchOverriddenFiles
# ----------------------------------------------------

# Step 7c: Sync Chromium DEPS dependencies (third_party/angle, v8, skia, toolchains)
echo ""
# Set required PYTHONPATH for upstream Brave hooks (e.g. generate_clang_format.py)
# Matches pythonPaths array in build/commands/lib/config.ts
export PYTHONPATH="${BRAVE_DIR}/script:${SRC_DIR}/tools/grit/grit/extern:${BRAVE_DIR}/vendor/requests:${BRAVE_DIR}/third_party/cryptography:${BRAVE_DIR}/third_party/macholib:${SRC_DIR}/build:${SRC_DIR}/third_party/depot_tools:${PYTHONPATH:-}"
export PYTHONUNBUFFERED="1"

echo "1. Syncing Chromium DEPS dependencies via gclient (shallow, no history, NOHOOKS)..."
(cd "${WORKSPACE_DIR}" && gclient sync --no-history --shallow --nohooks -j16)

# Download and extract the Chromium warm cache AFTER the source checkout and patches.
if [[ "${CACHE_PREP_ONLY:-false}" != "true" ]]; then
  echo -e "\n\e[32;1m\$ ./scripts/download-cache.sh\e[0;m"
  bash ./scripts/download-cache.sh || true
fi

echo "Installing Chromium build dependencies..."
if [[ -f "${SRC_DIR}/build/install-build-deps.sh" ]]; then
  # install-build-deps.sh complains if run as root without --no-prompt
  bash "${SRC_DIR}/build/install-build-deps.sh" --android --no-prompt || echo "WARNING: install-build-deps.sh failed, build might fail"
fi


# Apply Deterministic Braving Asset Overlay to brave-core and Chromium
if [[ -d "${REPO_ROOT}/branding/android" ]]; then
  echo ""
  echo "Applying Braving branding assets overlay..."
  THEME_DIR="${BRAVE_DIR}/app/theme/brave/android"
  BRANDING_DIR="${REPO_ROOT}/branding/android"

  for base_name in "res_brave_base" "res_brave_default_base" "res_brave_beta_base" "res_brave_dev_base" "res_brave_nightly_base"; do
    src_base="${BRANDING_DIR}/${base_name}"
    [[ ! -d "${src_base}" ]] && src_base="${BRANDING_DIR}/res_brave_base"
    if [[ -d "${src_base}" ]]; then
      mkdir -p "${THEME_DIR}/${base_name}"
      cp -rf "${src_base}/"* "${THEME_DIR}/${base_name}/"
    fi
  done

  if [[ -d "${SRC_DIR}/chrome/android/java/res_chromium_base" ]]; then
    cp -rf "${BRANDING_DIR}/res_brave_base/"* "${SRC_DIR}/chrome/android/java/res_chromium_base/"
  fi

  for fre_name in "res_brave" "res_brave_default" "res_brave_beta" "res_brave_dev" "res_brave_nightly"; do
    src_fre="${BRANDING_DIR}/${fre_name}"
    [[ ! -d "${src_fre}" ]] && src_fre="${BRANDING_DIR}/res_brave"
    if [[ -d "${src_fre}" ]]; then
      mkdir -p "${THEME_DIR}/${fre_name}"
      cp -rf "${src_fre}/"* "${THEME_DIR}/${fre_name}/"
    fi
  done

  if [[ -d "${SRC_DIR}/chrome/android/java/res_chromium" ]]; then
    cp -rf "${BRANDING_DIR}/res_brave/"* "${SRC_DIR}/chrome/android/java/res_chromium/"
  fi

  for density_dir in "${BRANDING_DIR}/mipmap-"*; do
    if [[ -d "${density_dir}" ]]; then
      density=$(basename "$density_dir")
      mkdir -p "${THEME_DIR}/${density}"
      cp -f "${density_dir}/app_icon.png" "${THEME_DIR}/${density}/app_icon.png" 2>/dev/null || true
    fi
  done

  echo " [OK] Braving branding overlay applied to brave-core."
fi

echo ""
echo "2. Applying Brave patches (1108+) to Chromium..."
(cd "${BRAVE_DIR}" && pnpm install --frozen-lockfile)

if [[ -d "${BRANDING_DIR}/shields_drawables" ]]; then
  echo " Overlaying dedicated Braving Shields toolbar vector drawables..."
  LEO_DRAWABLE="${BRAVE_DIR}/node_modules/@brave/leo/tokens/android/drawable"
  if [[ -d "${LEO_DRAWABLE}" ]]; then
    cp -f "${BRANDING_DIR}/shields_drawables/"*.xml "${LEO_DRAWABLE}/"
  else
    echo "WARNING: ${LEO_DRAWABLE} not found after pnpm install."
  fi
fi

(cd "${BRAVE_DIR}" && pnpm run apply_patches)
python3 "${REPO_ROOT}/scripts/android/apply-branding.py" "${BRAVE_DIR}"
bash "${REPO_ROOT}/scripts/android/apply-assets.sh" "${BRAVE_DIR}"

echo "Pruning Android Settings UI bloatware..."
echo "Enforcing strict minimalist UI policies natively..."
python3 "${REPO_ROOT}/scripts/android/enforce-policies.py" "${BRAVE_DIR}"
python3 "${REPO_ROOT}/scripts/android/prune-ui.py" "${BRAVE_DIR}"

# Prepare Chromium VERSION and VERSION.chromium sidecar using brave-core version.py
if [[ -f "${SRC_DIR}/chrome/VERSION" ]]; then
  echo ""
  echo "3. Preparing Chromium VERSION and VERSION.chromium sidecar (Brave ${BRAVE_VERSION})..."
  if [[ -f "${BRAVE_DIR}/build/util/version.py" && -n "${BRAVE_VERSION}" ]]; then
    python3 "${BRAVE_DIR}/build/util/version.py" update --brave-version "${BRAVE_VERSION}" "${SRC_DIR}/chrome/VERSION" || {
      echo "WARNING: version.py update failed."
    }
  fi
fi

echo ""
echo "4. Running gclient hooks on patched Chromium..."
(cd "${WORKSPACE_DIR}" && gclient runhooks)

echo ""
echo "5. Propagating branding and touching overridden files..."
(cd "${BRAVE_DIR}" && pnpm run build --prepare_only --target_os=android --target_arch="${TARGET_ARCH}")

# Ensure Braving branding assets (including themed_app_icon.xml in drawable & drawable-night) are present in res_chromium_base
if [[ -d "${BRANDING_DIR}" ]]; then
  if [[ -d "${SRC_DIR}/chrome/android/java/res_chromium_base" && -d "${BRANDING_DIR}/res_brave_base" ]]; then
    cp -rf "${BRANDING_DIR}/res_brave_base/"* "${SRC_DIR}/chrome/android/java/res_chromium_base/"
  fi
  if [[ -d "${SRC_DIR}/chrome/android/java/res_chromium" && -d "${BRANDING_DIR}/res_brave" ]]; then
    cp -rf "${BRANDING_DIR}/res_brave/"* "${SRC_DIR}/chrome/android/java/res_chromium/"
  fi
fi

# Verify //brave/build/version.gni was generated, or generate it now
if [[ -f "${BRAVE_DIR}/build/util/version.py" && -f "${SRC_DIR}/chrome/VERSION" && ! -f "${BRAVE_DIR}/build/version.gni" ]]; then
  echo "Generating brave/build/version.gni..."
  python3 "${BRAVE_DIR}/build/util/version.py" gen "${SRC_DIR}/chrome/VERSION"
fi

# Step 7d: Ensure hermetic GN binary is present in buildtools/linux64
mkdir -p "${SRC_DIR}/buildtools/linux64"
if [[ ! -x "${SRC_DIR}/buildtools/linux64/gn" ]]; then
  echo ""
  echo "Installing hermetic GN binary via CIPD..."
  cipd install "gn/gn/linux-amd64" "git_revision:c7ffaf80713afbe5a4f4d95a605c0a98084374de" -root "${SRC_DIR}/buildtools/linux64" || \
  cipd install "gn/gn/linux-amd64" "latest" -root "${SRC_DIR}/buildtools/linux64"
  chmod +x "${SRC_DIR}/buildtools/linux64/gn" 2>/dev/null || true
fi
export PATH="${SRC_DIR}/buildtools/linux64:${PATH}"

T_GN_START=$(date +%s)

# Step 8: Configure Android Build Arguments
OUT_DIR="${SRC_DIR}/out/Release"
mkdir -p "${OUT_DIR}"

GN_ARGS_FILE="${OUT_DIR}/args.gn"
echo ""
echo "Writing GN build arguments to ${GN_ARGS_FILE}..."

cat <<EOF > "${GN_ARGS_FILE}"
import("//brave/build/args/brave_defaults.gni")
import("//brave/build/args/blink_platform_defaults.gni")
import("//brave/build/args/branding_defaults.gni")
import("//brave/build/args/android_defaults.gni")

target_os = "android"
target_cpu = "${TARGET_ARCH}"
is_debug = false
is_official_build = true
is_java_debug = false
symbol_level = 0
blink_symbol_level = 0
v8_symbol_level = 0
enable_resource_allowlist_generation = false
is_component_build = false
disable_fieldtrial_testing_config = true
chrome_public_manifest_package = "${PACKAGE_ID}"
android_channel = "stable"
target_android_output_format = "apk"

brave_services_key = "no-key"
service_key_stt = "no-key"
service_key_aichat = "no-key"
service_key_search = "no-key"
brave_sync_endpoint = "no-key"
brave_variations_server_url = "no-key"
brave_stats_updater_url = "no-key"
bitflyer_production_fee_address = "no-key"
bitflyer_production_url = "no-key"
uphold_production_api_url = "no-key"
uphold_production_fee_address = "no-key"
uphold_production_oauth_url = "no-key"
zebpay_production_api_url = "no-key"
zebpay_production_oauth_url = "no-key"
rewards_grant_dev_endpoint = "no-key"
rewards_grant_staging_endpoint = "no-key"
rewards_grant_prod_endpoint = "no-key"
EOF

echo ""
echo "Android GN arguments configured:"
cat "${GN_ARGS_FILE}"

# Configure Siso to store its cache inside the output directory
export SISO_LOCAL_CACHE_DIR="${OUT_DIR}/siso_cache"

# Step 9: Run GN gen
echo ""
echo "Running gn gen from source root..."
cd "${SRC_DIR}" && gn gen "${OUT_DIR}"


if [[ "${GN_ONLY:-false}" == "true" ]]; then
  echo "\n========================================================"
  echo " [SUCCESS] GN configuration passed! Skipping compilation (--gn-only)."
  echo "========================================================"
  exit 0
fi

T_NINJA_START=$(date +%s)

# Step 10: Build chrome_public_apk
BUILD_TARGET="${BUILD_TARGET:-brave}"
echo ""
echo "Building target: ${BUILD_TARGET}"
echo "This will take a long time (hours on first build)..."

# Use autoninja if available, otherwise ninja. Restrict to -j 6 to prevent OOM on 32GB RAM CI runners.
# We pipe to awk to only show every 50th line to avoid the 4MB GitLab CI log limit,
# but we save the full log and dump the tail on failure.
echo "Logging full build output to ${WORKSPACE_DIR}/build.log..."

set +e
if command -v autoninja &>/dev/null; then
  (cd "${SRC_DIR}" && autoninja -C "${OUT_DIR}" ${BUILD_TARGET} 2>&1 | tee "${WORKSPACE_DIR}/build.log" | awk '{ if (NR % 50 == 0 || /FAILED:/ || /failed:/ || tolower($0) ~ /error/) print $0; }')
  BUILD_RES=${PIPESTATUS[0]}
else
  (cd "${SRC_DIR}" && ninja -C "${OUT_DIR}" ${BUILD_TARGET} 2>&1 | tee "${WORKSPACE_DIR}/build.log" | awk '{ if (NR % 50 == 0 || /FAILED:/ || /failed:/ || tolower($0) ~ /error/) print $0; }')
  BUILD_RES=${PIPESTATUS[0]}
fi
set -e

if [[ ${BUILD_RES} -ne 0 ]]; then
  echo "========================================================"
  echo " BUILD FAILED! Exit code: ${BUILD_RES}."
  echo "========================================================"
  if [[ -f "${OUT_DIR}/siso_output" ]]; then
    echo "--- siso_output ---"
    cat "${OUT_DIR}/siso_output"
  fi
  if [[ -f "${OUT_DIR}/siso_failed_commands.sh" ]]; then
    echo "--- siso_failed_commands.sh ---"
    cat "${OUT_DIR}/siso_failed_commands.sh"
  fi
  echo "--- Tail of build.log ---"
  tail -n 150 "${WORKSPACE_DIR}/build.log"
  exit 1
fi


if [[ "${CACHE_PREP_ONLY:-false}" == "true" ]]; then
  echo "CACHE_PREP_ONLY=true: Skipping APK packaging."
  exit 0
fi

T_PKG_START=$(date +%s)

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
  
  T_END=$(date +%s)
  echo ""
  echo "========================================================"
  echo " BUILD SUCCESSFUL"
  echo " APK: ${OUTPUT_APK_DIR}/${OUTPUT_NAME}"
  echo " Size: $(du -h "${OUTPUT_APK_DIR}/${OUTPUT_NAME}" | cut -f1)"
  echo "========================================================"
  echo " [TIMING] chromium_checkout=$((T_SYNC_START - T_CHECKOUT_START))s"
  echo " [TIMING] gclient_sync_and_hooks=$((T_GN_START - T_SYNC_START))s"
  echo " [TIMING] gn_gen=$((T_NINJA_START - T_GN_START))s"
  echo " [TIMING] ninja=$((T_PKG_START - T_NINJA_START))s"
  echo " [TIMING] packaging=$((T_END - T_PKG_START))s"
  echo " [TIMING] total=$((T_END - T_START))s"
  echo "========================================================"
else
  echo "ERROR: Build completed but no APK found in ${OUT_DIR}" >&2
  ls -la "${OUT_DIR}/apks/" 2>/dev/null || true
  exit 1
fi
