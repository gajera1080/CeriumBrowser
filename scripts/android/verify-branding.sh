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

# 2. Check branding mutator for package ID remapping
echo "Checking branding mutator script for package ID..."
if grep -Fq '"com.brave.browser", "org.braving.browser"' "${REPO_ROOT}/scripts/android/apply-branding.py"; then
  echo " [OK] Package ID remapping (com.brave.browser -> org.braving.browser) present in mutator."
else
  echo "ERROR: apply-branding.py does not remap package ID." >&2
  FAILURES=$((FAILURES + 1))
fi

# 3. Check for application label replacement script
echo "Checking branding mutator script..."
if [[ -f "${REPO_ROOT}/scripts/android/apply-branding.py" ]] && grep -Fq 'replace_in_file(f, "Brave", "Braving")' "${REPO_ROOT}/scripts/android/apply-branding.py"; then
  echo " [OK] Branding mutator properly targets Brave -> Braving."
else
  echo "ERROR: apply-branding.py is missing or missing expected replacements." >&2
  FAILURES=$((FAILURES + 1))
fi

# 4. Check master logo
echo "Checking Braving master logo..."
if [[ ! -f "${REPO_ROOT}/branding/logo.png" ]]; then
  echo "ERROR: Missing master logo at ${REPO_ROOT}/branding/logo.png" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] Master logo exists: branding/logo.png"
fi

# 5. Check launcher icon densities (legacy & adaptive)
echo "Checking Android launcher icon densities..."
DENSITIES=("mdpi" "hdpi" "xhdpi" "xxhdpi" "xxxhdpi")
for d in "${DENSITIES[@]}"; do
  # Standard launcher icon
  f="${REPO_ROOT}/branding/android/res_brave_base/mipmap-${d}/app_icon.png"
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: Missing app_icon.png for density ${d}" >&2
    FAILURES=$((FAILURES + 1))
  fi
  
  # Adaptive foreground
  fg="${REPO_ROOT}/branding/android/res_brave_base/mipmap-${d}/layered_app_icon.png"
  if [[ ! -f "${fg}" ]]; then
    echo "ERROR: Missing layered_app_icon.png (foreground) for density ${d}" >&2
    FAILURES=$((FAILURES + 1))
  fi
  
  # Adaptive background
  bg="${REPO_ROOT}/branding/android/res_brave_base/mipmap-${d}/layered_app_icon_background.png"
  if [[ ! -f "${bg}" ]]; then
    echo "ERROR: Missing layered_app_icon_background.png (background) for density ${d}" >&2
    FAILURES=$((FAILURES + 1))
  fi
done
if [[ ${FAILURES} -eq 0 ]]; then
  echo " [OK] All legacy & adaptive launcher icon densities verified (foreground & background)."
fi

# 6. Check First Run Experience (FRE) splash screen logos
echo "Checking FRE splash screen logos..."
for d in "${DENSITIES[@]}"; do
  fre="${REPO_ROOT}/branding/android/res_brave/drawable-${d}/fre_product_logo.png"
  if [[ ! -f "${fre}" ]]; then
    echo "ERROR: Missing fre_product_logo.png for density ${d}" >&2
    FAILURES=$((FAILURES + 1))
  fi
done
if [[ ${FAILURES} -eq 0 ]]; then
  echo " [OK] All FRE splash logo densities verified."
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
