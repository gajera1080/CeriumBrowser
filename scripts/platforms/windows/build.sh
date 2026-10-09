#!/usr/bin/env bash
# Braving — Windows Compilation Entry Point
# Usage: ./scripts/platforms/windows/build.sh [--manifest=<path>] [--arch=x64|arm64] [--release] [--dry-run] [--gn-only]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

MANIFEST=""
TARGET_ARCH="x64"
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
        all)
          PASS_ARGS=()
          for a in "$@"; do
            [[ "$a" != --arch=* ]] && PASS_ARGS+=("$a")
          done
          "$0" "${PASS_ARGS[@]}" --arch=x64
          "$0" "${PASS_ARGS[@]}" --arch=arm64
          exit 0
          ;;
        x64|arm64) ;;
        x86_64|amd64) TARGET_ARCH="x64" ;;
        aarch64) TARGET_ARCH="arm64" ;;
        *) echo "ERROR: Invalid architecture: ${TARGET_ARCH}" >&2; exit 1 ;;
      esac
      shift
      ;;
    --package)
      PACKAGE_OUTPUT=true
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
MANIFEST="$(cd "$(dirname "${MANIFEST}")" && pwd)/$(basename "${MANIFEST}")"

echo "========================================================"
echo " Braving Windows Build"
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

export BRAVE_VERSION
export DYNAMIC_BRAVE_VERSION="${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION}}"
export TARGET_ARCH

echo "Manifest Target Revisions:"
echo " - brave-core version: ${BRAVE_VERSION} (${BRAVE_CORE_COMMIT})"
echo " - Chromium version  : ${CHROMIUM_VERSION} (${CHROMIUM_COMMIT})"

# Step 2: Verify Required Tools
echo ""
echo "Verifying build tools..."
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required." >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "ERROR: git is required." >&2; exit 1; }

WORKSPACE_DIR="${WORKSPACE_DIR:-${REPO_ROOT}/build-workspace}"
SRC_DIR="${WORKSPACE_DIR}/src"
BRAVE_DIR="${SRC_DIR}/brave"
OUT_DIR="${SRC_DIR}/out/Release"
GN_ARGS_FILE="${OUT_DIR}/args.gn"

echo "Build workspace: ${WORKSPACE_DIR}"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Dry-run mode requested. Validation complete."
  exit 0
fi

# Full build requires node and pnpm
command -v node >/dev/null 2>&1 || { echo "ERROR: node is required." >&2; exit 1; }
command -v pnpm >/dev/null 2>&1 || { echo "ERROR: pnpm is required." >&2; exit 1; }

if [[ ! -d "${BRAVE_DIR}" ]]; then
  echo "ERROR: Prepared brave-core not found in ${BRAVE_DIR}." >&2
  exit 1
fi


CHROMIUM_ARCHIVE="${WORKSPACE_DIR}/chromium-src-${CHROMIUM_VERSION}.tar.xz"
if [[ ! -d "${SRC_DIR}/.git" ]]; then
  if [[ -f "${CHROMIUM_ARCHIVE}" ]]; then
    echo ""
    echo "Unpacking base Chromium source from ${CHROMIUM_ARCHIVE}..."
    tar -xf "${CHROMIUM_ARCHIVE}" -C "${WORKSPACE_DIR}"
    rm -f "${CHROMIUM_ARCHIVE}"
  else
    echo "ERROR: Base Chromium source not found in ${SRC_DIR}." >&2
    echo "Please ensure scripts/core/sync-chromium-source.sh has been run." >&2
    exit 1
  fi
else
  echo "Chromium source directory already exists, resetting to clean state..."
  git -C "${SRC_DIR}" reset --hard HEAD
  git -C "${SRC_DIR}" clean -ffd
fi

DEPOT_TOOLS_DIR="${WORKSPACE_DIR}/depot_tools"
if [[ ! -d "${DEPOT_TOOLS_DIR}" ]]; then
  echo ""
  echo "Fetching depot_tools..."
  git clone --depth 1 "https://chromium.googlesource.com/chromium/tools/depot_tools.git" "${DEPOT_TOOLS_DIR}"
  echo "Bootstrapping depot_tools..."
  "${DEPOT_TOOLS_DIR}/ensure_bootstrap" || "${DEPOT_TOOLS_DIR}/update_depot_tools"
else
  echo "Using pre-bootstrapped depot_tools from cache: ${DEPOT_TOOLS_DIR}"
fi
export PATH="${DEPOT_TOOLS_DIR}:${PATH}"
export DEPOT_TOOLS_UPDATE=0

# Step 2a: Git compatibility shim for depot_tools when running on Git < 2.43.1
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

# Step 2b: Generate .gclient configuration for Windows
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
target_os = ["win"]
target_cpu = ["${TARGET_ARCH}"]
EOF

# Step 2c: Sync Chromium DEPS dependencies via gclient
echo ""
export PYTHONPATH="${BRAVE_DIR}/script:${SRC_DIR}/tools/grit/grit/extern:${BRAVE_DIR}/vendor/requests:${BRAVE_DIR}/third_party/cryptography:${BRAVE_DIR}/third_party/macholib:${SRC_DIR}/build:${SRC_DIR}/third_party/depot_tools${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUNBUFFERED="1"

echo "1. Syncing Chromium DEPS dependencies via gclient (shallow, no history, NOHOOKS)..."
(cd "${WORKSPACE_DIR}" && gclient sync --no-history --shallow --nohooks -j16)

echo ""
echo "2. Installing brave-core node dependencies and applying upstream Brave patches to Chromium..."
(cd "${BRAVE_DIR}" && pnpm install --frozen-lockfile)
(cd "${BRAVE_DIR}" && pnpm run apply_patches)

# Prepare Chromium VERSION and apply mutators
if [[ -f "${SRC_DIR}/chrome/VERSION" ]]; then
  echo ""
  echo "3. Preparing Chromium VERSION and VERSION.chromium sidecar (Brave ${BRAVE_VERSION})..."
  if [[ -f "${BRAVE_DIR}/build/util/version.py" && -n "${BRAVE_VERSION}" ]]; then
    python3 "${BRAVE_DIR}/build/util/version.py" update --brave-version "${BRAVE_VERSION}" "${SRC_DIR}/chrome/VERSION"
  fi
  echo "Applying mutators to brave-core and Chromium src..."
  python3 "${REPO_ROOT}/scripts/core/apply-features.py" "${BRAVE_DIR}" --strict --src-dir="${SRC_DIR}" --target-os=win
fi

echo ""
echo "4. Running gclient hooks on patched Chromium..."
(cd "${WORKSPACE_DIR}" && gclient runhooks)

# Propagate branding from brave-core/app/theme/brave_origin
if command -v pnpm >/dev/null 2>&1 && [[ -f "${BRAVE_DIR}/package.json" ]]; then
  echo ""
  echo "5. Propagating branding from brave-core/app/theme/brave_origin..."
  (cd "${BRAVE_DIR}" && pnpm run build Release --prepare_only --target_os=win --target_arch="${TARGET_ARCH}" --channel=release)
fi

# Generate brave/build/version.gni if missing
if [[ -f "${BRAVE_DIR}/build/util/version.py" && -f "${SRC_DIR}/chrome/VERSION" && ! -f "${BRAVE_DIR}/build/version.gni" ]]; then
  echo "Generating brave/build/version.gni..."
  python3 "${BRAVE_DIR}/build/util/version.py" gen "${SRC_DIR}/chrome/VERSION"
fi

# Ensure hermetic GN binary is present in buildtools/linux64
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

mkdir -p "${OUT_DIR}"

echo "Generating Windows args.gn with Brave Origin branding..."
cat <<EOF > "${GN_ARGS_FILE}"
is_debug = false
is_official_build = true
is_component_build = false
symbol_level = 0
target_os = "win"
target_cpu = "${TARGET_ARCH}"
is_brave_origin_branded = true
use_siso = true
exclude_unwind_tables = true
dcheck_always_on = false

# Debloated subsystems enforced via policies
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
echo "Windows GN arguments configured:"
cat "${GN_ARGS_FILE}"

echo ""
echo "Running gn gen from source root..."
cd "${SRC_DIR}" && gn gen "${OUT_DIR}"

if [[ "${GN_ONLY}" == "true" ]]; then
  echo "========================================================"
  echo " [SUCCESS] Windows GN configuration passed (--gn-only)."
  echo "========================================================"
  exit 0
fi

BUILD_TARGET="${BUILD_TARGET:-brave}"
echo "Building Windows target: ${BUILD_TARGET}..."
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

set -e
set -o pipefail

if [[ "${CACHE_PREP_ONLY:-false}" == "true" ]]; then
  echo "CACHE_PREP_ONLY=true: Skipping Windows packaging."
  exit 0
fi

if [[ "${PACKAGE_OUTPUT:-false}" == "true" ]]; then
  echo "Packaging Windows distribution..."
  "${SCRIPT_DIR}/package.sh" --out-dir="${OUT_DIR}" --arch="${TARGET_ARCH}" --version="${DYNAMIC_BRAVE_VERSION}"
fi

echo "Windows build finished successfully."
