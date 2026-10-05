#!/usr/bin/env bash
# ==============================================================================
# check-release-needed.sh
#
# Purpose:
#   Lightweight CI preflight script that queries the GitLab Repository Tags API
#   to check if a release tag for 'v${DYNAMIC_BRAVE_VERSION}' already exists.
#
# Behavior:
#   - If tag exists (HTTP 200):
#       Outputs SKIP_BUILD=true to the dotenv file ($BUILD_ENV_FILE).
#       Downstream build/compile jobs can evaluate $SKIP_BUILD to skip costly builds.
#   - If tag does not exist (HTTP 404):
#       Outputs SKIP_BUILD=false to the dotenv file ($BUILD_ENV_FILE).
#       Downstream jobs proceed with compilation and publishing.
#   - If API fails or any other HTTP error occurs:
#       Logs a warning and outputs SKIP_BUILD=false (fail-open) so builds
#       are not blocked by transient API or network glitches.
#
# Environment Variables:
#   - DYNAMIC_BRAVE_VERSION (required): Target Brave version string (e.g., <version>)
#   - BUILD_ENV_FILE        (optional): Path to dotenv output file (default: build.env)
#   - CI_API_V4_URL         (optional): GitLab API v4 root URL
#   - CI_PROJECT_ID         (optional): GitLab Project ID
#   - CI_JOB_TOKEN          (optional): GitLab CI authentication token
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Validate Required Environment Variables
# ------------------------------------------------------------------------------
if [[ -z "${DYNAMIC_BRAVE_VERSION:-}" ]]; then
  echo "ERROR: DYNAMIC_BRAVE_VERSION environment variable is unset or empty." >&2
  exit 1
fi

# Dotenv file path destination (default to build.env if unset)
BUILD_ENV_FILE="${BUILD_ENV_FILE:-build.env}"
TAG_NAME="v${DYNAMIC_BRAVE_VERSION}"

echo "============================================================"
echo " Checking Release Status for Tag: ${TAG_NAME}"
echo " Dotenv Target File: ${BUILD_ENV_FILE}"
echo "============================================================"

# ------------------------------------------------------------------------------
# 2. Helper Functions
# ------------------------------------------------------------------------------
# Writes or updates SKIP_BUILD in the target dotenv file idempotently.
write_skip_build() {
  local skip_value="$1"
  python3 -c '
import sys, os
filepath, val = sys.argv[1], sys.argv[2]
env_vars = {}
if os.path.exists(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip()
env_vars["SKIP_BUILD"] = val.strip()
target_dir = os.path.dirname(filepath)
if target_dir and target_dir != ".":
    os.makedirs(target_dir, exist_ok=True)
with open(filepath, "w", encoding="utf-8") as f:
    for k, v in env_vars.items():
        f.write(f"{k}={v}\n")
' "${BUILD_ENV_FILE}" "${skip_value}"

  echo "Successfully wrote SKIP_BUILD=${skip_value} to ${BUILD_ENV_FILE}"
}

# ------------------------------------------------------------------------------
# 3. Validate GitLab CI API Environment Context
# ------------------------------------------------------------------------------
# When running outside GitLab CI or without API credentials, fail-open to allow
# local or unauthenticated runs to proceed without false rejections.
if [[ -z "${CI_API_V4_URL:-}" || -z "${CI_PROJECT_ID:-}" || -z "${CI_JOB_TOKEN:-}" ]]; then
  echo "WARNING: GitLab CI API variables (CI_API_V4_URL, CI_PROJECT_ID, CI_JOB_TOKEN) are not fully set." >&2
  echo "         Cannot query GitLab Tags API. Failing open (SKIP_BUILD=false)." >&2
  write_skip_build "false"
  exit 0
fi

# ------------------------------------------------------------------------------
# 4. Query GitLab Repository Tags API
# ------------------------------------------------------------------------------
API_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/repository/tags/${TAG_NAME}"

# Temporary buffers for capturing response output and curl diagnostic logs
HTTP_RESPONSE_FILE="$(mktemp /tmp/gitlab-tag-resp.XXXXXX)"
HTTP_ERROR_FILE="$(mktemp /tmp/gitlab-tag-err.XXXXXX)"
trap 'rm -f "${HTTP_RESPONSE_FILE}" "${HTTP_ERROR_FILE}"' EXIT

echo "Querying GitLab API: GET ${API_URL}"

# NOTE: We deliberately do not use --fail because HTTP 404 is a valid, expected
# response indicating the release tag does not exist yet. We capture the HTTP status
# code directly via -w "%{http_code}". We wrap the invocation to handle connection
# errors or transport failures gracefully.
set +e
HTTP_STATUS=$(curl -sSL \
  --connect-timeout 15 \
  --max-time 30 \
  --write-out "%{http_code}" \
  --header "JOB-TOKEN: ${CI_JOB_TOKEN}" \
  -o "${HTTP_RESPONSE_FILE}" \
  "${API_URL}" \
  2>"${HTTP_ERROR_FILE}")
CURL_EXIT_CODE=$?
set -e

# ------------------------------------------------------------------------------
# 5. Evaluate Response and Determine SKIP_BUILD Decision
# ------------------------------------------------------------------------------
# Check for curl execution/network failures
if [[ ${CURL_EXIT_CODE} -ne 0 || "${HTTP_STATUS}" == "000" || -z "${HTTP_STATUS}" ]]; then
  echo "WARNING: Failed to connect to GitLab API (curl exit code: ${CURL_EXIT_CODE}, HTTP status: '${HTTP_STATUS}')." >&2
  if [[ -s "${HTTP_ERROR_FILE}" ]]; then
    echo "curl diagnostic: $(cat "${HTTP_ERROR_FILE}")" >&2
  fi
  echo "Failing open: setting SKIP_BUILD=false so the build pipeline can proceed."
  write_skip_build "false"
  exit 0
fi

case "${HTTP_STATUS}" in
  200)
    echo "Release tag '${TAG_NAME}' already exists in GitLab repository (HTTP 200)."
    echo "Version ${DYNAMIC_BRAVE_VERSION} has already been released. Skipping build."
    write_skip_build "true"
    exit 0
    ;;
  404)
    echo "Release tag '${TAG_NAME}' does not exist in GitLab repository (HTTP 404)."
    echo "A new release is needed for version ${DYNAMIC_BRAVE_VERSION}. Proceeding with build."
    write_skip_build "false"
    exit 0
    ;;
  *)
    echo "WARNING: Unexpected HTTP status code ${HTTP_STATUS} received from GitLab Tags API." >&2
    if [[ -s "${HTTP_RESPONSE_FILE}" ]]; then
      echo "API response body: $(head -c 500 "${HTTP_RESPONSE_FILE}")" >&2
    fi
    echo "Failing open: setting SKIP_BUILD=false so the build pipeline can proceed."
    write_skip_build "false"
    exit 0
    ;;
esac
