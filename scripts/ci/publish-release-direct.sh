#!/usr/bin/env bash
# ==============================================================================
# Cerium Browser CI/CD — Direct Release Publisher
# ==============================================================================
# Purpose:
#   Uploads the signed release APK directly to GitLab project uploads and
#   creates an official GitLab Release with a direct download asset link.
#   Automatically creates the Git tag `v<version>` referenced to CI_COMMIT_SHA.
#
# Requirements & Principles:
#   - set -euo pipefail for robust error handling.
#   - CI_JOB_TOKEN for GitLab API authentication (JOB-TOKEN header).
#   - Dynamic versioning without hardcoded release versions.
#   - Safe JSON serialization & parsing via python3 -c to avoid escaping bugs.
#   - Supports --dry-run mode to inspect payloads and actions safely.
#
# Usage:
#   ./scripts/ci/publish-release-direct.sh [--dry-run]
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Parse Arguments & Initialize Options
# ------------------------------------------------------------------------------
DRY_RUN=false

for arg in "$@"; do
  case "${arg}" in
    --dry-run)
      DRY_RUN=true
      ;;
    -h|--help)
      echo "Usage: $0 [--dry-run]"
      echo "Publishes signed APK and creates a GitLab release via the GitLab API."
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: ${arg}" >&2
      echo "Usage: $0 [--dry-run]" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# ------------------------------------------------------------------------------
# 2. Validate Environment Variables
# ------------------------------------------------------------------------------
# Version resolution: DYNAMIC_BRAVE_VERSION preferred, fallback to BRAVE_VERSION
DYNAMIC_BRAVE_VERSION="${DYNAMIC_BRAVE_VERSION:-${BRAVE_VERSION:-}}"
TARGET_ARCH="${TARGET_ARCH:-arm64}"
TARGET_PLATFORM="${TARGET_PLATFORM:-android}"
if [[ "${CI_COMMIT_REF_NAME:-}" == "release" || "${CI_COMMIT_BRANCH:-}" == "release" || -z "${TARGET_PLATFORM:-}" || "${TARGET_PLATFORM}" == "all" ]]; then
  RELEASE_TAG="v${DYNAMIC_BRAVE_VERSION}"
else
  RELEASE_TAG="v${DYNAMIC_BRAVE_VERSION}-${TARGET_PLATFORM}"
fi

DYNAMIC_CHROMIUM_VERSION="${DYNAMIC_CHROMIUM_VERSION:-${CHROMIUM_VERSION:-}}"

if [[ -z "${DYNAMIC_CHROMIUM_VERSION}" && -f "${REPO_ROOT}/metadata/releases/${DYNAMIC_BRAVE_VERSION}.yaml" ]]; then
  DYNAMIC_CHROMIUM_VERSION="$(grep -E '^chromium_version:' "${REPO_ROOT}/metadata/releases/${DYNAMIC_BRAVE_VERSION}.yaml" | awk '{print $2}' | tr -d '"' | tr -d "'" || true)"
fi

declare -a MISSING_VARS=()

if [[ -z "${DYNAMIC_BRAVE_VERSION}" ]]; then
  MISSING_VARS+=("DYNAMIC_BRAVE_VERSION")
fi

if [[ -z "${TARGET_ARCH}" ]]; then
  MISSING_VARS+=("TARGET_ARCH")
fi

if [[ "${DRY_RUN}" == "true" ]]; then
  # In dry-run mode, provide fallback values for CI environment variables if unset
  CI_JOB_TOKEN="${CI_JOB_TOKEN:-dry-run-token}"
  CI_API_V4_URL="${CI_API_V4_URL:-https://gitlab.com/api/v4}"
  CI_PROJECT_ID="${CI_PROJECT_ID:-dry-run-project-id}"
  CI_PROJECT_URL="${CI_PROJECT_URL:-https://gitlab.com/CeriumBrowser/Cerium-Browser}"
  CI_COMMIT_SHA="${CI_COMMIT_SHA:-$(git -C "${REPO_ROOT}" rev-parse HEAD 2>/dev/null || echo "0000000000000000000000000000000000000000")}"
else
  # In live execution mode, strictly enforce all required GitLab CI variables
  [[ -z "${CI_JOB_TOKEN:-}" ]] && MISSING_VARS+=("CI_JOB_TOKEN")
  [[ -z "${CI_API_V4_URL:-}" ]] && MISSING_VARS+=("CI_API_V4_URL")
  [[ -z "${CI_PROJECT_ID:-}" ]] && MISSING_VARS+=("CI_PROJECT_ID")
  [[ -z "${CI_PROJECT_URL:-}" ]] && MISSING_VARS+=("CI_PROJECT_URL")
  [[ -z "${CI_COMMIT_SHA:-}" ]] && MISSING_VARS+=("CI_COMMIT_SHA")
fi

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
  echo "ERROR: Required environment variable(s) missing: ${MISSING_VARS[*]}" >&2
  exit 1
fi

echo "=========================================================="
echo " Cerium Direct Release Publisher"
echo " Version     : ${DYNAMIC_BRAVE_VERSION}"
echo " Architecture: ${TARGET_ARCH}"
echo " Dry Run     : ${DRY_RUN}"
echo "=========================================================="

# ------------------------------------------------------------------------------
# 3. Discover Release Artifact Files
# ------------------------------------------------------------------------------
declare -a PACKAGES_FOUND=()

# Search Android APKs
for d in "${REPO_ROOT}/out/apks" "out/apks" "${REPO_ROOT}/build-workspace/src/out/Release/apks"; do
  if [[ -d "$d" ]]; then
    for f in "$d"/*.apk; do
      [[ -f "$f" ]] && PACKAGES_FOUND+=("$f")
    done
  fi
done

# Search Windows packages (both zip archives and installer executables across all architectures)
for d in "${REPO_ROOT}/out/packages" "out/packages"; do
  if [[ -d "$d" ]]; then
    for f in "$d"/Cerium-Windows-*.zip "$d"/Cerium-Installer-*.exe "$d"/Braving-Windows-*.zip "$d"/Braving-Installer-*.exe; do
      [[ -f "$f" ]] && PACKAGES_FOUND+=("$f")
    done
  fi
done

# Deduplicate
if [[ ${#PACKAGES_FOUND[@]} -gt 0 ]]; then
  mapfile -t PACKAGES_FOUND < <(printf "%s\n" "${PACKAGES_FOUND[@]}" | sort -u)
fi

if [[ ${#PACKAGES_FOUND[@]} -eq 0 ]]; then
  if [[ "${DRY_RUN}" == "true" ]]; then
    if [[ "${CI_COMMIT_REF_NAME:-}" == "release" || "${CI_COMMIT_BRANCH:-}" == "release" ]]; then
      echo "[DRY-RUN] Simulating full multi-architecture release on release branch:"
      PACKAGES_FOUND+=(
        "${REPO_ROOT}/out/apks/Cerium-${DYNAMIC_BRAVE_VERSION}-arm64.apk"
        "${REPO_ROOT}/out/packages/Cerium-Windows-x64-v${DYNAMIC_BRAVE_VERSION}.zip"
        "${REPO_ROOT}/out/packages/Cerium-Windows-arm64-v${DYNAMIC_BRAVE_VERSION}.zip"
      )
    elif [[ "${TARGET_PLATFORM}" == "windows" ]]; then
      echo "[DRY-RUN] Simulating Windows release package:"
      PACKAGES_FOUND+=("${REPO_ROOT}/out/packages/Cerium-Windows-${TARGET_ARCH}-v${DYNAMIC_BRAVE_VERSION}.zip")
    else
      echo "[DRY-RUN] Simulating Android release package:"
      PACKAGES_FOUND+=("${REPO_ROOT}/out/apks/Cerium-${DYNAMIC_BRAVE_VERSION}-${TARGET_ARCH}.apk")
    fi
  else
    echo "ERROR: No release packages found in out/apks or out/packages!" >&2
    exit 1
  fi
fi

# ------------------------------------------------------------------------------
# 4. Upload Release Assets to GitLab Generic Package Registry
# ------------------------------------------------------------------------------
PACKAGE_NAME="cerium-release"
PACKAGE_VERSION="${DYNAMIC_BRAVE_VERSION}"
PACKAGE_REGISTRY_BASE="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/${PACKAGE_NAME}/${PACKAGE_VERSION}"
MASTER_SHA256_FILE="$(mktemp /tmp/master-sha256-XXXXXX.txt)"
trap 'rm -f "${MASTER_SHA256_FILE}"' EXIT

declare -a UPLOADED_ITEMS_JSON=()

echo ""
echo "--- Step 1: Uploading Release Assets to GitLab Generic Package Registry ---"

for pkg in "${PACKAGES_FOUND[@]}"; do
  bname="$(basename "$pkg")"
  pkg_url="${PACKAGE_REGISTRY_BASE}/${bname}"

  # Determine architecture from filename or TARGET_ARCH
  pkg_arch="${TARGET_ARCH}"
  if [[ "$bname" =~ arm64 ]]; then
    pkg_arch="arm64"
  elif [[ "$bname" =~ x64 ]]; then
    pkg_arch="x64"
  elif [[ "$bname" =~ arm ]]; then
    pkg_arch="arm"
  fi

  # Determine platform
  pkg_platform="android"
  if [[ "$bname" =~ \.zip$ || "$bname" =~ \.exe$ ]]; then
    pkg_platform="windows"
  fi

  # Compute or look up SHA256
  pkg_sha=""
  dir="$(dirname "$pkg")"
  if [[ -f "${dir}/SHA256SUMS.txt" ]]; then
    pkg_sha="$(grep "${bname}" "${dir}/SHA256SUMS.txt" 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [[ -z "${pkg_sha}" && -f "${pkg}" ]]; then
    pkg_sha="$(sha256sum "${pkg}" | awk '{print $1}')"
  elif [[ -z "${pkg_sha}" && "${DRY_RUN}" == "true" ]]; then
    pkg_sha="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  fi

  echo "${pkg_sha}  ${bname}" >> "${MASTER_SHA256_FILE}"

  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY-RUN] Upload ${bname} -> ${pkg_url}"
  else
    echo "Uploading package: ${bname}..."
    curl --fail-with-body --silent --show-error --location \
      --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
      --upload-file "${pkg}" \
      "${pkg_url}"
    echo "Package upload complete: ${pkg_url}"
  fi

  item_json=$(python3 -c "import json, sys; print(json.dumps({'name': sys.argv[1], 'url': sys.argv[2], 'sha256': sys.argv[3], 'platform': sys.argv[4], 'arch': sys.argv[5]}))" \
    "${bname}" "${pkg_url}" "${pkg_sha}" "${pkg_platform}" "${pkg_arch}")
  UPLOADED_ITEMS_JSON+=("${item_json}")
done

FULL_SHA256_URL="${PACKAGE_REGISTRY_BASE}/SHA256SUMS.txt"
if [[ "${DRY_RUN}" == "true" ]]; then
  echo "[DRY-RUN] Upload SHA256SUMS.txt -> ${FULL_SHA256_URL}"
else
  curl --fail-with-body --silent --show-error --location \
    --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
    --upload-file "${MASTER_SHA256_FILE}" \
    "${FULL_SHA256_URL}"
fi

# ------------------------------------------------------------------------------
# 5. Step 2: Build GitLab Release JSON Payload
# ------------------------------------------------------------------------------
RELEASE_PAYLOAD="$(python3 - "${DYNAMIC_BRAVE_VERSION}" "${CI_COMMIT_SHA}" "${DYNAMIC_CHROMIUM_VERSION}" "${FULL_SHA256_URL}" "${RELEASE_TAG}" "${UPLOADED_ITEMS_JSON[@]}" <<'PYEOF'
import json, sys

version = sys.argv[1]
commit_sha = sys.argv[2]
chromium_version = sys.argv[3]
sha256_url = sys.argv[4]
tag_name = sys.argv[5]
items = [json.loads(x) for x in sys.argv[6:]]

chromium_part = f" and Chromium v{chromium_version}" if chromium_version else ""
description_lines = [f"Updated to v{version}{chromium_part}\n"]

android_items = [it for it in items if it["platform"] == "android"]
windows_items = [it for it in items if it["platform"] == "windows"]

if android_items:
    description_lines.append("### Android")
    for it in android_items:
        description_lines.append(f"- [{it['name']}]({it['url']})")
        description_lines.append(f"  - **Architecture**: `{it['arch']}`")
        if it["sha256"]:
            description_lines.append(f"  - **SHA256**: `{it['sha256']}`")
    description_lines.append("")

if windows_items:
    description_lines.append("### Windows")
    for it in windows_items:
        description_lines.append(f"- [{it['name']}]({it['url']})")
        description_lines.append(f"  - **Architecture**: `{it['arch']}`")
        if it["sha256"]:
            description_lines.append(f"  - **SHA256**: `{it['sha256']}`")
    description_lines.append("")

description_lines.extend([
    "### Debloated Features",
    "- Brave Wallet / Crypto",
    "- AI Chat / Leo",
    "- Brave VPN",
    "- Brave News",
    "- Brave Rewards / BAT Ads",
    "- P3A Telemetry\n",
])

links = [{"name": it["name"], "url": it["url"], "link_type": "package"} for it in items]
if sha256_url:
    links.append({"name": "SHA256SUMS.txt", "url": sha256_url, "link_type": "package"})

payload = {
    "name": f"Release v{version}",
    "tag_name": tag_name,
    "ref": commit_sha,
    "description": "\n".join(description_lines),
    "assets": {"links": links}
}

print(json.dumps(payload))
PYEOF
)"

# ------------------------------------------------------------------------------
# 7. Step 3: Create GitLab Release via Releases API
# ------------------------------------------------------------------------------
RELEASES_ENDPOINT="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/releases"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo ""
  echo "--- [DRY-RUN] Step 2: Create GitLab Release ---"
  echo "Executing command (simulated):"
  echo "  curl --fail-with-body \\"
  echo "    --header \"JOB-TOKEN: [MASKED]\" \\"
  echo "    --header \"Content-Type: application/json\" \\"
  echo "    --request POST \\"
  echo "    \"${RELEASES_ENDPOINT}\" \\"
  echo "    --data '<PAYLOAD>'"
  echo ""
  echo "Generated JSON Payload:"
  python3 -m json.tool <<< "${RELEASE_PAYLOAD}"
else
  echo ""
  echo "--- Step 2: Creating GitLab Release ${RELEASE_TAG} ---"
  TMP_RESPONSE="$(mktemp /tmp/gitlab-release-response-XXXXXX.json)"
  trap 'rm -f "${TMP_RESPONSE}"' EXIT

  HTTP_CODE="$(curl --silent --show-error --output "${TMP_RESPONSE}" --write-out "%{http_code}" \
    --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
    --header "Content-Type: application/json" \
    --request POST \
    "${RELEASES_ENDPOINT}" \
    --data "${RELEASE_PAYLOAD}")"

  if [[ "${HTTP_CODE}" == "201" || "${HTTP_CODE}" == "200" ]]; then
    echo "GitLab Release successfully created via API."
  elif [[ "${HTTP_CODE}" == "409" ]]; then
    echo "Release ${RELEASE_TAG} already exists (HTTP 409). Updating release..."
    curl --fail-with-body --silent --show-error \
      --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
      --header "Content-Type: application/json" \
      --request PUT \
      "${RELEASES_ENDPOINT}/${RELEASE_TAG}" \
      --data "${RELEASE_PAYLOAD}"
    echo "GitLab Release successfully updated via API."
  else
    echo "ERROR: Failed to create release (HTTP ${HTTP_CODE}):" >&2
    cat "${TMP_RESPONSE}" >&2
    exit 1
  fi
fi

# ------------------------------------------------------------------------------
# 8. Print Release URL on Success
# ------------------------------------------------------------------------------
RELEASE_WEB_URL="${CI_PROJECT_URL%/}/-/releases/${RELEASE_TAG}"

echo ""
echo "=========================================================="
if [[ "${DRY_RUN}" == "true" ]]; then
  echo " [DRY-RUN] Release publication simulated successfully!"
else
  echo " Release published successfully!"
fi
echo " Release URL : ${RELEASE_WEB_URL}"
echo " Packages    : ${#PACKAGES_FOUND[@]} published to ${PACKAGE_REGISTRY_BASE}"
echo " Checksums   : ${FULL_SHA256_URL}"
echo " Tag Created : ${RELEASE_TAG} (ref: ${CI_COMMIT_SHA})"
echo "=========================================================="
