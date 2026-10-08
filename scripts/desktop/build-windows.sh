#!/usr/bin/env bash
# Braving — Windows Compilation Entry Point
# Usage: ./scripts/desktop/build-windows.sh [--manifest=<path>] [--arch=x64|arm64] [--release] [--dry-run] [--gn-only]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

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

DEPOT_TOOLS_DIR="${WORKSPACE_DIR}/depot_tools"
if [[ -d "${DEPOT_TOOLS_DIR}" ]]; then
  export PATH="${DEPOT_TOOLS_DIR}:${PATH}"
fi

# Apply cross-platform & Windows mutators to brave-core and Chromium src
if [[ -d "${SRC_DIR}" && -d "${BRAVE_DIR}" ]]; then
  echo "Applying mutators to brave-core and Chromium src..."
  python3 "${REPO_ROOT}/scripts/android/apply-features.py" "${BRAVE_DIR}" --strict --src-dir="${SRC_DIR}" --target-os=win
fi

# Propagate branding from brave-core/app/theme/brave_origin
if command -v pnpm >/dev/null 2>&1 && [[ -f "${BRAVE_DIR}/package.json" ]]; then
  echo "Propagating branding from brave-core/app/theme/brave_origin..."
  (cd "${BRAVE_DIR}" && pnpm run build Release --prepare_only --target_os=win --target_arch="${TARGET_ARCH}" --channel=release)
fi

# Generate brave/build/version.gni if missing
if [[ -f "${BRAVE_DIR}/build/util/version.py" && -f "${SRC_DIR}/chrome/VERSION" && ! -f "${BRAVE_DIR}/build/version.gni" ]]; then
  echo "Generating brave/build/version.gni..."
  python3 "${BRAVE_DIR}/build/util/version.py" gen "${SRC_DIR}/chrome/VERSION"
fi

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

if [[ "${GN_ONLY}" == "true" ]]; then
  echo ""
  echo "Running gn gen from source root..."
  cd "${SRC_DIR}" && gn gen "${OUT_DIR}"
  echo "========================================================"
  echo " [SUCCESS] Windows GN configuration passed (--gn-only)."
  echo "========================================================"
  exit 0
fi

BUILD_TARGET="${BUILD_TARGET:-brave}"
echo "Building Windows target: ${BUILD_TARGET}..."
cd "${SRC_DIR}"
read -r -a BUILD_TARGETS <<< "${BUILD_TARGET}"
autoninja -C "${OUT_DIR}" "${BUILD_TARGETS[@]}"

if [[ "${PACKAGE_OUTPUT:-false}" == "true" ]]; then
  echo "Packaging Windows distribution..."
  "${SCRIPT_DIR}/package-windows.sh" --out-dir="${OUT_DIR}" --arch="${TARGET_ARCH}" --version="${DYNAMIC_BRAVE_VERSION}"
fi

echo "Windows build finished successfully."
