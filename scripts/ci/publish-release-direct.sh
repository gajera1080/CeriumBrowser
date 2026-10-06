#!/usr/bin/env bash
# ==============================================================================
# Braving Browser CI/CD — Direct Release Publisher
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
  CI_PROJECT_URL="${CI_PROJECT_URL:-https://gitlab.com/braving/braving-browser}"
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
echo " Braving Direct Release Publisher"
echo " Version     : ${DYNAMIC_BRAVE_VERSION}"
echo " Architecture: ${TARGET_ARCH}"
echo " Dry Run     : ${DRY_RUN}"
echo "=========================================================="

# ------------------------------------------------------------------------------
# 3. Discover APK File
# ------------------------------------------------------------------------------
# Paths searched in order of precedence:
#   1. out/apks/braving-android-${TARGET_ARCH}-v${DYNAMIC_BRAVE_VERSION}.apk
#   2. build-workspace/src/out/Release/apks/*.apk (first match)
APK_PATH=""
CANDIDATE_PRIMARY="${REPO_ROOT}/out/apks/Braving-${DYNAMIC_BRAVE_VERSION}-${TARGET_ARCH}.apk"
CANDIDATE_SECONDARY="${REPO_ROOT}/out/apks/braving-android-${TARGET_ARCH}-v${DYNAMIC_BRAVE_VERSION}.apk"

if [[ -f "${CANDIDATE_PRIMARY}" ]]; then
  APK_PATH="${CANDIDATE_PRIMARY}"
elif [[ -f "${CANDIDATE_SECONDARY}" ]]; then
  APK_PATH="${CANDIDATE_SECONDARY}"
elif [[ -d "${REPO_ROOT}/out/apks" ]]; then
  for candidate in "${REPO_ROOT}/out/apks/"*.apk; do
    if [[ -f "${candidate}" ]]; then
      APK_PATH="${candidate}"
      break
    fi
  done
elif [[ -d "${REPO_ROOT}/build-workspace/src/out/Release/apks" ]]; then
  for candidate in "${REPO_ROOT}/build-workspace/src/out/Release/apks/"*.apk; do
    if [[ -f "${candidate}" ]]; then
      APK_PATH="${candidate}"
      break
    fi
  done
fi

# Fallback: check relative to working directory if REPO_ROOT paths were not matched
if [[ -z "${APK_PATH}" ]]; then
  if [[ -f "out/apks/Braving-${DYNAMIC_BRAVE_VERSION}-${TARGET_ARCH}.apk" ]]; then
    APK_PATH="out/apks/Braving-${DYNAMIC_BRAVE_VERSION}-${TARGET_ARCH}.apk"
  elif [[ -f "out/apks/braving-android-${TARGET_ARCH}-v${DYNAMIC_BRAVE_VERSION}.apk" ]]; then
    APK_PATH="out/apks/braving-android-${TARGET_ARCH}-v${DYNAMIC_BRAVE_VERSION}.apk"
  elif compgen -G "out/apks/*.apk" > /dev/null 2>&1; then
    for candidate in out/apks/*.apk; do
      if [[ -f "${candidate}" ]]; then
        APK_PATH="${candidate}"
        break
      fi
    done
  elif compgen -G "build-workspace/src/out/Release/apks/*.apk" > /dev/null 2>&1; then
    for candidate in build-workspace/src/out/Release/apks/*.apk; do
      if [[ -f "${candidate}" ]]; then
        APK_PATH="${candidate}"
        break
      fi
    done
  fi
fi

if [[ -z "${APK_PATH}" || ! -f "${APK_PATH}" ]]; then
  if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY-RUN] No APK found on disk. Simulating with placeholder path:"
    echo "          out/apks/braving-android-${TARGET_ARCH}-v${DYNAMIC_BRAVE_VERSION}.apk"
    APK_PATH="${CANDIDATE_PRIMARY}"
  else
    echo "ERROR: APK file not found at expected paths:" >&2
    echo "  1) ${CANDIDATE_PRIMARY}" >&2
    echo "  2) ${REPO_ROOT}/build-workspace/src/out/Release/apks/*.apk" >&2
    exit 1
  fi
fi

APK_BASENAME="$(basename "${APK_PATH}")"
echo "Found APK: ${APK_PATH} (${APK_BASENAME})"

# ------------------------------------------------------------------------------
# 4. Resolve SHA256 Checksum
# ------------------------------------------------------------------------------
# Search for SHA256SUMS.txt alongside the APK, or calculate directly
APK_DIR="$(dirname "${APK_PATH}")"
SHA256_FILE="${APK_DIR}/SHA256SUMS.txt"
APK_SHA256=""

if [[ -f "${SHA256_FILE}" ]]; then
  echo "Found SHA256SUMS.txt at: ${SHA256_FILE}"
  MATCHING_LINE="$(grep "${APK_BASENAME}" "${SHA256_FILE}" 2>/dev/null || true)"
  if [[ -n "${MATCHING_LINE}" ]]; then
    APK_SHA256="$(echo "${MATCHING_LINE}" | awk '{print $1}')"
  elif [[ $(wc -l < "${SHA256_FILE}") -eq 1 ]]; then
    APK_SHA256="$(awk '{print $1}' "${SHA256_FILE}")"
  fi
fi

if [[ -z "${APK_SHA256}" && -f "${APK_PATH}" ]]; then
  echo "Computing SHA256 checksum for ${APK_PATH}..."
  APK_SHA256="$(sha256sum "${APK_PATH}" | awk '{print $1}')"
elif [[ -z "${APK_SHA256}" && "${DRY_RUN}" == "true" ]]; then
  APK_SHA256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
fi

if [[ -n "${APK_SHA256}" ]]; then
  echo "APK SHA256: ${APK_SHA256}"
fi

# ------------------------------------------------------------------------------
# 5. Step 1: Upload Release Assets to GitLab Generic Package Registry
# ------------------------------------------------------------------------------
# We use the GitLab Generic Package Registry instead of /projects/:id/uploads
# because the uploads endpoint returns HTTP 401 Unauthorized with CI_JOB_TOKEN,
# whereas the Generic Package Registry natively authenticates via JOB-TOKEN: ${CI_JOB_TOKEN}
# and provides permanent, direct package URLs suitable for release asset links.
PACKAGE_NAME="braving-release"
PACKAGE_VERSION="${DYNAMIC_BRAVE_VERSION}"
PACKAGE_REGISTRY_BASE="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/${PACKAGE_NAME}/${PACKAGE_VERSION}"
FULL_APK_URL="${PACKAGE_REGISTRY_BASE}/${APK_BASENAME}"
FULL_SHA256_URL="${PACKAGE_REGISTRY_BASE}/SHA256SUMS.txt"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo ""
  echo "--- [DRY-RUN] Step 1: Upload Release Assets to Generic Package Registry ---"
  echo "Executing command (simulated):"
  echo "  curl --fail-with-body \\"
  echo "    --header \"JOB-TOKEN: [MASKED]\" \\"
  echo "    --upload-file \"${APK_PATH}\" \\"
  echo "    \"${FULL_APK_URL}\""
  echo "Simulated Package URL: ${FULL_APK_URL}"
  if [[ -f "${SHA256_FILE}" ]]; then
    echo "Simulated SHA256SUMS URL: ${FULL_SHA256_URL}"
  fi
else
  echo ""
  echo "--- Step 1: Uploading Release Assets to GitLab Generic Package Registry ---"
  echo "Uploading APK package: ${APK_BASENAME}..."
  curl --fail-with-body --silent --show-error --location \
    --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
    --upload-file "${APK_PATH}" \
    "${FULL_APK_URL}"
  echo "APK package upload complete: ${FULL_APK_URL}"

  if [[ -f "${SHA256_FILE}" ]]; then
    echo "Uploading SHA256SUMS.txt to Generic Package Registry..."
    curl --fail-with-body --silent --show-error --location \
      --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
      --upload-file "${SHA256_FILE}" \
      "${FULL_SHA256_URL}"
    echo "SHA256SUMS upload complete: ${FULL_SHA256_URL}"
  fi
fi

# ------------------------------------------------------------------------------
# 6. Step 2: Build GitLab Release JSON Payload
# ------------------------------------------------------------------------------
# Build the JSON payload using python3 -c to safely handle multiline formatting,
# quote escaping, and special characters.
SHA256_URL_ARG=""
if [[ -f "${SHA256_FILE}" ]]; then
  SHA256_URL_ARG="${FULL_SHA256_URL}"
fi

RELEASE_PAYLOAD="$(python3 -c '
import json, sys

version = sys.argv[1]
arch = sys.argv[2]
commit_sha = sys.argv[3]
apk_url = sys.argv[4]
sha256 = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else ""
apk_name = sys.argv[6] if len(sys.argv) > 6 and sys.argv[6] else f"Braving-{version}-{arch}.apk"
chromium_version = sys.argv[7] if len(sys.argv) > 7 and sys.argv[7] else ""
sha256_url = sys.argv[8] if len(sys.argv) > 8 and sys.argv[8] else ""

chromium_part = f" and Chromium v{chromium_version}" if chromium_version else ""

description_lines = [
    f"Updated to v{version}{chromium_part}\n",
    "### Android",
    f"- [{apk_name}]({apk_url})",
    f"- **Architecture**: `{arch}`",
]
if sha256:
    description_lines.append(f"- **SHA256**: `{sha256}`")

description_lines.extend([
    "\n### Debloated Features",
    "- Brave Wallet / Crypto",
    "- AI Chat / Leo",
    "- Brave VPN",
    "- Brave News",
    "- Brave Rewards / BAT Ads",
    "- P3A Telemetry\n",
])

description = "\n".join(description_lines)

links = [
    {
        "name": apk_name,
        "url": apk_url,
        "link_type": "package",
    }
]
if sha256_url:
    links.append({
        "name": "SHA256SUMS.txt",
        "url": sha256_url,
        "link_type": "package",
    })

payload = {
    "name": f"Release v{version}",
    "tag_name": f"v{version}",
    "ref": commit_sha,
    "description": description,
    "assets": {
        "links": links
    }
}

print(json.dumps(payload))
' "${DYNAMIC_BRAVE_VERSION}" "${TARGET_ARCH}" "${CI_COMMIT_SHA}" "${FULL_APK_URL}" "${APK_SHA256}" "${APK_BASENAME}" "${DYNAMIC_CHROMIUM_VERSION}" "${SHA256_URL_ARG}")"

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
  echo "--- Step 2: Creating GitLab Release v${DYNAMIC_BRAVE_VERSION} ---"
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
    echo "Release v${DYNAMIC_BRAVE_VERSION} already exists (HTTP 409). Updating release..."
    curl --fail-with-body --silent --show-error \
      --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
      --header "Content-Type: application/json" \
      --request PUT \
      "${RELEASES_ENDPOINT}/v${DYNAMIC_BRAVE_VERSION}" \
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
RELEASE_WEB_URL="${CI_PROJECT_URL%/}/-/releases/v${DYNAMIC_BRAVE_VERSION}"

echo ""
echo "=========================================================="
if [[ "${DRY_RUN}" == "true" ]]; then
  echo " [DRY-RUN] Release publication simulated successfully!"
else
  echo " Release published successfully!"
fi
echo " Release URL : ${RELEASE_WEB_URL}"
echo " Direct APK  : ${FULL_APK_URL}"
if [[ -n "${APK_SHA256}" ]]; then
  echo " SHA256      : ${APK_SHA256}"
fi
echo " Tag Created : v${DYNAMIC_BRAVE_VERSION} (ref: ${CI_COMMIT_SHA})"
echo "=========================================================="
