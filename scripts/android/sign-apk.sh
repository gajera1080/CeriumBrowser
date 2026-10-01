#!/usr/bin/env bash
# Braving — Android APK Release Signing & Verification Script
# Resolves keystore (local or GitLab Secure Files API), aligns APK with zipalign,
# signs with apksigner, and verifies with apksigner verify.
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

KEYSTORE_FILENAME="${ANDROID_KEYSTORE_FILE:-braving_android.jks}"
SECURE_FILES_DIR="${SECURE_FILES_DIR:-${REPO_ROOT}/.secure_files}"
KEYSTORE_PATH="${ANDROID_KEYSTORE_PATH:-}"
KEY_ALIAS="${ANDROID_KEY_ALIAS:-braving}"

PREFLIGHT=false
DRY_RUN=false
declare -a TARGET_APKS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apk=*)
      TARGET_APKS+=("${1#*=}")
      shift
      ;;
    --keystore=*)
      KEYSTORE_PATH="${1#*=}"
      shift
      ;;
    --alias=*)
      KEY_ALIAS="${1#*=}"
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
    -*)
      echo "ERROR: Unknown option: $1" >&2
      exit 1
      ;;
    *)
      TARGET_APKS+=("$1")
      shift
      ;;
  esac
done

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "========================================================"
  echo " Braving APK Signing (Dry-Run)"
  echo " Keystore : ${KEYSTORE_PATH:-${SECURE_FILES_DIR}/${KEYSTORE_FILENAME}}"
  echo " Alias    : ${KEY_ALIAS}"
  echo "========================================================"
  exit 0
fi

# Ensure bundled Chromium JDK is on PATH if present
if [[ -d "${SRC_DIR}/third_party/jdk/current/bin" ]]; then
  export PATH="${SRC_DIR}/third_party/jdk/current/bin:${PATH}"
fi

# Resolve password from KEY_PASSWORD_ANDROID (supports direct value or File-type variable)
RAW_PASS="${KEY_PASSWORD_ANDROID:-}"
if [[ -z "${RAW_PASS}" ]]; then
  echo "ERROR: KEY_PASSWORD_ANDROID is not set or empty." >&2
  echo "Configure KEY_PASSWORD_ANDROID in GitLab Settings -> CI/CD -> Variables." >&2
  exit 1
fi

if [[ -f "${RAW_PASS}" ]]; then
  RAW_PASS="$(cat "${RAW_PASS}")"
fi
# Strip leading/trailing whitespace & newlines
KEY_PASS="${RAW_PASS#"${RAW_PASS%%[![:space:]]*}"}"
KEY_PASS="${KEY_PASS%"${KEY_PASS##*[![:space:]]}"}"

if [[ -z "${KEY_PASS}" ]]; then
  echo "ERROR: KEY_PASSWORD_ANDROID resolved to an empty string." >&2
  exit 1
fi

# Resolve or download keystore
if [[ -z "${KEYSTORE_PATH}" ]]; then
  LOCAL_CANDIDATE="${SECURE_FILES_DIR}/${KEYSTORE_FILENAME}"
  if [[ -s "${LOCAL_CANDIDATE}" ]]; then
    KEYSTORE_PATH="${LOCAL_CANDIDATE}"
  elif [[ -n "${CI_API_V4_URL:-}" && -n "${CI_PROJECT_ID:-}" && -n "${CI_JOB_TOKEN:-}" ]]; then
    echo "Downloading '${KEYSTORE_FILENAME}' from GitLab CI/CD Secure Files API..."
    python3 - "${LOCAL_CANDIDATE}" "${KEYSTORE_FILENAME}" <<'PYEOF'
import json, os, sys, urllib.parse, urllib.request

dest, name = sys.argv[1], sys.argv[2]
api, pid, tok = os.environ.get("CI_API_V4_URL", "").rstrip("/"), os.environ.get("CI_PROJECT_ID", ""), os.environ.get("CI_JOB_TOKEN", "")

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        r = super().redirect_request(req, fp, code, msg, hdrs, newurl)
        if r and urllib.parse.urlparse(req.full_url).netloc != urllib.parse.urlparse(newurl).netloc:
            r.headers.pop("job-token", None)
        return r

opener = urllib.request.build_opener(SafeRedirect)
req = urllib.request.Request(f"{api}/projects/{pid}/secure_files?per_page=100", headers={"JOB-TOKEN": tok})
with opener.open(req, timeout=30) as r:
    files = json.loads(r.read().decode("utf-8"))

target = next((f for f in files if isinstance(f, dict) and f.get("name", "").strip() == name.strip()), None)
if not target:
    print(f"ERROR: Secure File '{name}' not found in GitLab project {pid}.", file=sys.stderr)
    sys.exit(1)

dl_req = urllib.request.Request(f"{api}/projects/{pid}/secure_files/{target['id']}/download", headers={"JOB-TOKEN": tok})
with opener.open(dl_req, timeout=60) as r:
    data = r.read()

os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
with open(dest, "wb") as f:
    f.write(data)
os.chmod(dest, 0o600)
print(f"Downloaded Secure File '{name}' ({len(data)} bytes) to {dest}")
PYEOF
    KEYSTORE_PATH="${LOCAL_CANDIDATE}"
  fi
fi

if [[ -z "${KEYSTORE_PATH}" || ! -s "${KEYSTORE_PATH}" ]]; then
  echo "ERROR: Keystore '${KEYSTORE_FILENAME}' not found at '${KEYSTORE_PATH:-${SECURE_FILES_DIR}/${KEYSTORE_FILENAME}}'." >&2
  echo "Upload '${KEYSTORE_FILENAME}' in GitLab Settings -> CI/CD -> Secure Files." >&2
  exit 1
fi

# Preflight check: verify keystore unlocks and alias exists
if command -v keytool >/dev/null 2>&1; then
  if ! BRAVING_KS_PASS="${KEY_PASS}" keytool -list \
    -keystore "${KEYSTORE_PATH}" \
    -alias "${KEY_ALIAS}" \
    -storepass:env BRAVING_KS_PASS >/dev/null 2>&1; then
    echo "ERROR: Failed to unlock keystore '${KEYSTORE_PATH}' with alias '${KEY_ALIAS}'." >&2
    echo "Verify KEY_PASSWORD_ANDROID and that keystore contains alias '${KEY_ALIAS}'." >&2
    exit 1
  fi
  echo "Keystore verified successfully with alias '${KEY_ALIAS}'."
fi

if [[ "${PREFLIGHT}" == "true" ]]; then
  echo " [OK] Signing preflight check passed."
  exit 0
fi

# Locate build tools (zipalign & apksigner)
find_tool() {
  local name="$1"
  local found=""
  if [[ -d "${SRC_DIR}/third_party/android_sdk/public/build-tools" ]]; then
    found=$(find "${SRC_DIR}/third_party/android_sdk/public/build-tools" -name "${name}" -type f 2>/dev/null | sort -V | tail -n 1 || true)
    [[ -n "${found}" && -x "${found}" ]] && { echo "${found}"; return 0; }
  fi
  if command -v "${name}" >/dev/null 2>&1; then
    command -v "${name}"
    return 0
  fi
  local sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-${HOME}/Android/Sdk}}"
  if [[ -d "${sdk}/build-tools" ]]; then
    found=$(find "${sdk}/build-tools" -name "${name}" -type f 2>/dev/null | sort -V | tail -n 1 || true)
    [[ -n "${found}" && -x "${found}" ]] && { echo "${found}"; return 0; }
  fi
  return 1
}

ZIPALIGN_BIN="${ZIPALIGN_PATH:-$(find_tool "zipalign" || true)}"
APKSIGNER_BIN="${APKSIGNER_PATH:-$(find_tool "apksigner" || true)}"

if [[ -z "${ZIPALIGN_BIN}" || ! -x "${ZIPALIGN_BIN}" ]]; then
  echo "ERROR: 'zipalign' not found on PATH or in Android SDK." >&2
  exit 1
fi
if [[ -z "${APKSIGNER_BIN}" || ! -x "${APKSIGNER_BIN}" ]]; then
  echo "ERROR: 'apksigner' not found on PATH or in Android SDK." >&2
  exit 1
fi

# Discover APKs if not specified
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
  echo "ERROR: No APK files found to sign." >&2
  exit 1
fi

TMP_ALIGNED=""
TMP_SIGNED=""
TMP_STRIPPED=""
cleanup() {
  rm -f "${TMP_ALIGNED:-}" "${TMP_SIGNED:-}" "${TMP_SIGNED:+${TMP_SIGNED}.idsig}" "${TMP_STRIPPED:-}" "${TMP_STRIPPED:+${TMP_STRIPPED}.nosig.tmp}"
}
trap cleanup EXIT

for apk in "${TARGET_APKS[@]}"; do
  if [[ ! -f "${apk}" ]]; then
    echo "ERROR: APK not found: ${apk}" >&2
    exit 1
  fi
  apk_name="$(basename "${apk}")"
  echo "--------------------------------------------------------"
  echo "Signing: ${apk}"
  echo "--------------------------------------------------------"

  TMP_ALIGNED="$(mktemp "${TMPDIR:-/tmp}/braving-aligned-XXXXXX.apk")"
  TMP_SIGNED="$(mktemp "${TMPDIR:-/tmp}/braving-signed-XXXXXX.apk")"
  TMP_STRIPPED="$(mktemp "${TMPDIR:-/tmp}/braving-stripped-XXXXXX.apk")"
  cp -f "${apk}" "${TMP_STRIPPED}"

  # Strip any existing v1 JAR signatures (e.g. debug signatures) to ensure clean single-identity signing
  python3 - "${TMP_STRIPPED}" <<'PYEOF'
import os, sys, zipfile
target = sys.argv[1]
tmp_clean = target + ".nosig.tmp"
has_sig = False
try:
    with zipfile.ZipFile(target, 'r') as zin:
        sig_entries = [
            n for n in zin.namelist()
            if n.startswith("META-INF/") and any(n.upper().endswith(ext) for ext in (".SF", ".RSA", ".DSA", ".EC", "MANIFEST.MF"))
        ]
        if sig_entries:
            has_sig = True
            with zipfile.ZipFile(tmp_clean, 'w') as zout:
                for item in zin.infolist():
                    if item.filename not in sig_entries:
                        zout.writestr(item, zin.read(item.filename))
    if has_sig and os.path.exists(tmp_clean):
        os.replace(tmp_clean, target)
except Exception:
    if os.path.exists(tmp_clean):
        try:
            os.unlink(tmp_clean)
        except OSError:
            pass
PYEOF

  "${ZIPALIGN_BIN}" -p -f 4 "${TMP_STRIPPED}" "${TMP_ALIGNED}"
  BRAVING_KS_PASS="${KEY_PASS}" "${APKSIGNER_BIN}" sign \
    --ks "${KEYSTORE_PATH}" \
    --ks-key-alias "${KEY_ALIAS}" \
    --ks-pass env:BRAVING_KS_PASS \
    --v1-signing-enabled true \
    --v2-signing-enabled true \
    --v3-signing-enabled true \
    --in "${TMP_ALIGNED}" \
    --out "${TMP_SIGNED}"

  "${APKSIGNER_BIN}" verify --verbose "${TMP_SIGNED}"
  mv -f "${TMP_SIGNED}" "${apk}"
  chmod 0644 "${apk}" 2>/dev/null || true
  rm -f "${TMP_ALIGNED}" "${TMP_STRIPPED}" "${TMP_STRIPPED}.nosig.tmp" "${apk}.idsig"

  # Sync between out/apks and build-workspace/src/out/Release/apks
  if [[ -d "${OUT_DIR}/apks" && "${apk}" != "${OUT_DIR}/apks/${apk_name}" ]]; then
    cp -f "${apk}" "${OUT_DIR}/apks/${apk_name}"
    chmod 0644 "${OUT_DIR}/apks/${apk_name}" 2>/dev/null || true
  fi
  if [[ -d "${OUTPUT_APK_DIR}" && "${apk}" != "${OUTPUT_APK_DIR}/${apk_name}" ]]; then
    cp -f "${apk}" "${OUTPUT_APK_DIR}/${apk_name}"
    chmod 0644 "${OUTPUT_APK_DIR}/${apk_name}" 2>/dev/null || true
  fi

  echo " [OK] Signed and verified: ${apk}"
done

echo "========================================================"
echo " APK SIGNING COMPLETE"
echo "========================================================"
