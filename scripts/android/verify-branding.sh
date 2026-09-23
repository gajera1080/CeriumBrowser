#!/usr/bin/env bash
# Braving Branding & Visual Asset Verification Script
# Enforces complete elimination of Brave lion branding across launcher,
# adaptive, themed, splash, and toolbar Shields assets.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "========================================================"
echo " Braving Branding & Package ID Verification"
echo "========================================================"

FAILURES=0

# 1. Verify release manifests specify org.braving.browser
echo "Checking release manifests..."
for manifest in "${REPO_ROOT}/metadata/releases"/*.yaml; do
  if [[ -f "${manifest}" ]]; then
    if ! grep -Eq 'package_id:[[:space:]]*"?org\.braving\.browser"?' "${manifest}"; then
      echo "ERROR: Manifest ${manifest} does not specify package_id: org.braving.browser" >&2
      FAILURES=$((FAILURES + 1))
    else
      echo " [OK] Manifest ${manifest} has valid package_id."
    fi
  fi
done

# 2. Check for branding patch
echo "Checking branding patch..."
if [[ -f "${REPO_ROOT}/patches/android/0001-braving-branding.patch" ]]; then
  echo " [OK] Branding patch found."
else
  echo "ERROR: patches/android/0001-braving-branding.patch is missing." >&2
  FAILURES=$((FAILURES + 1))
fi

if grep -Fq 'chrome_public_manifest_package = "${PACKAGE_ID}"' "${REPO_ROOT}/scripts/android/build-android.sh"; then
  echo " [OK] Package ID enforcement (chrome_public_manifest_package) present in build-android.sh."
else
  echo "ERROR: build-android.sh does not configure chrome_public_manifest_package." >&2
  FAILURES=$((FAILURES + 1))
fi

# 4. Check master vector logo
echo "Checking Braving master vector logo..."
if [[ -f "${REPO_ROOT}/branding/logo.svg" ]]; then
  echo " [OK] Master vector logo exists: branding/logo.svg"
else
  echo "ERROR: Missing master logo at ${REPO_ROOT}/branding/logo.svg" >&2
  FAILURES=$((FAILURES + 1))
fi

# 5. Check Android Vector Drawable logo
echo "Checking Android vector logo drawable..."
if [[ -f "${REPO_ROOT}/branding/android/drawable/ic_brave_logo.xml" ]]; then
  echo " [OK] Vector drawable exists: branding/android/drawable/ic_brave_logo.xml"
else
  echo "ERROR: Missing vector logo drawable at ${REPO_ROOT}/branding/android/drawable/ic_brave_logo.xml" >&2
  FAILURES=$((FAILURES + 1))
fi

# 6. Verify zero raster PNG files exist in branding/ (pure vector policy)
echo "Checking for illegal raster PNG files in branding/..."
FOUND_PNGS=$(find "${REPO_ROOT}/branding" -name "*.png" 2>/dev/null || true)
if [[ -n "${FOUND_PNGS}" ]]; then
  echo "ERROR: Found raster PNG files in branding/ (pure vector required):" >&2
  echo "${FOUND_PNGS}" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] Pure vector policy verified (no raster PNG files in branding/)."
fi

# 7. Check Android 13+ Themed Vector Icon (in drawable and drawable-night)
echo "Checking Android 13+ themed_app_icon.xml..."
UPSTREAM_LION_SIG="M74.68,37.99"
UPSTREAM_LION_NIGHT_SIG="M74.96,45.77"

for base_name in "res_brave_base" "res_brave_default_base"; do
  for draw_dir in "drawable" "drawable-night"; do
    themed="${REPO_ROOT}/branding/android/${base_name}/${draw_dir}/themed_app_icon.xml"
    if [[ ! -f "${themed}" ]]; then
      echo "ERROR: Missing themed_app_icon.xml in ${base_name}/${draw_dir}/" >&2
      FAILURES=$((FAILURES + 1))
    elif grep -q "${UPSTREAM_LION_SIG}" "${themed}" || grep -q "${UPSTREAM_LION_NIGHT_SIG}" "${themed}"; then
      echo "ERROR: ${base_name}/${draw_dir}/themed_app_icon.xml still contains upstream Brave lion vector path!" >&2
      FAILURES=$((FAILURES + 1))
    else
      echo " [OK] Android 13+ ${base_name}/${draw_dir}/themed_app_icon.xml verified."
    fi
  done
done

# 8. Check dedicated Braving Shields toolbar vector drawables
echo "Checking Braving Shields toolbar vector drawables..."
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
  fi
done
if [[ ${FAILURES} -eq 0 ]]; then
  echo " [OK] Dedicated Braving Shields toolbar vector drawables verified."
fi

# 9. Final status
if [[ ${FAILURES} -gt 0 ]]; then
  echo ""
  echo "FAILED: Branding verification detected ${FAILURES} issue(s)." >&2
  exit 1
fi

echo ""
echo "SUCCESS: All branding verification checks passed cleanly."
echo "No visible upstream Brave lion branding detected in Braving asset suite."
exit 0
