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

# Step 1: Resolve signing password & generate normalized candidates (never echo or trace secrets)
RAW_KS_PASS="${KEY_PASSWORD_ANDROID:-${ANDROID_KEYSTORE_PASSWORD:-}}"
RAW_KEY_PASS="${ANDROID_KEY_PASSWORD:-${KEY_PASSWORD_ANDROID:-${ANDROID_KEYSTORE_PASSWORD:-}}}"

if [[ -z "${RAW_KS_PASS}" ]]; then
  echo "ERROR: KEY_PASSWORD_ANDROID environment variable is not set or empty." >&2
  echo "Configure KEY_PASSWORD_ANDROID in GitLab Settings -> CI/CD -> Variables." >&2
  exit 1
fi

KS_PASS_IS_FILE="false (env variable)"
KS_PASS_EFFECTIVE_RAW="${RAW_KS_PASS}"
if [[ -f "${RAW_KS_PASS}" ]]; then
  KS_PASS_IS_FILE="true (File-type variable)"
  KS_PASS_EFFECTIVE_RAW="$(cat "${RAW_KS_PASS}")"
fi
KS_PASS_TRIMMED="$(trim_whitespace "${KS_PASS_EFFECTIVE_RAW}")"

build_password_candidates() {
  local raw_input="$1"
  local -n out_arr="$2"
  out_arr=()

  local _add_cand
  _add_cand() {
    local c="$1"
    [[ -z "${c}" ]] && return 0
    local existing
    for existing in "${out_arr[@]+"${out_arr[@]}"}"; do
      if [[ "${existing}" == "${c}" ]]; then
        return 0
      fi
    done
    out_arr+=("${c}")
  }

  if [[ -f "${raw_input}" ]]; then
    local file_raw=""
    file_raw="$(cat "${raw_input}")"
    local file_no_crlf="${file_raw//[$'\r\n']/}"
    local file_trimmed
    file_trimmed="$(trim_whitespace "${file_raw}")"
    _add_cand "${file_no_crlf}"
    _add_cand "${file_trimmed}"
    _add_cand "${file_raw}"
  fi

  local no_crlf="${raw_input//[$'\r\n']/}"
  local trimmed
  trimmed="$(trim_whitespace "${raw_input}")"
  _add_cand "${raw_input}"
  _add_cand "${no_crlf}"
  _add_cand "${trimmed}"
}

declare -a KS_PASS_CANDIDATES=()
declare -a KEY_PASS_CANDIDATES=()
build_password_candidates "${RAW_KS_PASS}" KS_PASS_CANDIDATES
build_password_candidates "${RAW_KEY_PASS}" KEY_PASS_CANDIDATES

if [[ ${#KS_PASS_CANDIDATES[@]} -eq 0 ]]; then
  echo "ERROR: KEY_PASSWORD_ANDROID resolved to an empty password." >&2
  exit 1
fi

KS_PASS="${KS_PASS_CANDIDATES[0]}"
KEY_PASS="${KEY_PASS_CANDIDATES[0]:-${KS_PASS}}"

sanitize_output() {
  local text="$1"
  local p
  for p in "${KS_PASS_CANDIDATES[@]+"${KS_PASS_CANDIDATES[@]}"}" "${KEY_PASS_CANDIDATES[@]+"${KEY_PASS_CANDIDATES[@]}"}" "${RAW_KS_PASS}" "${RAW_KEY_PASS}"; do
    if [[ -n "${p}" ]]; then
      text="${text//"${p}"/[REDACTED]}"
    fi
  done
  printf '%s\n' "${text}"
}


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

# Inspect keystore binary header (magic bytes -> PKCS12 vs JKS, size, SHA-256, plaintext alias names)
KEYSTORE_TYPE="UNKNOWN"
KEYSTORE_SIZE="0"
KEYSTORE_SHA256=""
KEYSTORE_PLAINTEXT_ALIASES=""
{
  IFS= read -r KEYSTORE_TYPE || true
  IFS= read -r KEYSTORE_SIZE || true
  IFS= read -r KEYSTORE_SHA256 || true
  IFS= read -r KEYSTORE_PLAINTEXT_ALIASES || true
} < <(python3 - "${KEYSTORE_PATH}" <<'PYEOF'
import hashlib
import struct
import sys

ks_path = sys.argv[1]
try:
    with open(ks_path, "rb") as f:
        data = f.read()
except OSError:
    data = b""

size = len(data)
sha256 = hashlib.sha256(data).hexdigest() if data else ""


def parse_der_length(buf, idx):
    if idx >= len(buf):
        return 0, idx
    b = buf[idx]
    idx += 1
    if (b & 0x80) == 0:
        return b, idx
    num_bytes = b & 0x7F
    if num_bytes == 0 or idx + num_bytes > len(buf):
        return 0, idx
    length = int.from_bytes(buf[idx : idx + num_bytes], "big")
    return length, idx + num_bytes


def extract_pkcs12_aliases(buf):
    # OID 1.2.840.113549.1.9.20 (friendlyName) -> 06 09 2a 86 48 86 f7 0d 01 09 14
    oid_friendly = bytes.fromhex("06092a864886f70d010914")
    pos = 0
    aliases = []
    while True:
        idx = buf.find(oid_friendly, pos)
        if idx == -1:
            break
        cur = idx + len(oid_friendly)
        if cur < len(buf) and buf[cur] == 0x31:  # SET
            _, cur = parse_der_length(buf, cur + 1)
            if cur < len(buf):
                str_tag = buf[cur]
                str_len, val_start = parse_der_length(buf, cur + 1)
                raw_val = buf[val_start : val_start + str_len]
                if str_tag == 0x1E:  # BMPString (UTF-16BE)
                    alias = raw_val.decode("utf-16-be", errors="replace")
                else:
                    alias = raw_val.decode("utf-8", errors="replace")
                alias = alias.strip("\x00")
                if alias and alias not in aliases:
                    aliases.append(alias)
        pos = idx + 1
    return aliases


def extract_jks_aliases(buf):
    aliases = []
    if len(buf) < 12:
        return aliases
    try:
        magic, version, count = struct.unpack(">III", buf[:12])
        if magic != 0xFEEDFEED:
            return aliases
        pos = 12
        for _ in range(min(count, 1024)):
            if pos + 6 > len(buf):
                break
            tag = struct.unpack(">I", buf[pos : pos + 4])[0]
            pos += 4
            alias_len = struct.unpack(">H", buf[pos : pos + 2])[0]
            pos += 2
            if pos + alias_len > len(buf):
                break
            alias = buf[pos : pos + alias_len].decode("utf-8", errors="replace")
            pos += alias_len
            if alias and alias not in aliases:
                aliases.append(alias)
            if pos + 8 > len(buf):
                break
            pos += 8
            if tag == 1:  # PrivateKeyEntry
                if pos + 4 > len(buf):
                    break
                key_len = struct.unpack(">I", buf[pos : pos + 4])[0]
                pos += 4 + key_len
                if pos + 4 > len(buf):
                    break
                cert_count = struct.unpack(">I", buf[pos : pos + 4])[0]
                pos += 4
                for _ in range(min(cert_count, 256)):
                    if version == 2:
                        if pos + 2 > len(buf):
                            break
                        ct_len = struct.unpack(">H", buf[pos : pos + 2])[0]
                        pos += 2 + ct_len
                    if pos + 4 > len(buf):
                        break
                    c_len = struct.unpack(">I", buf[pos : pos + 4])[0]
                    pos += 4 + c_len
            elif tag == 2:  # TrustedCertEntry
                if version == 2:
                    if pos + 2 > len(buf):
                        break
                    ct_len = struct.unpack(">H", buf[pos : pos + 2])[0]
                    pos += 2 + ct_len
                if pos + 4 > len(buf):
                    break
                c_len = struct.unpack(">I", buf[pos : pos + 4])[0]
                pos += 4 + c_len
            else:
                break
    except Exception:
        pass
    return aliases


if len(data) >= 4 and data[:4] == b"\xfe\xed\xfe\xed":
    ks_type = "JKS"
    aliases = extract_jks_aliases(data)
elif len(data) >= 2 and data[0] == 0x30:
    ks_type = "PKCS12"
    aliases = extract_pkcs12_aliases(data)
else:
    ks_type = "UNKNOWN"
    aliases = []

print(ks_type)
print(size)
print(sha256)
print(",".join(aliases))
PYEOF
)

declare -a KEYTOOL_STORE_ARGS=()
declare -a KEYTOOL_SRCSTORE_ARGS=()
declare -a APKSIGNER_KS_TYPE_ARGS=()
if [[ "${KEYSTORE_TYPE}" == "JKS" || "${KEYSTORE_TYPE}" == "PKCS12" ]]; then
  echo "Detected keystore format: ${KEYSTORE_TYPE} (${KEYSTORE_SIZE} bytes, sha256=${KEYSTORE_SHA256})"
  KEYTOOL_STORE_ARGS=(-storetype "${KEYSTORE_TYPE}")
  KEYTOOL_SRCSTORE_ARGS=(-srcstoretype "${KEYSTORE_TYPE}")
  APKSIGNER_KS_TYPE_ARGS=(--ks-type "${KEYSTORE_TYPE}")
fi

# Step 3: Validate keystore, alias, and private key recovery using keytool if available
KEYSTORE_CERT_SHA256=""
if command -v keytool >/dev/null 2>&1; then
  KEYTOOL_LIST_OUT=""
  KEYSTORE_UNLOCKED=false
  FIRST_KEYTOOL_ERR=""

  for cand in "${KS_PASS_CANDIDATES[@]}"; do
    if KEYTOOL_LIST_OUT=$(BRAVING_KS_PASS="${cand}" keytool -list -v \
      "${KEYTOOL_STORE_ARGS[@]+"${KEYTOOL_STORE_ARGS[@]}"}" \
      -keystore "${KEYSTORE_PATH}" \
      -storepass:env BRAVING_KS_PASS 2>&1); then
      KS_PASS="${cand}"
      if [[ -z "${ANDROID_KEY_PASSWORD:-}" ]]; then
        KEY_PASS="${cand}"
      fi
      KEYSTORE_UNLOCKED=true
      break
    else
      if [[ -z "${FIRST_KEYTOOL_ERR}" ]]; then
        FIRST_KEYTOOL_ERR="${KEYTOOL_LIST_OUT}"
      fi
    fi
  done

  if [[ "${KEYSTORE_UNLOCKED}" != "true" ]]; then
    SANITIZED_ERR="$(sanitize_output "${FIRST_KEYTOOL_ERR}")"
    echo "ERROR: Failed to unlock keystore '${KEYSTORE_PATH}' with KEY_PASSWORD_ANDROID (tried ${#KS_PASS_CANDIDATES[@]} password candidate(s))." >&2
    echo "Keystore Diagnostics (non-secret):" >&2
    echo "  - Container Format  : ${KEYSTORE_TYPE}" >&2
    echo "  - File Size         : ${KEYSTORE_SIZE} bytes" >&2
    echo "  - SHA-256           : ${KEYSTORE_SHA256}" >&2
    echo "  - Plaintext Aliases : ${KEYSTORE_PLAINTEXT_ALIASES:-<none detected>}" >&2
    echo "  - Target Alias      : ${KEY_ALIAS}" >&2
    echo "  - Password File Var : ${KS_PASS_IS_FILE}" >&2
    echo "  - Password Length   : raw=${#RAW_KS_PASS} chars, effective=${#KS_PASS_EFFECTIVE_RAW} chars, trimmed=${#KS_PASS_TRIMMED} chars" >&2
    if [[ -n "${SANITIZED_ERR}" ]]; then
      echo "Keytool Error Output:" >&2
      echo "${SANITIZED_ERR}" >&2
    fi
    if [[ -n "${KEYSTORE_PLAINTEXT_ALIASES}" ]]; then
      echo "NOTE: Plaintext alias(es) '${KEYSTORE_PLAINTEXT_ALIASES}' were detected inside '${KEYSTORE_FILENAME}' (${KEYSTORE_TYPE})." >&2
      echo "      The keystore file is intact; verify that KEY_PASSWORD_ANDROID in GitLab CI/CD Variables matches the keystore password." >&2
    else
      echo "Verify KEY_PASSWORD_ANDROID and '${KEYSTORE_FILENAME}' in GitLab Settings -> CI/CD." >&2
    fi
    exit 1
  fi

  KEYTOOL_OUT=""
  if ! KEYTOOL_OUT=$(BRAVING_KS_PASS="${KS_PASS}" keytool -list -v \
    "${KEYTOOL_STORE_ARGS[@]+"${KEYTOOL_STORE_ARGS[@]}"}" \
    -keystore "${KEYSTORE_PATH}" \
    -alias "${KEY_ALIAS}" \
    -storepass:env BRAVING_KS_PASS 2>&1); then
    DETECTED_ALIAS=$(KEYTOOL_LIST_TEXT="${KEYTOOL_LIST_OUT}" PLAINTEXT_ALIASES="${KEYSTORE_PLAINTEXT_ALIASES}" python3 - <<'PYEOF'
import os
import re

text = os.environ.get("KEYTOOL_LIST_TEXT", "")
current_alias = None
private_aliases = []
all_aliases = []

for raw_line in text.splitlines():
    line = raw_line.strip()
    m_alias = re.match(r"^Alias name:\s*(.+)$", line, re.IGNORECASE)
    if m_alias:
        current_alias = m_alias.group(1).strip()
        if current_alias and current_alias not in all_aliases:
            all_aliases.append(current_alias)
        continue
    m_entry = re.match(r"^Entry type:\s*(\S+)", line, re.IGNORECASE)
    if m_entry and current_alias:
        etype = m_entry.group(1).strip().lower()
        if "privatekeyentry" in etype or "keyentry" in etype:
            if current_alias not in private_aliases:
                private_aliases.append(current_alias)
        continue
    if "privatekeyentry" in line.lower() and "," in line:
        cand = line.split(",", 1)[0].strip()
        if cand and cand not in private_aliases:
            private_aliases.append(cand)
            if cand not in all_aliases:
                all_aliases.append(cand)

if private_aliases:
    print(private_aliases[0])
elif all_aliases:
    print(all_aliases[0])
else:
    pt = [a.strip() for a in os.environ.get("PLAINTEXT_ALIASES", "").split(",") if a.strip()]
    if pt:
        print(pt[0])
PYEOF
)
    DETECTED_ALIAS="$(trim_whitespace "${DETECTED_ALIAS}")"
    if [[ -n "${DETECTED_ALIAS}" && "${DETECTED_ALIAS}" != "${KEY_ALIAS}" ]]; then
      echo "Auto-detected keystore alias: ${DETECTED_ALIAS} (configured alias '${KEY_ALIAS}' was not found)"
      KEY_ALIAS="${DETECTED_ALIAS}"
      if ! KEYTOOL_OUT=$(BRAVING_KS_PASS="${KS_PASS}" keytool -list -v \
        "${KEYTOOL_STORE_ARGS[@]+"${KEYTOOL_STORE_ARGS[@]}"}" \
        -keystore "${KEYSTORE_PATH}" \
        -alias "${KEY_ALIAS}" \
        -storepass:env BRAVING_KS_PASS 2>&1); then
        SANITIZED_ERR="$(sanitize_output "${KEYTOOL_OUT}")"
        echo "ERROR: Failed to inspect auto-detected alias '${KEY_ALIAS}' in '${KEYSTORE_PATH}'." >&2
        [[ -n "${SANITIZED_ERR}" ]] && echo "${SANITIZED_ERR}" >&2
        exit 1
      fi
    else
      SANITIZED_ERR="$(sanitize_output "${KEYTOOL_OUT}")"
      echo "ERROR: Alias '${KEY_ALIAS}' does not exist in keystore '${KEYSTORE_PATH}' and no alternative alias could be auto-detected." >&2
      [[ -n "${SANITIZED_ERR}" ]] && echo "${SANITIZED_ERR}" >&2
      exit 1
    fi
  fi

  if echo "${KEYTOOL_OUT}" | grep -qi "trustedCertEntry"; then
    echo "ERROR: Alias '${KEY_ALIAS}' in '${KEYSTORE_PATH}' is a certificate-only entry (trustedCertEntry), not a PrivateKeyEntry." >&2
    exit 1
  fi

  KEYSTORE_CERT_SHA256=$(echo "${KEYTOOL_OUT}" | grep -iE "SHA-?256" | sed -E 's/.*SHA-?256\)?:[[:space:]]*//' | tr -d ':[:space:]' | tr '[:upper:]' '[:lower:]' | head -n 1 || true)

  if echo "${KEYTOOL_OUT}" | grep -qi "PrivateKeyEntry"; then
    declare -a PROBE_KEY_CANDIDATES=()
    if [[ -z "${ANDROID_KEY_PASSWORD:-}" ]]; then
      PROBE_KEY_CANDIDATES+=("${KS_PASS}")
    fi
    for kcand in "${KEY_PASS_CANDIDATES[@]}"; do
      already_in=false
      for existing in "${PROBE_KEY_CANDIDATES[@]+"${PROBE_KEY_CANDIDATES[@]}"}"; do
        if [[ "${existing}" == "${kcand}" ]]; then
          already_in=true
          break
        fi
      done
      if [[ "${already_in}" == "false" ]]; then
        PROBE_KEY_CANDIDATES+=("${kcand}")
      fi
    done

    KEY_RECOVERED=false
    FIRST_PROBE_ERR=""
    for kcand in "${PROBE_KEY_CANDIDATES[@]}"; do
      TMP_P12_PROBE=$(mktemp "${TMPDIR:-/tmp}/braving-ks-probe-XXXXXX.p12")
      rm -f "${TMP_P12_PROBE}"
      if PROBE_OUT=$(BRAVING_KS_PASS="${KS_PASS}" BRAVING_KEY_PASS="${kcand}" keytool -importkeystore \
        -srckeystore "${KEYSTORE_PATH}" \
        "${KEYTOOL_SRCSTORE_ARGS[@]+"${KEYTOOL_SRCSTORE_ARGS[@]}"}" \
        -srcalias "${KEY_ALIAS}" \
        -srcstorepass:env BRAVING_KS_PASS \
        -srckeypass:env BRAVING_KEY_PASS \
        -destkeystore "${TMP_P12_PROBE}" \
        -deststoretype PKCS12 \
        -deststorepass braving_probe_tmp \
        -destkeypass braving_probe_tmp \
        -noprompt 2>&1); then
        rm -f "${TMP_P12_PROBE}"
        TMP_P12_PROBE=""
        KEY_PASS="${kcand}"
        KEY_RECOVERED=true
        break
      else
        if [[ -z "${FIRST_PROBE_ERR}" ]]; then
          FIRST_PROBE_ERR="${PROBE_OUT}"
        fi
      fi
      rm -f "${TMP_P12_PROBE}"
      TMP_P12_PROBE=""
    done

    if [[ "${KEY_RECOVERED}" != "true" ]]; then
      SANITIZED_PROBE_ERR="$(sanitize_output "${FIRST_PROBE_ERR}")"
      echo "ERROR: Failed to recover private key for alias '${KEY_ALIAS}' in '${KEYSTORE_PATH}'." >&2
      echo "Verify that KEY_PASSWORD_ANDROID (or ANDROID_KEY_PASSWORD) matches the private key password." >&2
      [[ -n "${SANITIZED_PROBE_ERR}" ]] && echo "${SANITIZED_PROBE_ERR}" >&2
      exit 1
    fi
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

  echo "2. Signing with apksigner (alias: ${KEY_ALIAS}, type: ${KEYSTORE_TYPE})..."
  BRAVING_KS_PASS="${KS_PASS}" BRAVING_KEY_PASS="${KEY_PASS}" \
    "${APKSIGNER_BIN}" sign \
    --ks "${KEYSTORE_PATH}" \
    "${APKSIGNER_KS_TYPE_ARGS[@]+"${APKSIGNER_KS_TYPE_ARGS[@]}"}" \
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
