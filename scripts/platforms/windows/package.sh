#!/usr/bin/env bash
# Braving — Windows Packaging Script
# Usage: ./scripts/platforms/windows/package.sh [--out-dir=<path>] [--dest-dir=<path>] [--arch=x64|arm64] [--version=<ver>] [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

WORKSPACE_DIR="${WORKSPACE_DIR:-${REPO_ROOT}/build-workspace}"
OUT_DIR="${WORKSPACE_DIR}/src/out/Release"
DEST_DIR="${REPO_ROOT}/out/packages"
TARGET_ARCH="x64"
VERSION="${DYNAMIC_BRAVE_VERSION:-}"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir=*)
      OUT_DIR="${1#*=}"
      shift
      ;;
    --dest-dir=*|--dist-dir=*)
      DEST_DIR="${1#*=}"
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
    --version=*)
      VERSION="${1#*=}"
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

if [[ -z "${VERSION}" ]]; then
  MANIFEST=$(ls -t "${REPO_ROOT}/metadata/releases"/*.yaml 2>/dev/null | head -n 1 || true)
  if [[ -n "${MANIFEST}" && -f "${MANIFEST}" ]]; then
    VERSION=$(python3 -c "import sys, yaml; print(yaml.safe_load(open(sys.argv[1])).get('brave_version', ''))" "${MANIFEST}" 2>/dev/null || true)
  fi
  VERSION="${VERSION:-0.0.0}"
fi

echo "========================================================"
echo " Braving Windows Package"
echo " Version     : ${VERSION}"
echo " Architecture: ${TARGET_ARCH}"
echo " Source Dir  : ${OUT_DIR}"
echo " Output Dir  : ${DEST_DIR}"
echo "========================================================"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Dry-run mode requested. Windows packaging validation complete."
  exit 0
fi

if [[ ! -d "${OUT_DIR}" ]]; then
  echo "ERROR: Windows output directory not found: ${OUT_DIR}" >&2
  exit 1
fi
command -v zip >/dev/null 2>&1 || { echo "ERROR: zip is required." >&2; exit 1; }

mkdir -p "${DEST_DIR}"
ZIP_NAME="Braving-Windows-${TARGET_ARCH}-v${VERSION}.zip"
ZIP_PATH="${DEST_DIR}/${ZIP_NAME}"

echo "Packaging standalone Windows distribution into ${ZIP_NAME}..."
# Exclude intermediate build artifacts, object files, and build graph databases
(cd "${OUT_DIR}" && zip -q -r -9 "${ZIP_PATH}" . \
  -x "*.ninja*" "obj/*" "gen/*" ".siso*" "*.log" "build.ninja*" "args.gn")

# Copy installer if generated
if [[ -f "${OUT_DIR}/mini_installer.exe" ]]; then
  INSTALLER_NAME="Braving-Installer-${TARGET_ARCH}-v${VERSION}.exe"
  echo "Found mini_installer.exe. Copying to ${DEST_DIR}/${INSTALLER_NAME}..."
  cp "${OUT_DIR}/mini_installer.exe" "${DEST_DIR}/${INSTALLER_NAME}"
fi

# Generate SHA256 checksums
echo "Generating SHA256SUMS.txt..."
(cd "${DEST_DIR}" && sha256sum Braving-* > SHA256SUMS.txt)

echo "========================================================"
echo " [SUCCESS] Windows packaging completed successfully."
echo " Output artifacts in ${DEST_DIR}"
echo "========================================================"
