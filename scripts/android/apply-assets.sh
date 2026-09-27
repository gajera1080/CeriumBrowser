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

# 2. Overlay Android adaptive & themed vector icons into app/theme/brave/android/res_brave_base/
THEME_ANDROID="${BRAVE_DIR}/app/theme/brave/android"
if [[ -d "${THEME_ANDROID}" ]]; then
  target_base="${THEME_ANDROID}/res_brave_base"
  if [[ -d "${target_base}" ]]; then
    mkdir -p "${target_base}/drawable" "${target_base}/drawable-night" "${target_base}/mipmap-anydpi-v26"
    if [[ -f "${REPO_ROOT}/branding/android/res_brave_base/drawable/themed_app_icon.xml" ]]; then
      cp -f "${REPO_ROOT}/branding/android/res_brave_base/drawable/themed_app_icon.xml" "${target_base}/drawable/themed_app_icon.xml"
    fi
    if [[ -f "${REPO_ROOT}/branding/android/res_brave_base/drawable-night/themed_app_icon.xml" ]]; then
      cp -f "${REPO_ROOT}/branding/android/res_brave_base/drawable-night/themed_app_icon.xml" "${target_base}/drawable-night/themed_app_icon.xml"
    fi
    if [[ -f "${REPO_ROOT}/branding/android/res_brave_base/mipmap-anydpi-v26/app_icon.xml" ]]; then
      cp -f "${REPO_ROOT}/branding/android/res_brave_base/mipmap-anydpi-v26/app_icon.xml" "${target_base}/mipmap-anydpi-v26/app_icon.xml"
    fi
  fi
  echo " [OK] Overlaid themed_app_icon.xml and mipmap-anydpi-v26/app_icon.xml into app/theme/brave/android/res_brave_base/."

  # 3. Overlay Shields toolbar vector drawables into app/theme/brave/android/shields_drawables/
  if [[ -d "${REPO_ROOT}/branding/android/shields_drawables" ]]; then
    mkdir -p "${THEME_ANDROID}/shields_drawables"
    cp -f "${REPO_ROOT}/branding/android/shields_drawables/"*.xml "${THEME_ANDROID}/shields_drawables/"
    echo " [OK] Overlaid Shields vector drawables into app/theme/brave/android/shields_drawables/."
  fi
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
