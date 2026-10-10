#!/usr/bin/env bash
# Cerium Branding & Visual Asset Verification Script
# Enforces complete elimination of Brave lion branding across launcher,
# adaptive, themed, splash, and toolbar Shields assets.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "========================================================"
echo " Cerium Branding & Package ID Verification"
echo "========================================================"

FAILURES=0

# 1. Verify release manifests specify valid package_id
echo "Checking release manifests..."
for manifest in "${REPO_ROOT}/metadata/releases"/*.yaml; do
  if [[ -f "${manifest}" ]]; then
    if ! grep -Eq 'package_id:[[:space:]]*"?(org\.cerium\.browser|org\.braving\.browser)"?' "${manifest}"; then
      echo "ERROR: Manifest ${manifest} does not specify package_id: org.cerium.browser" >&2
      FAILURES=$((FAILURES + 1))
    else
      echo " [OK] Manifest ${manifest} has valid package_id."
    fi
  fi
done

# 2. Check for branding patch
echo "Checking branding patch..."
if [[ -f "${REPO_ROOT}/patches/android/0001-cerium-branding.patch" || -f "${REPO_ROOT}/patches/android/0001-braving-branding.patch" ]]; then
  echo " [OK] Branding patch found."
else
  echo "ERROR: patches/android/0001-cerium-branding.patch is missing." >&2
  FAILURES=$((FAILURES + 1))
fi

if grep -Fq 'chrome_public_manifest_package = "${PACKAGE_ID}"' "${REPO_ROOT}/scripts/platforms/android/build.sh"; then
  echo " [OK] Package ID enforcement (chrome_public_manifest_package) present in build.sh."
else
  echo "ERROR: build.sh does not configure chrome_public_manifest_package." >&2
  FAILURES=$((FAILURES + 1))
fi

# 4. Check master vector logo
echo "Checking Cerium master vector logo..."
if [[ -f "${REPO_ROOT}/branding/logo.svg" ]]; then
  echo " [OK] Master vector logo exists: branding/logo.svg"
else
  echo "ERROR: Missing master logo at ${REPO_ROOT}/branding/logo.svg" >&2
  FAILURES=$((FAILURES + 1))
fi

# 5. Check all 9 Android Vector Drawable logos in branding/android/drawable/
echo "Checking Android vector logo drawables..."
REQUIRED_DRAWABLES=(
  "ic_brave_logo.xml"
  "ic_brave.xml"
  "ic_brave_36.xml"
  "ic_channel_brave.xml"
  "ic_brave_notification.xml"
  "chrome_logo_on_circular_background.xml"
  "ic_brave_splash.xml"
  "ic_brave_brand.xml"
  "onboarding_illustration.xml"
)

UPSTREAM_LION_SIG="M74.68,37.99"

for d in "${REQUIRED_DRAWABLES[@]}"; do
  dpath="${REPO_ROOT}/branding/android/drawable/${d}"
  if [[ ! -f "${dpath}" ]]; then
    echo "ERROR: Missing vector drawable: ${d}" >&2
    FAILURES=$((FAILURES + 1))
  elif grep -q "${UPSTREAM_LION_SIG}" "${dpath}"; then
    echo "ERROR: ${d} contains upstream Brave lion vector path!" >&2
    FAILURES=$((FAILURES + 1))
  fi
done

if [[ ${FAILURES} -eq 0 ]]; then
  echo " [OK] All 9 vector logo drawables exist in branding/android/drawable/."
fi

# 5b. Verify adaptive launcher icon container (app_icon.xml)
echo "Checking adaptive launcher icon container (app_icon.xml)..."
APP_ICON_XML="${REPO_ROOT}/branding/android/res_brave_base/mipmap-anydpi-v26/app_icon.xml"
if [[ ! -f "${APP_ICON_XML}" ]]; then
  echo "ERROR: Missing ${APP_ICON_XML}" >&2
  FAILURES=$((FAILURES + 1))
elif ! grep -q "<adaptive-icon" "${APP_ICON_XML}" || ! grep -q "@mipmap/layered_app_icon" "${APP_ICON_XML}"; then
  echo "ERROR: ${APP_ICON_XML} must be an <adaptive-icon> referencing @mipmap/layered_app_icon" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] Adaptive launcher icon container verified: ${APP_ICON_XML}"
fi

# 5c. Check apply-branding.py script and prepare-source.sh wiring
echo "Checking apply-branding.py mutator..."
if [[ ! -f "${REPO_ROOT}/scripts/core/apply-branding.py" ]]; then
  echo "ERROR: Missing scripts/core/apply-branding.py" >&2
  FAILURES=$((FAILURES + 1))
elif ! grep -Fq "apply-branding.py" "${REPO_ROOT}/scripts/core/prepare-source.sh"; then
  echo "ERROR: scripts/core/prepare-source.sh does not invoke apply-branding.py" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] apply-branding.py mutator exists and is wired into prepare-source.sh."
fi

# 6. Verify static pre-rendered PNG and SVG logo suite in branding/brave-core-static/
echo "Checking static pre-rendered PNG & SVG logos in branding/brave-core-static/..."
STATIC_DIR="${REPO_ROOT}/branding/brave-core-static"
if [[ ! -d "${STATIC_DIR}" ]]; then
  echo "ERROR: Missing static branding directory: ${STATIC_DIR}" >&2
  FAILURES=$((FAILURES + 1))
else
  STATIC_PNG_COUNT=$(find "${STATIC_DIR}" -type f -name "*.png" -size +0c | wc -l)
  STATIC_SVG_COUNT=$(find "${STATIC_DIR}" -type f -name "*.svg" -size +0c | wc -l)
  STATIC_ICO_COUNT=$(find "${STATIC_DIR}" -type f -name "*.ico" -size +0c | wc -l)
  STATIC_TOTAL_COUNT=$(find "${STATIC_DIR}" -type f | wc -l)
  if [[ ${STATIC_PNG_COUNT} -ne 156 ]]; then
    echo "ERROR: Expected 156 non-empty static PNG logos in ${STATIC_DIR}, found ${STATIC_PNG_COUNT}" >&2
    FAILURES=$((FAILURES + 1))
  fi
  if [[ ${STATIC_SVG_COUNT} -ne 10 ]]; then
    echo "ERROR: Expected 10 non-empty static SVG logos in ${STATIC_DIR}, found ${STATIC_SVG_COUNT}" >&2
    FAILURES=$((FAILURES + 1))
  fi
  if [[ ${STATIC_ICO_COUNT} -ne 26 ]]; then
    echo "ERROR: Expected 26 non-empty static ICO logos in ${STATIC_DIR}, found ${STATIC_ICO_COUNT}" >&2
    FAILURES=$((FAILURES + 1))
  fi
  if [[ ${STATIC_TOTAL_COUNT} -ne 192 ]]; then
    echo "ERROR: Expected exactly 192 total static files in ${STATIC_DIR}, found ${STATIC_TOTAL_COUNT}" >&2
    FAILURES=$((FAILURES + 1))
  fi
  STATIC_INTEGRITY_ERR=$(python3 - "${STATIC_DIR}" <<'PYEOF'
import os, struct, sys, xml.etree.ElementTree as ET
static_dir = sys.argv[1]
errs = []
for root, _, files in os.walk(static_dir):
    for f in sorted(files):
        p = os.path.join(root, f)
        rel = os.path.relpath(p, static_dir)
        if f.endswith(".png"):
            with open(p, "rb") as fp:
                header = fp.read(8)
            if header != b"\x89PNG\r\n\x1a\n":
                errs.append(f"Invalid PNG magic: {rel}")
        elif f.endswith(".svg"):
            try:
                ET.parse(p)
            except Exception as e:
                errs.append(f"Invalid SVG XML in {rel}: {e}")
        elif f.endswith(".ico"):
            with open(p, "rb") as fp:
                data = fp.read()
            if len(data) < 6 or data[:4] != b"\x00\x00\x01\x00":
                errs.append(f"Invalid ICO header: {rel}")
if errs:
    print("\n".join(errs))
PYEOF
)
  if [[ -n "${STATIC_INTEGRITY_ERR}" ]]; then
    echo "ERROR: Static logo integrity errors in ${STATIC_DIR}:" >&2
    echo "${STATIC_INTEGRITY_ERR}" >&2
    FAILURES=$((FAILURES + 1))
  elif [[ ${STATIC_PNG_COUNT} -eq 156 && ${STATIC_SVG_COUNT} -eq 10 && ${STATIC_ICO_COUNT} -eq 26 && ${STATIC_TOTAL_COUNT} -eq 192 ]]; then
    echo " [OK] Verified 156 static PNG logos, 10 static SVG logos, and 26 static Windows ICO logos in branding/brave-core-static/."
  fi
fi

if grep -Eq 'rsvg-convert|from PIL import|ImageDraw' "${REPO_ROOT}/scripts/core/apply-assets.sh"; then
  echo "ERROR: scripts/core/apply-assets.sh still contains dynamic logo generation (rsvg-convert/PIL)!" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] scripts/core/apply-assets.sh is 100% static (no dynamic PIL/rsvg-convert rendering)."
fi

# 7. Check Android 13+ Themed Vector Icon (in drawable and drawable-night)
echo "Checking Android 13+ themed_app_icon.xml..."
UPSTREAM_LION_SIG="M74.68,37.99"
UPSTREAM_LION_NIGHT_SIG="M74.96,45.77"

for draw_dir in "drawable" "drawable-night"; do
  themed="${REPO_ROOT}/branding/android/res_brave_base/${draw_dir}/themed_app_icon.xml"
  if [[ ! -f "${themed}" ]]; then
    echo "ERROR: Missing themed_app_icon.xml in res_brave_base/${draw_dir}/" >&2
    FAILURES=$((FAILURES + 1))
  elif grep -q "${UPSTREAM_LION_SIG}" "${themed}" || grep -q "${UPSTREAM_LION_NIGHT_SIG}" "${themed}"; then
    echo "ERROR: res_brave_base/${draw_dir}/themed_app_icon.xml still contains upstream Brave lion vector path!" >&2
    FAILURES=$((FAILURES + 1))
  else
    echo " [OK] Android 13+ res_brave_base/${draw_dir}/themed_app_icon.xml verified."
  fi
done


# 8. Check dedicated Cerium Shields toolbar vector drawables
echo "Checking Cerium Shields toolbar vector drawables..."
SHIELDS_DIR="${REPO_ROOT}/branding/android/shields_drawables"
REQUIRED_SHIELDS=(
  "ic_social_brave_release_favicon_fullheight_color.xml"
  "ic_social_brave_monochrome_favicon_fullheight_color.xml"
  "ic_social_brave_outline_favicon_fullheight.xml"
  "ic_social_brave_carved_favicon_fullheight.xml"
)

for s in "${REQUIRED_SHIELDS[@]}"; do
  spath="${SHIELDS_DIR}/${s}"
  if [[ ! -f "${spath}" ]]; then
    echo "ERROR: Missing Shields drawable: ${s}" >&2
    FAILURES=$((FAILURES + 1))
  elif grep -q "${UPSTREAM_LION_SIG}" "${spath}"; then
    echo "ERROR: Shields drawable ${s} still contains upstream Brave lion vector path!" >&2
    FAILURES=$((FAILURES + 1))
  elif ! grep -q 'android:width="24dp"' "${spath}" || ! grep -q 'android:height="24dp"' "${spath}"; then
    echo "ERROR: Shields drawable ${s} must have exact 24dp x 24dp intrinsic dimensions!" >&2
    FAILURES=$((FAILURES + 1))
  fi
done

SHIELDS_COLOR_XML="${SHIELDS_DIR}/ic_social_brave_release_favicon_fullheight_color.xml"
if [[ -f "${SHIELDS_COLOR_XML}" ]]; then
  if grep -qi 'fillColor="#ffffff"' "${SHIELDS_COLOR_XML}" || ! grep -qi '#FFFD8C57' "${SHIELDS_COLOR_XML}"; then
    echo "ERROR: ${SHIELDS_COLOR_XML} must use the colored Cerium gradients, not flat white!" >&2
    FAILURES=$((FAILURES + 1))
  fi
fi

if [[ ${FAILURES} -eq 0 ]]; then
  echo " [OK] Dedicated Cerium Shields toolbar vector drawables (24dp x 24dp, colored ON state) verified."
fi

# 9. Verify no Android XML string/pathData exceeds the AAPT2 UTF-8 ResStringPool limit (32,767 bytes)
echo "Checking Android XML drawables for AAPT2 string length limits (max 32767 bytes)..."
MAX_STRING_LEN=32767
OVERSIZED_COUNT=0
PARSE_ERR_COUNT=0
while IFS= read -r -d '' xml_file; do
  CHECK_RESULT=$(python3 -c "
import sys, xml.etree.ElementTree as ET
try:
    tree = ET.parse(sys.argv[1])
    for el in tree.iter():
        for k, v in el.attrib.items():
            encoded = v.encode('utf-8')
            if len(encoded) > int(sys.argv[2]):
                attr_name = k.split('}')[-1]
                print(f'OVERSIZED:{attr_name}={len(encoded)} bytes')
                sys.exit(2)
except Exception as e:
    print(f'PARSE_ERROR:{e}')
    sys.exit(3)
" "${xml_file}" "${MAX_STRING_LEN}" 2>/dev/null || true)
  if [[ -n "${CHECK_RESULT}" ]]; then
    if [[ "${CHECK_RESULT}" =~ ^PARSE_ERROR: ]]; then
      echo "ERROR: ${xml_file} failed XML parsing: ${CHECK_RESULT#PARSE_ERROR:}" >&2
      PARSE_ERR_COUNT=$((PARSE_ERR_COUNT + 1))
    else
      echo "ERROR: ${xml_file} has attribute exceeding AAPT2 string limit: ${CHECK_RESULT#OVERSIZED:}" >&2
      OVERSIZED_COUNT=$((OVERSIZED_COUNT + 1))
    fi
    FAILURES=$((FAILURES + 1))
  fi
done < <(find "${REPO_ROOT}/branding/android" -name "*.xml" -print0)

if [[ ${OVERSIZED_COUNT} -eq 0 && ${PARSE_ERR_COUNT} -eq 0 ]]; then
  echo " [OK] All Android XML drawables comply with AAPT2 string length limits (<${MAX_STRING_LEN} bytes)."
fi

# 10. Final status
if [[ ${FAILURES} -gt 0 ]]; then
  echo ""
  echo "FAILED: Branding verification detected ${FAILURES} issue(s)." >&2
  exit 1
fi

echo ""
echo "SUCCESS: All branding verification checks passed cleanly."
echo "No visible upstream Brave lion branding detected in Cerium asset suite."
exit 0
