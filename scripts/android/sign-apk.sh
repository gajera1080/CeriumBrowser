#!/usr/bin/env bash
# Braving — Android APK Release Signing & Verification Script
# Downloads `braving_android.jks` from GitLab Secure Files (if not already present),
# aligns the APK with `zipalign`, signs it with `apksigner` using alias `braving`
# and `KEY_PASSWORD_ANDROID`, and verifies the signature with `apksigner verify`.
#
# Usage:
#   ./scripts/android/sign-apk.sh [--preflight] [--dry-run] [--apk=<path>] [--keystore=<path>] [--alias=<alias>]

set -euo pipefail
set +x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

WORKSPACE_DIR="${WORKSPACE_DIR:-${REPO_ROOT}/build-workspace}"
SRC_DIR="${WORKSPACE_DIR}/src"
OUT_DIR="${OUT_DIR:-${SRC_DIR}/out/Release}"
OUTPUT_APK_DIR="${OUTPUT_APK_DIR:-${REPO_ROOT}/out/apks}"

trim_whitespace() {
  local var="$*"
  var="${var#"${var%%[![:space:]]*}"}"
  var="${var%"${var##*[![:space:]]}"}"
  printf '%s' "$var"
}

KEYSTORE_FILENAME="$(trim_whitespace "${ANDROID_KEYSTORE_FILE:-braving_android.jks}")"
SECURE_FILES_DIR="${SECURE_FILES_DIR:-${SECURE_FILES_DOWNLOAD_PATH:-${REPO_ROOT}/.secure_files}}"
KEYSTORE_PATH="$(trim_whitespace "${ANDROID_KEYSTORE_PATH:-}")"
KEY_ALIAS="$(trim_whitespace "${ANDROID_KEY_ALIAS:-${ANDROID_KEYSTORE_NAME:-braving}}")"

PREFLIGHT=false
DRY_RUN=false
FORCE_SIGN=false
EXPLICIT_APKS=false
declare -a TARGET_APKS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apk=*)
      TARGET_APKS+=("${1#*=}")
      EXPLICIT_APKS=true
      shift
      ;;
    --keystore=*)
      KEYSTORE_PATH="$(trim_whitespace "${1#*=}")"
      shift
      ;;
    --alias=*)
      KEY_ALIAS="$(trim_whitespace "${1#*=}")"
      shift
      ;;
    --preflight)
      PREFLIGHT=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --force)
      FORCE_SIGN=true
      shift
      ;;
    -*)
      echo "ERROR: Unknown option: $1" >&2
      exit 1
      ;;
    *)
      TARGET_APKS+=("$1")
      EXPLICIT_APKS=true
      shift
      ;;
  esac
done

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "========================================================"
  echo " Braving APK Signing (Dry-Run)"
  echo " Default Keystore : ${SECURE_FILES_DIR}/${KEYSTORE_FILENAME}"
  echo " Key Alias        : ${KEY_ALIAS}"
  echo " Password Env Var : KEY_PASSWORD_ANDROID"
  echo "========================================================"
  echo "Dry-run mode requested. Signing configuration valid."
  exit 0
fi

# Ensure bundled Chromium JDK is on PATH if present
if [[ -d "${SRC_DIR}/third_party/jdk/current/bin" ]]; then
  export PATH="${SRC_DIR}/third_party/jdk/current/bin:${PATH}"
fi

# Step 1: Resolve signing password (never echo or trace secrets)
KS_PASS="${KEY_PASSWORD_ANDROID:-${ANDROID_KEYSTORE_PASSWORD:-}}"
KEY_PASS="${ANDROID_KEY_PASSWORD:-${KEY_PASSWORD_ANDROID:-${ANDROID_KEYSTORE_PASSWORD:-}}}"

if [[ -z "${KS_PASS}" ]]; then
  echo "ERROR: KEY_PASSWORD_ANDROID environment variable is not set or empty." >&2
  echo "Configure KEY_PASSWORD_ANDROID in GitLab Settings -> CI/CD -> Variables." >&2
  exit 1
fi

# Step 2: Resolve or download keystore (`braving_android.jks`)
resolve_keystore() {
  if [[ -n "${KEYSTORE_PATH}" ]]; then
    if [[ ! -s "${KEYSTORE_PATH}" ]]; then
      echo "ERROR: Explicitly specified keystore not found or empty: ${KEYSTORE_PATH}" >&2
      exit 1
    fi
    return 0
  fi

  local candidate_paths=(
    "${SECURE_FILES_DIR}/${KEYSTORE_FILENAME}"
    "${CI_PROJECT_DIR:-${REPO_ROOT}}/.secure_files/${KEYSTORE_FILENAME}"
    "${REPO_ROOT}/${KEYSTORE_FILENAME}"
  )

  for candidate in "${candidate_paths[@]}"; do
    if [[ -s "${candidate}" ]]; then
      KEYSTORE_PATH="${candidate}"
      echo "Using local keystore: ${KEYSTORE_PATH}"
      return 0
    fi
  done

  # Also check if a file in .secure_files matches after trimming trailing/leading whitespace
  local search_dirs=(
    "${SECURE_FILES_DIR}"
    "${CI_PROJECT_DIR:-${REPO_ROOT}}/.secure_files"
  )
  for sdir in "${search_dirs[@]}"; do
    if [[ -d "${sdir}" ]]; then
      while IFS= read -r -d $'\0' entry; do
        local base_trimmed
        base_trimmed="$(trim_whitespace "$(basename "${entry}")")"
        if [[ "${base_trimmed,,}" == "${KEYSTORE_FILENAME,,}" && -s "${entry}" ]]; then
          KEYSTORE_PATH="${entry}"
          echo "Using local keystore: ${KEYSTORE_PATH}"
          return 0
        fi
      done < <(find "${sdir}" -maxdepth 1 -type f -print0 2>/dev/null | sort -z)
    fi
  done

  mkdir -p "${SECURE_FILES_DIR}"
  local dest_path="${SECURE_FILES_DIR}/${KEYSTORE_FILENAME}"

  if [[ -n "${ANDROID_KEYSTORE_BASE64:-}" ]]; then
    echo "Decoding keystore from ANDROID_KEYSTORE_BASE64 into ${dest_path}..."
    python3 - "${dest_path}" <<'PYEOF'
import base64
import os
import sys

dest = sys.argv[1]
raw = base64.b64decode(os.environ["ANDROID_KEYSTORE_BASE64"].strip())
if not raw:
    sys.exit(1)
with open(dest, "wb") as f:
    f.write(raw)
os.chmod(dest, 0o600)
PYEOF
    KEYSTORE_PATH="${dest_path}"
    return 0
  fi

  if [[ -n "${CI_API_V4_URL:-}" && -n "${CI_PROJECT_ID:-}" && ( -n "${CI_JOB_TOKEN:-}" || -n "${GITLAB_TOKEN:-}" || -n "${PRIVATE_TOKEN:-}" ) ]]; then
    echo "Downloading '${KEYSTORE_FILENAME}' from GitLab CI/CD Secure Files API..."
    if python3 - "${dest_path}" "${KEYSTORE_FILENAME}" <<'PYEOF'
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

dest_path = sys.argv[1]
target_name = sys.argv[2]

api_url = os.environ.get("CI_API_V4_URL", "").strip().rstrip("/")
project_id = os.environ.get("CI_PROJECT_ID", "").strip()
job_token = os.environ.get("CI_JOB_TOKEN", "").strip()
priv_token = os.environ.get("GITLAB_TOKEN", "").strip() or os.environ.get("PRIVATE_TOKEN", "").strip()

headers = {}
if job_token:
    headers["JOB-TOKEN"] = job_token
elif priv_token:
    headers["PRIVATE-TOKEN"] = priv_token


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        new_req = super().redirect_request(req, fp, code, msg, hdrs, newurl)
        if new_req is not None:
            orig_host = urllib.parse.urlparse(req.full_url).netloc
            new_host = urllib.parse.urlparse(newurl).netloc
            if orig_host and new_host and orig_host.lower() != new_host.lower():
                for k in list(new_req.headers.keys()):
                    if k.lower() in ("job-token", "private-token", "authorization"):
                        new_req.headers.pop(k, None)
        return new_req


opener = urllib.request.build_opener(SafeRedirectHandler)

list_url = f"{api_url}/projects/{project_id}/secure_files?per_page=100"
req = urllib.request.Request(list_url, headers=headers)
try:
    with opener.open(req, timeout=30) as resp:
        files = json.loads(resp.read().decode("utf-8"))
except Exception as exc:
    print(f"ERROR: Failed to query GitLab Secure Files API ({list_url}): {exc}", file=sys.stderr)
    sys.exit(1)

if not isinstance(files, list) or not files:
    print("ERROR: No Secure Files found in GitLab project.", file=sys.stderr)
    sys.exit(1)

target_file = None
for item in files:
    if isinstance(item, dict) and item.get("name") == target_name:
        target_file = item
        break

if target_file is None:
    target_norm = target_name.strip().lower()
    for item in files:
        if isinstance(item, dict) and str(item.get("name", "")).strip().lower() == target_norm:
            target_file = item
            break

if target_file is None or "id" not in target_file:
    available = [str(i.get("name", "")) for i in files if isinstance(i, dict)]
    print(
        f"ERROR: Secure File '{target_name}' not found in GitLab Secure Files. Available: {available}",
        file=sys.stderr,
    )
    sys.exit(1)

file_id = target_file["id"]
dl_url = f"{api_url}/projects/{project_id}/secure_files/{file_id}/download"
dl_req = urllib.request.Request(dl_url, headers=headers)
try:
    with opener.open(dl_req, timeout=60) as resp:
        raw_bytes = resp.read()
except Exception as exc:
    print(f"ERROR: Failed to download GitLab Secure File id={file_id}: {exc}", file=sys.stderr)
    sys.exit(1)

if not raw_bytes:
    print(f"ERROR: Downloaded GitLab Secure File '{target_name}' is empty.", file=sys.stderr)
    sys.exit(1)

expected_sha256 = str(target_file.get("checksum") or "").strip().lower()
checksum_algo = str(target_file.get("checksum_algorithm") or "sha256").strip().lower()
if expected_sha256 and checksum_algo == "sha256" and len(expected_sha256) == 64:
    actual_sha256 = hashlib.sha256(raw_bytes).hexdigest().lower()
    if actual_sha256 != expected_sha256:
        print(
            f"ERROR: SHA256 mismatch for Secure File '{target_name}': expected {expected_sha256}, got {actual_sha256}",
            file=sys.stderr,
        )
        sys.exit(1)

os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
with open(dest_path, "wb") as f:
    f.write(raw_bytes)
try:
    os.chmod(dest_path, 0o600)
except OSError:
    pass

print(f"Downloaded Secure File '{target_file.get('name')}' (id={file_id}, {len(raw_bytes)} bytes) to {dest_path}")
PYEOF
    then
      KEYSTORE_PATH="${dest_path}"
      return 0
    fi
  fi

  echo "ERROR: Keystore '${KEYSTORE_FILENAME}' not found in ${SECURE_FILES_DIR} and could not be downloaded from GitLab Secure Files." >&2
  echo "Upload '${KEYSTORE_FILENAME}' in GitLab Settings -> CI/CD -> Secure Files." >&2
  exit 1
}

TMP_ALIGNED=""
TMP_SIGNED=""
TMP_P12_PROBE=""
cleanup_tmp() {
  rm -f "${TMP_ALIGNED:-}" "${TMP_SIGNED:-}" "${TMP_SIGNED:+${TMP_SIGNED}.idsig}" "${TMP_P12_PROBE:-}"
}
trap cleanup_tmp EXIT

resolve_keystore

# Step 3: Validate keystore, alias, and private key recovery using keytool if available
KEYSTORE_CERT_SHA256=""
if command -v keytool >/dev/null 2>&1; then
  KEYTOOL_OUT=""
   if ! KEYTOOL_OUT=$(BRAVING_KS_PASS="${KS_PASS}" keytool -list \
     -storetype JKS \
       -keystore "${KEYSTORE_PATH}" \
         -alias "${KEY_ALIAS}" \
           -storepass:env BRAVING_KS_PASS 2>/dev/null); then
    echo "ERROR: Failed to unlock keystore '${KEYSTORE_PATH}' or alias '${KEY_ALIAS}' does not exist." >&2
    echo "Verify KEY_PASSWORD_ANDROID and that '${KEYSTORE_FILENAME}' contains alias '${KEY_ALIAS}'." >&2
    exit 1
  fi

  if echo "${KEYTOOL_OUT}" | grep -qi "trustedCertEntry"; then
    echo "ERROR: Alias '${KEY_ALIAS}' in '${KEYSTORE_PATH}' is a certificate-only entry (trustedCertEntry), not a PrivateKeyEntry." >&2
    exit 1
  fi

  KEYSTORE_CERT_SHA256=$(echo "${KEYTOOL_OUT}" | grep -i "SHA-256" | sed -E 's/.*SHA-256\):[[:space:]]*//' | tr -d ':[:space:]' | tr '[:upper:]' '[:lower:]' | head -n 1 || true)

  if echo "${KEYTOOL_OUT}" | grep -qi "PrivateKeyEntry"; then
    TMP_P12_PROBE=$(mktemp "${TMPDIR:-/tmp}/braving-ks-probe-XXXXXX.p12")
    rm -f "${TMP_P12_PROBE}"
    if ! BRAVING_KS_PASS="${KS_PASS}" BRAVING_KEY_PASS="${KEY_PASS}" keytool -importkeystore \
      -srckeystore "${KEYSTORE_PATH}" \
        -srcstoretype JKS \
          -srcalias "${KEY_ALIAS}" \
            -srcstorepass:env BRAVING_KS_PASS \
              -srckeypass:env BRAVING_KEY_PASS \
      -destkeystore "${TMP_P12_PROBE}" \
      -deststoretype PKCS12 \
      -deststorepass braving_probe_tmp \
      -destkeypass braving_probe_tmp \
      -noprompt >/dev/null 2>&1; then
      rm -f "${TMP_P12_PROBE}"
      TMP_P12_PROBE=""
      echo "ERROR: Failed to recover private key for alias '${KEY_ALIAS}' in '${KEYSTORE_PATH}'." >&2
      echo "Verify that KEY_PASSWORD_ANDROID (or ANDROID_KEY_PASSWORD) matches the private key password." >&2
      exit 1
    fi
    rm -f "${TMP_P12_PROBE}"
    TMP_P12_PROBE=""
  fi

  echo "Verified keystore '${KEYSTORE_PATH}' contains valid key entry for alias '${KEY_ALIAS}'."
fi

if [[ "${PREFLIGHT}" == "true" ]]; then
  echo " [OK] Signing preflight check passed."
  exit 0
fi

# Step 4: Locate zipalign and apksigner
find_build_tool() {
  local tool_name="$1"
  local explicit_path="${2:-}"

  if [[ -n "${explicit_path}" && -x "${explicit_path}" ]]; then
    echo "${explicit_path}"
    return 0
  fi

  local found=""
  if [[ -d "${SRC_DIR}/third_party/android_sdk/public/build-tools" ]]; then
    found=$(find "${SRC_DIR}/third_party/android_sdk/public/build-tools" -name "${tool_name}" \( -type f -o -type l \) 2>/dev/null | sort -V | tail -n 1 || true)
    if [[ -n "${found}" && -x "${found}" ]]; then
      echo "${found}"
      return 0
    fi
  fi

  if command -v "${tool_name}" >/dev/null 2>&1; then
    command -v "${tool_name}"
    return 0
  fi

  local sdk_root="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-${HOME:-/root}/Android/Sdk}}"
  if [[ -d "${sdk_root}/build-tools" ]]; then
    found=$(find "${sdk_root}/build-tools" -name "${tool_name}" \( -type f -o -type l \) 2>/dev/null | sort -V | tail -n 1 || true)
    if [[ -n "${found}" && -x "${found}" ]]; then
      echo "${found}"
      return 0
    fi
  fi

  return 1
}

ZIPALIGN_BIN=$(find_build_tool "zipalign" "${ZIPALIGN_PATH:-}" || true)
APKSIGNER_BIN=$(find_build_tool "apksigner" "${APKSIGNER_PATH:-}" || true)

if [[ -z "${ZIPALIGN_BIN}" || ! -x "${ZIPALIGN_BIN}" ]]; then
  echo "ERROR: 'zipalign' binary not found in Chromium Android SDK or PATH." >&2
  exit 1
fi

if [[ -z "${APKSIGNER_BIN}" || ! -x "${APKSIGNER_BIN}" ]]; then
  echo "ERROR: 'apksigner' binary not found in Chromium Android SDK or PATH." >&2
  exit 1
fi

echo "Using zipalign : ${ZIPALIGN_BIN}"
echo "Using apksigner: ${APKSIGNER_BIN}"

# Step 5: Discover APK files to sign if not explicitly provided
if [[ ${#TARGET_APKS[@]} -eq 0 ]]; then
  if [[ -d "${OUTPUT_APK_DIR}" ]]; then
    while IFS= read -r -d $'\0' apk; do
      TARGET_APKS+=("${apk}")
    done < <(find "${OUTPUT_APK_DIR}" -maxdepth 1 -name "*.apk" -type f -print0 | sort -z)
  fi

  if [[ ${#TARGET_APKS[@]} -eq 0 && -d "${OUT_DIR}/apks" ]]; then
    mkdir -p "${OUTPUT_APK_DIR}"
    while IFS= read -r -d $'\0' apk; do
      dest="${OUTPUT_APK_DIR}/$(basename "${apk}")"
      cp -f "${apk}" "${dest}"
      TARGET_APKS+=("${dest}")
    done < <(find "${OUT_DIR}/apks" -maxdepth 1 \( -name "Braving*.apk" -o -name "Brave*.apk" -o -name "ChromePublic.apk" \) -type f -print0 | sort -z)
  fi
fi

if [[ ${#TARGET_APKS[@]} -eq 0 ]]; then
  echo "ERROR: No APK files found to sign in ${OUTPUT_APK_DIR} or ${OUT_DIR}/apks." >&2
  exit 1
fi

# Step 6: Align, Sign, and Verify each APK
sync_apk_copies() {
  local abs_apk="$1"
  local apk_name="$2"
  local sync_to_output="${3:-true}"

  chmod 0644 "${abs_apk}" 2>/dev/null || true

  if [[ "${sync_to_output}" == "true" && -d "${OUTPUT_APK_DIR}" ]]; then
    local out_copy="${OUTPUT_APK_DIR}/${apk_name}"
    if [[ "$(cd "${OUTPUT_APK_DIR}" && pwd)/${apk_name}" != "${abs_apk}" ]]; then
      cp -f "${abs_apk}" "${out_copy}"
      chmod 0644 "${out_copy}" 2>/dev/null || true
    fi
  fi

  if [[ "${sync_to_output}" == "true" && -d "${OUT_DIR}/apks" ]]; then
    local release_copy="${OUT_DIR}/apks/${apk_name}"
    if [[ "$(cd "${OUT_DIR}/apks" && pwd)/${apk_name}" != "${abs_apk}" ]]; then
      cp -f "${abs_apk}" "${release_copy}"
      chmod 0644 "${release_copy}" 2>/dev/null || true
    fi
  fi
}

sign_and_verify_apk() {
  local apk_path="$1"
  local sync_to_output="${2:-true}"
  if [[ ! -f "${apk_path}" ]]; then
    echo "ERROR: APK file not found: ${apk_path}" >&2
    exit 1
  fi

  local apk_dir
  apk_dir="$(cd "$(dirname "${apk_path}")" && pwd)"
  local apk_name
  apk_name="$(basename "${apk_path}")"
  local abs_apk="${apk_dir}/${apk_name}"

  # Idempotency check: if already aligned and signed with the target keystore certificate, skip re-signing
  if [[ "${FORCE_SIGN}" == "false" && -n "${KEYSTORE_CERT_SHA256}" ]]; then
    if "${ZIPALIGN_BIN}" -c -p 4 "${abs_apk}" >/dev/null 2>&1; then
      local existing_certs=""
      if existing_certs=$("${APKSIGNER_BIN}" verify --print-certs "${abs_apk}" 2>/dev/null); then
        if echo "${existing_certs}" | tr '[:upper:]' '[:lower:]' | grep -q "${KEYSTORE_CERT_SHA256}"; then
          sync_apk_copies "${abs_apk}" "${apk_name}" "${sync_to_output}"
          echo " [OK] APK already aligned, signed, and verified with alias '${KEY_ALIAS}': ${abs_apk}"
          return 0
        fi
      fi
    fi
  fi

  echo "--------------------------------------------------------"
  echo "Signing APK : ${abs_apk}"
  echo "Keystore    : ${KEYSTORE_PATH}"
  echo "Key Alias   : ${KEY_ALIAS}"
  echo "--------------------------------------------------------"

  TMP_ALIGNED=$(mktemp "${TMPDIR:-/tmp}/braving-aligned-XXXXXX.apk")
  TMP_SIGNED=$(mktemp "${TMPDIR:-/tmp}/braving-signed-XXXXXX.apk")

  echo "1. Running zipalign (4-byte & page-aligned shared objects)..."
  "${ZIPALIGN_BIN}" -p -f 4 "${abs_apk}" "${TMP_ALIGNED}"

  echo "2. Signing with apksigner (alias: ${KEY_ALIAS})..."
  BRAVING_KS_PASS="${KS_PASS}" BRAVING_KEY_PASS="${KEY_PASS}" \
    "${APKSIGNER_BIN}" sign \
      --ks "${KEYSTORE_PATH}" \
        --ks-type JKS \
          --ks-key-alias "${KEY_ALIAS}" \
    --ks-pass env:BRAVING_KS_PASS \
    --key-pass env:BRAVING_KEY_PASS \
    --in "${TMP_ALIGNED}" \
    --out "${TMP_SIGNED}"

  echo "3. Verifying APK signature..."
  local verify_out=""
  verify_out=$("${APKSIGNER_BIN}" verify --verbose --print-certs "${TMP_SIGNED}")
  echo "${verify_out}"
  if [[ -n "${KEYSTORE_CERT_SHA256}" ]]; then
    if ! echo "${verify_out}" | tr '[:upper:]' '[:lower:]' | grep -q "${KEYSTORE_CERT_SHA256}"; then
      echo "ERROR: Signed APK certificate SHA-256 does not match keystore alias '${KEY_ALIAS}' (${KEYSTORE_CERT_SHA256})." >&2
      exit 1
    fi
  fi

  mv -f "${TMP_SIGNED}" "${abs_apk}"
  chmod 0644 "${abs_apk}" 2>/dev/null || true
  rm -f "${TMP_ALIGNED}" "${TMP_SIGNED}.idsig" "${abs_apk}.idsig"
  TMP_ALIGNED=""
  TMP_SIGNED=""

  # Final verification in place
  "${APKSIGNER_BIN}" verify "${abs_apk}"
  echo " [OK] Signed and verified: ${abs_apk}"

  # Synchronize signed APK across both out/apks/ and build-workspace/src/out/Release/apks/
  sync_apk_copies "${abs_apk}" "${apk_name}" "${sync_to_output}"
}

for apk in "${TARGET_APKS[@]}"; do
  sign_and_verify_apk "${apk}" "true"
done

# When auto-discovering APKs (no explicit --apk passed), also sign any remaining browser APKs in ${OUT_DIR}/apks/ in-place
# without polluting ${OUTPUT_APK_DIR} with intermediate filenames like ChromePublic.apk
if [[ "${EXPLICIT_APKS}" == "false" && -d "${OUT_DIR}/apks" ]]; then
  while IFS= read -r -d $'\0' extra_apk; do
    extra_name="$(basename "${extra_apk}")"
    already_signed=false
    for signed_apk in "${TARGET_APKS[@]}"; do
      if [[ "$(basename "${signed_apk}")" == "${extra_name}" ]]; then
        already_signed=true
        break
      fi
    done
    if [[ "${already_signed}" == "false" ]]; then
      sign_and_verify_apk "${extra_apk}" "false"
    fi
  done < <(find "${OUT_DIR}/apks" -maxdepth 1 \( -name "Braving*.apk" -o -name "Brave*.apk" -o -name "ChromePublic.apk" \) -type f -print0 | sort -z)
fi

echo "========================================================"
echo " APK SIGNING & VERIFICATION SUCCESSFUL"
echo "========================================================"
