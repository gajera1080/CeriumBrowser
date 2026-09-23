#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAVE_DIR="${1:-}"
if [[ -z "${BRAVE_DIR}" ]]; then
  echo "Usage: $0 <path-to-brave-core>" >&2
  exit 1
fi

echo "Applying Braving Android Vector Assets..."

# 1. Overlay ic_brave_logo.xml into brave-res/drawable/
mkdir -p "${BRAVE_DIR}/android/java/brave-res/drawable"
if [[ -f "${REPO_ROOT}/branding/android/drawable/ic_brave_logo.xml" ]]; then
  cp -f "${REPO_ROOT}/branding/android/drawable/ic_brave_logo.xml" "${BRAVE_DIR}/android/java/brave-res/drawable/ic_brave_logo.xml"
  echo " [OK] Copied ic_brave_logo.xml to brave-res/drawable/"
fi

# 2. Overlay Android 13+ themed vector icons into app/theme/brave/android/
THEME_ANDROID="${BRAVE_DIR}/app/theme/brave/android"
if [[ -d "${THEME_ANDROID}" ]]; then
  for base_name in "res_brave_base" "res_brave_default_base" "res_brave_beta_base" "res_brave_dev_base" "res_brave_nightly_base"; do
    target_base="${THEME_ANDROID}/${base_name}"
    if [[ -d "${target_base}" ]]; then
      mkdir -p "${target_base}/drawable" "${target_base}/drawable-night"
      if [[ -f "${REPO_ROOT}/branding/android/res_brave_base/drawable/themed_app_icon.xml" ]]; then
        cp -f "${REPO_ROOT}/branding/android/res_brave_base/drawable/themed_app_icon.xml" "${target_base}/drawable/themed_app_icon.xml"
      fi
      if [[ -f "${REPO_ROOT}/branding/android/res_brave_base/drawable-night/themed_app_icon.xml" ]]; then
        cp -f "${REPO_ROOT}/branding/android/res_brave_base/drawable-night/themed_app_icon.xml" "${target_base}/drawable-night/themed_app_icon.xml"
      fi
    fi
  done
  echo " [OK] Overlaid themed_app_icon.xml into brave-core theme bases."
fi

# 3. Overlay Shields toolbar vector drawables if @brave/leo is installed
LEO_DRAWABLE="${BRAVE_DIR}/node_modules/@brave/leo/tokens/android/drawable"
if [[ -d "${LEO_DRAWABLE}" && -d "${REPO_ROOT}/branding/android/shields_drawables" ]]; then
  cp -f "${REPO_ROOT}/branding/android/shields_drawables/"*.xml "${LEO_DRAWABLE}/"
  echo " [OK] Overlaid Shields vector drawables into @brave/leo tokens."
fi

# 4. Prevent java_resources failure by removing any misplaced branding folders in brave-res
rm -rf "${BRAVE_DIR}/android/java/brave-res/mipmap-"* \
       "${BRAVE_DIR}/android/java/brave-res/res_brave"* \
       "${BRAVE_DIR}/android/java/brave-res/shields_drawables" 2>/dev/null || true

# 5. Clean up any old rasterized ic_brave_logo.png files in density folders
for density in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
  rm -f "${BRAVE_DIR}/android/java/brave-res/drawable-${density}/ic_brave_logo.png"
done

echo " [OK] Braving vector assets applied cleanly to brave-core."




