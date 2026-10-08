#!/usr/bin/env bash
# Braving — Android Compilation Entry Point
# Usage: ./scripts/platforms/android/build.sh [--manifest=<path>] [--arch=arm64|arm|x86_64] [--release]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

MANIFEST=""
TARGET_ARCH="arm64"
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
      case "${TARGET_ARCH}" in
        arm64|arm|x86|x64) ;;
        x86_64) TARGET_ARCH="x64" ;;
        *) echo "ERROR: Invalid architecture: ${TARGET_ARCH}" >&2; exit 1 ;;
      esac
      shift
      ;;
    --gn-only)
    GN_ONLY=true
    shift
    ;;
    --release)
      shift
      ;;
    --debug)
      echo "ERROR: Debug builds are disabled for production releases. Only --release is supported." >&2
      exit 1
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
echo " Release Mode: true"
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

export BRAVE_VERSION
export DYNAMIC_BRAVE_VERSION="${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION}}"
export TARGET_ARCH

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

# Full build requires node and pnpm
command -v node >/dev/null 2>&1 || { echo "ERROR: node is required." >&2; exit 1; }
command -v pnpm >/dev/null 2>&1 || { echo "ERROR: pnpm is required." >&2; exit 1; }

# --- SYSTEM RESOURCES CHECK ---
echo "========================================================"
echo " System Resources Check"
echo "========================================================"
lscpu | grep -E "^CPU\(s\):|^Model name:|^Socket\(s\):|^Core\(s\) per socket:|^Thread\(s\) per core:" || true
echo ""
free -m || true
echo ""
df -h "${WORKSPACE_DIR}" || true
echo "========================================================"

T_START=$(date +%s)
T_CHECKOUT_START=${T_START}

# Phase 2: Verify brave-core
if [[ ! -d "${BRAVE_DIR}" ]]; then
  echo "ERROR: Prepared brave-core not found in ${BRAVE_DIR}." >&2
  echo "Please run scripts/core/prepare-source.sh (Phase 1) first." >&2
  exit 1
fi


if [[ ! -d "${SRC_DIR}/.git" ]]; then
  echo ""
  echo "Fetching clean Chromium at exact revision with NO history (${CHROMIUM_VERSION} @ ${CHROMIUM_COMMIT})..."
  mkdir -p "${SRC_DIR}"
  git init "${SRC_DIR}"
  git -C "${SRC_DIR}" config advice.detachedHead false
  git -C "${SRC_DIR}" remote add origin "https://chromium.googlesource.com/chromium/src.git" 2>/dev/null || git -C "${SRC_DIR}" remote set-url origin "https://chromium.googlesource.com/chromium/src.git"
  git -C "${SRC_DIR}" fetch --depth 1 origin "refs/tags/${CHROMIUM_VERSION}:refs/tags/${CHROMIUM_VERSION}" 2>/dev/null || \
  git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
  git -C "${SRC_DIR}" reset --hard FETCH_HEAD
  git -C "${SRC_DIR}" clean -ffd
else
  echo "Chromium source directory already exists, verifying commit..."
  CURRENT_COMMIT=$(git -C "${SRC_DIR}" rev-parse HEAD 2>/dev/null || echo "")
  if [[ "${CURRENT_COMMIT}" != "${CHROMIUM_COMMIT}" ]]; then
    echo "Existing source is at ${CURRENT_COMMIT}, fetching exact revision ${CHROMIUM_COMMIT}..."
    git -C "${SRC_DIR}" fetch --depth 1 origin "${CHROMIUM_COMMIT}"
    git -C "${SRC_DIR}" reset --hard FETCH_HEAD
    git -C "${SRC_DIR}" clean -ffd
  else
    echo "Existing source is at ${CURRENT_COMMIT}, resetting to clean state..."
    git -C "${SRC_DIR}" reset --hard HEAD
    git -C "${SRC_DIR}" clean -ffd
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

# Step 7a: Git compatibility shim for depot_tools when running on Git < 2.43.1
# git checkout only supports --end-of-options starting in Git 2.43.1.
# On older Git (e.g. Debian Bookworm's git 2.39), depot_tools passing --end-of-options
# causes: "error: pathspec '--end-of-options' did not match any file(s) known to git"
REAL_GIT=$(command -v git)
GIT_NEEDS_SHIM=$(python3 -c "
import subprocess
try:
    ver_str = subprocess.check_output(['${REAL_GIT}', '--version'], text=True).split()[-1]
    parts = [int(p) for p in ver_str.split('.')[:2] if p.isdigit()]
    if len(parts) >= 2 and (parts[0] < 2 or (parts[0] == 2 and parts[1] < 43)):
        print('true')
    else:
        print('false')
except Exception:
    print('true')
" 2>/dev/null || echo "true")

if [[ "${GIT_NEEDS_SHIM}" == "true" ]]; then
  echo "Detected Git < 2.43.1 (${REAL_GIT}). Installing Git compatibility shim for depot_tools..."
  GIT_COMPAT_DIR="${WORKSPACE_DIR}/git-compat"
  mkdir -p "${GIT_COMPAT_DIR}"
  cat <<WRAPPER > "${GIT_COMPAT_DIR}/git"
#!/usr/bin/env bash
REAL_GIT="${REAL_GIT}"
is_subcmd=false
for arg in "\$@"; do
  if [[ "\$arg" == "checkout" || "\$arg" == "switch" || "\$arg" == "restore" ]]; then
    is_subcmd=true
    break
  fi
done

if [[ "\$is_subcmd" == true ]]; then
  filtered_args=()
  for arg in "\$@"; do
    if [[ "\$arg" != "--end-of-options" ]]; then
      filtered_args+=("\$arg")
    fi
  done
  exec "\$REAL_GIT" "\${filtered_args[@]}"
fi

exec "\$REAL_GIT" "\$@"
WRAPPER
  chmod +x "${GIT_COMPAT_DIR}/git"
  cp -f "${GIT_COMPAT_DIR}/git" "${DEPOT_TOOLS_DIR}/git"
  export PATH="${GIT_COMPAT_DIR}:${PATH}"
  echo "Git compatibility shim installed at ${GIT_COMPAT_DIR}/git and ${DEPOT_TOOLS_DIR}/git"
fi

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
export PYTHONPATH="${BRAVE_DIR}/script:${SRC_DIR}/tools/grit/grit/extern:${BRAVE_DIR}/vendor/requests:${BRAVE_DIR}/third_party/cryptography:${BRAVE_DIR}/third_party/macholib:${SRC_DIR}/build:${SRC_DIR}/third_party/depot_tools${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUNBUFFERED="1"

echo "1. Syncing Chromium DEPS dependencies via gclient (shallow, no history, NOHOOKS)..."
(cd "${WORKSPACE_DIR}" && gclient sync --no-history --shallow --nohooks -j16)

# Step 7d: Install build dependencies
echo "Installing Chromium build dependencies..."
if [[ -f "${SRC_DIR}/build/install-build-deps.sh" ]]; then
  # install-build-deps.sh complains if run as root without --no-prompt
  bash "${SRC_DIR}/build/install-build-deps.sh" --android --no-prompt
fi


echo ""
echo "2. Installing brave-core node dependencies and applying upstream Brave patches to Chromium..."
(cd "${BRAVE_DIR}" && pnpm install --frozen-lockfile)
(cd "${BRAVE_DIR}" && pnpm run apply_patches)


# Prepare Chromium VERSION and VERSION.chromium sidecar using brave-core version.py
if [[ -f "${SRC_DIR}/chrome/VERSION" ]]; then
  echo ""
  echo "3. Preparing Chromium VERSION and VERSION.chromium sidecar (Brave ${BRAVE_VERSION})..."
  if [[ -f "${BRAVE_DIR}/build/util/version.py" && -n "${BRAVE_VERSION}" ]]; then
    python3 "${BRAVE_DIR}/build/util/version.py" update --brave-version "${BRAVE_VERSION}" "${SRC_DIR}/chrome/VERSION"
  fi
  # Apply version display mutators to Chromium src so APK versionName, Settings,
  # and C++/Java version strings display clean Brave version (e.g. <version>)
  # without prepending Chromium major milestone (e.g. <milestone>.)
  echo "Applying version display mutators to Chromium src..."
  python3 "${REPO_ROOT}/scripts/core/apply-features.py" "${BRAVE_DIR}" --strict --src-dir="${SRC_DIR}" --target-os=android
fi

echo ""
echo "4. Running gclient hooks on patched Chromium..."
(cd "${WORKSPACE_DIR}" && gclient runhooks)

echo ""
echo "5. Propagating branding from brave-core/app/theme/brave and touching overridden files..."
(cd "${BRAVE_DIR}" && pnpm run build Release --prepare_only --target_os=android --target_arch="${TARGET_ARCH}" --channel=release)

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
  HOST_ARCH=$(uname -m)
  CIPD_ARCH="amd64"
  if [[ "${HOST_ARCH}" == "aarch64" ]]; then
    CIPD_ARCH="arm64"
  fi
  cipd install "gn/gn/linux-${CIPD_ARCH}" "git_revision:c7ffaf80713afbe5a4f4d95a605c0a98084374de" -root "${SRC_DIR}/buildtools/linux64" || \
  cipd install "gn/gn/linux-${CIPD_ARCH}" "latest" -root "${SRC_DIR}/buildtools/linux64"
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
enable_resource_allowlist_generation = true
is_component_build = false
disable_fieldtrial_testing_config = true
chrome_public_manifest_package = "${PACKAGE_ID}"
android_channel = "stable"
brave_channel = ""
target_android_output_format = "aab"
chrome_version_name = "${BRAVE_VERSION}"
android_override_version_name = "${BRAVE_VERSION}"
android_default_version_name = "${BRAVE_VERSION}"
enable_android_secondary_abi = false
skip_secondary_abi_for_cq = true
dcheck_always_on = false
enable_java_asserts = false
exclude_unwind_tables = true
use_siso = true
disable_android_lint = true

# Debloated subsystems (wallet, vpn, ai_chat, news, rewards, p3a, stats) are enforced via Enterprise Policies
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

# Configure Siso cache environment variables
export SISO_CACHE_DIR="${OUT_DIR}/.siso_local_cache"
export SISO_LOCAL_CACHE_DIR="${SISO_CACHE_DIR}"

# Step 9: Cache Restore OR GN Gen
CACHE_RESTORED=false
if [[ "${CACHE_PREP_ONLY:-false}" != "true" ]]; then
  echo ""
  echo -e "\e[32;1m\$ ./scripts/download-cache.sh\e[0;m"
  if [[ -f "${REPO_ROOT}/scripts/download-cache.sh" ]]; then
    bash "${REPO_ROOT}/scripts/download-cache.sh"
  fi
  # Check if download-cache.sh successfully restored the cache
  if [[ -f "${OUT_DIR}/.cache_restored" ]]; then
    CACHE_RESTORED=true
    rm -f "${OUT_DIR}/.cache_restored"
    echo ""
    echo "[CACHE] Warm cache restored from Stage 2. Skipping gn gen to preserve build.ninja integrity."
  fi
fi

if [[ "${CACHE_RESTORED}" == "false" ]]; then
  echo ""
  echo "Running gn gen from source root..."
  cd "${SRC_DIR}" && gn gen "${OUT_DIR}"
  rm -f "${OUT_DIR}/build.ninja.d"
else
  if [[ -f "${OUT_DIR}/build.ninja" ]]; then
    touch -r "${OUT_DIR}/build.ninja" "${GN_ARGS_FILE}"
  fi
  echo "Running gn gen skipped — using cached build.ninja from Stage 2."
  cd "${SRC_DIR}"
fi

# Configure Siso runtime settings via .sisorc and ensure backend files exist
# -fs_keep_tainted: preserves HashFS cmdhash when local file timestamps are newer than entTime
# -local_cache_enable & -cache_dir: enables local disk caching of action outputs
mkdir -p "${SRC_DIR}/build/config/siso"
cat <<EOF > "${SRC_DIR}/build/config/siso/.sisorc"
ninja -fs_keep_tainted -local_cache_enable -cache_dir=${SISO_CACHE_DIR}
EOF

if [[ -d "${SRC_DIR}/build/config/siso/backend_config" && ! -f "${SRC_DIR}/build/config/siso/backend_config/backend.star" ]]; then
  cp "${SRC_DIR}/build/config/siso/backend_config/template.star" "${SRC_DIR}/build/config/siso/backend_config/backend.star" 2>/dev/null || true
fi
if [[ ! -f "${SRC_DIR}/build/config/siso/.sisoenv" ]]; then
  touch "${SRC_DIR}/build/config/siso/.sisoenv"
fi

if [[ "${GN_ONLY:-false}" == "true" ]]; then
  echo ""
  echo "========================================================"
  echo " [SUCCESS] GN configuration passed! Skipping compilation (--gn-only)."
  echo "========================================================"
  exit 0
fi

T_NINJA_START=$(date +%s)

# Step 10: Build chrome_public_bundle (or custom BUILD_TARGET)
BUILD_TARGET="${BUILD_TARGET:-chrome_public_bundle}"
echo ""
echo "Building target: ${BUILD_TARGET}"
echo "This will take a long time (hours on first build)..."

# Filter console stream to avoid GitLab CI 4MB log limit while preserving all errors and saving complete build.log
echo "Logging full build output to ${WORKSPACE_DIR}/build.log..."
set +e
set +o pipefail

cd "${SRC_DIR}"
BUILD_RES=0

if command -v autoninja &>/dev/null; then
  autoninja -C "${OUT_DIR}" ${BUILD_TARGET} 2>&1 | python3 -u "${REPO_ROOT}/scripts/core/filter-build-log.py" "${WORKSPACE_DIR}/build.log"
  BUILD_RES=${PIPESTATUS[0]}
else
  ninja -C "${OUT_DIR}" ${BUILD_TARGET} 2>&1 | python3 -u "${REPO_ROOT}/scripts/core/filter-build-log.py" "${WORKSPACE_DIR}/build.log"
  BUILD_RES=${PIPESTATUS[0]}
fi

# Collect any Siso glog files from /tmp into OUT_DIR for CI artifact upload
for f in /tmp/siso.* /tmp/siso_*; do
  if [[ -f "$f" ]]; then
    cp -f "$f" "${OUT_DIR}/" 2>/dev/null || true
  fi
done

# Compress build.log to build.log.gz for compact CI artifact storage
if [[ -f "${WORKSPACE_DIR}/build.log" ]]; then
  gzip -k -f "${WORKSPACE_DIR}/build.log" || true
fi

# Package build logs, Siso traces, and configs into .tar.xz artifact
archive_build_artifacts() {
  local archive_path="${WORKSPACE_DIR}/build-artifacts.tar.xz"
  echo "Compressing build logs and diagnostic artifacts to ${archive_path}..."
  local entries=()
  if [[ -f "${WORKSPACE_DIR}/build.log" ]]; then
    entries+=(-C "${WORKSPACE_DIR}" "build.log")
  fi
  if [[ -d "${OUT_DIR}" ]]; then
    if [[ -f "${OUT_DIR}/args.gn" ]]; then
      entries+=(-C "${OUT_DIR}" "args.gn")
    fi
    if [[ -f "${OUT_DIR}/.ninja_log" ]]; then
      entries+=(-C "${OUT_DIR}" ".ninja_log")
    fi
    for s_file in "${OUT_DIR}"/siso*; do
      if [[ -e "${s_file}" ]]; then
        entries+=(-C "${OUT_DIR}" "$(basename "${s_file}")")
      fi
    done
  fi

  if [[ ${#entries[@]} -gt 0 ]]; then
    XZ_OPT="-T0 -6" tar -cJf "${archive_path}" "${entries[@]}" 2>/dev/null || \
      tar -czf "${WORKSPACE_DIR}/build-artifacts.tar.gz" "${entries[@]}" 2>/dev/null || true
    if [[ -f "${archive_path}" ]]; then
      echo " [OK] Packed build artifacts: ${archive_path} ($(du -h "${archive_path}" | cut -f1))"
    fi
  fi
}
archive_build_artifacts

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

# Re-enable strict error handling for packaging steps (C1)
set -e
set -o pipefail

if [[ "${CACHE_PREP_ONLY:-false}" == "true" ]]; then
  echo "CACHE_PREP_ONLY=true: Skipping APK packaging."
  exit 0
fi

T_PKG_START=$(date +%s)

# Step 11: Collect and Optimize Artifacts (AAB Bundle & Standalone Universal APK)
BRAVING_VERSION=$(extract_manifest_val "braving_version" "${BRAVE_VERSION:-unknown}")
OUTPUT_APK_DIR="${REPO_ROOT}/out/apks"
mkdir -p "${OUTPUT_APK_DIR}"
OUTPUT_NAME="Braving-${BRAVING_VERSION}-${TARGET_ARCH}.apk"
OUTPUT_AAB_NAME="Braving-${BRAVING_VERSION}-${TARGET_ARCH}.aab"

BUILT_AAB=$(find "${OUT_DIR}/apks" -name "*.aab" -type f 2>/dev/null | sort | head -n 1 || true)
BUILT_APK=""

if [[ -n "${BUILT_AAB}" ]]; then
  echo ""
  echo "Found Android App Bundle: ${BUILT_AAB}"
  cp -f "${BUILT_AAB}" "${OUTPUT_APK_DIR}/${OUTPUT_AAB_NAME}"
  echo " [OK] Saved App Bundle artifact: ${OUTPUT_APK_DIR}/${OUTPUT_AAB_NAME}"

  # Step 11a: Convert AAB to Universal Standalone APK via bundletool
  BUNDLETOOL_JAR="${SRC_DIR}/third_party/android_build_tools/bundletool/cipd/bundletool.jar"
  if [[ ! -f "${BUNDLETOOL_JAR}" ]]; then
    BUNDLETOOL_JAR=$(find "${SRC_DIR}" -name "bundletool*.jar" -type f 2>/dev/null | head -n 1 || true)
  fi

  if [[ -f "${BUNDLETOOL_JAR}" ]]; then
    echo "Converting AAB to Universal Standalone APK with compressed native libraries (bundletool)..."
    APKS_ARCHIVE="${OUT_DIR}/apks/universal.apks"
    rm -f "${APKS_ARCHIVE}"

    java -jar "${BUNDLETOOL_JAR}" build-apks \
      --bundle="${BUILT_AAB}" \
      --output="${APKS_ARCHIVE}" \
      --mode=universal

    RAW_UNIVERSAL="${OUT_DIR}/apks/universal.apk"
    rm -f "${RAW_UNIVERSAL}"
    unzip -q -o "${APKS_ARCHIVE}" "universal.apk" -d "${OUT_DIR}/apks/"

    # Step 11b: 4-byte alignment via zipalign
    ZIPALIGN_BIN=$(find "${SRC_DIR}/third_party/android_sdk" -name "zipalign" -type f -perm /111 2>/dev/null | head -n 1 || command -v zipalign || true)
    FINAL_UNSIGNED="${OUT_DIR}/apks/${OUTPUT_NAME}.unsigned"
    if [[ -n "${ZIPALIGN_BIN}" && -x "${ZIPALIGN_BIN}" ]]; then
      echo "Aligning package with zipalign..."
      "${ZIPALIGN_BIN}" -p -f 4 "${RAW_UNIVERSAL}" "${FINAL_UNSIGNED}"
    else
      cp -f "${RAW_UNIVERSAL}" "${FINAL_UNSIGNED}"
    fi

    BUILT_APK="${FINAL_UNSIGNED}"
  else
    echo "WARNING: bundletool.jar not found at ${BUNDLETOOL_JAR}. Falling back to pre-existing APKs."
  fi
fi

# Fallback: search for direct APK outputs
if [[ -z "${BUILT_APK}" ]]; then
  if [[ -f "${OUT_DIR}/apks/ChromePublic.apk" ]]; then
    BUILT_APK="${OUT_DIR}/apks/ChromePublic.apk"
  elif [[ -f "${OUT_DIR}/apks/${OUTPUT_NAME}" ]]; then
    BUILT_APK="${OUT_DIR}/apks/${OUTPUT_NAME}"
  else
    BUILT_APK=$(find "${OUT_DIR}/apks" \( -name "Braving*.apk" -o -name "Brave*.apk" -o -name "ChromePublic*.apk" \) -type f 2>/dev/null | sort | head -n 1 || true)
  fi
fi
if [[ -z "${BUILT_APK}" ]]; then
  BUILT_APK=$(find "${OUT_DIR}" \( -name "Braving*.apk" -o -name "Brave*.apk" -o -name "ChromePublic*.apk" \) -type f 2>/dev/null | sort | head -n 1 || true)
fi
if [[ -z "${BUILT_APK}" ]]; then
  BUILT_APK=$(find "${OUT_DIR}/apks" -name "*.apk" -type f 2>/dev/null | sort | head -n 1 || true)
fi

if [[ -n "${BUILT_APK}" ]]; then
  if [[ "${BUILT_APK}" != "${OUTPUT_APK_DIR}/${OUTPUT_NAME}" ]]; then
    cp -f "${BUILT_APK}" "${OUTPUT_APK_DIR}/${OUTPUT_NAME}"
  fi
  if [[ "${BUILT_APK}" != "${OUT_DIR}/apks/${OUTPUT_NAME}" ]]; then
    cp -f "${BUILT_APK}" "${OUT_DIR}/apks/${OUTPUT_NAME}" 2>/dev/null || true
  fi

  # Step 12: Release APK Signing (when KEY_PASSWORD_ANDROID or keystore is configured)
  if [[ -n "${KEY_PASSWORD_ANDROID:-}" || -n "${ANDROID_KEYSTORE_PASSWORD:-}" || -n "${ANDROID_KEYSTORE_PATH:-}" || -s "${REPO_ROOT}/.secure_files/${ANDROID_KEYSTORE_FILE:-braving_android.jks}" ]]; then
    echo ""
    echo "Signing release APK via sign-apk.sh..."
    "${SCRIPT_DIR}/sign-apk.sh" --apk="${OUTPUT_APK_DIR}/${OUTPUT_NAME}"
  fi

  # Final refresh of diagnostics archive
  archive_build_artifacts

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
