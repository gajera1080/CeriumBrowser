#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BRAVE_DIR="${1:-}"
if [[ -z "${BRAVE_DIR}" ]]; then
  echo "Usage: $0 <path-to-brave-core>" >&2
  exit 1
fi

echo "Applying Braving Vector & Raster Branding Assets..."

# 1. Overlay Android vector drawables into brave-res/drawable/, res/drawable/, and first_run/
mkdir -p "${BRAVE_DIR}/android/java/brave-res/drawable"
mkdir -p "${BRAVE_DIR}/android/java/res/drawable"
mkdir -p "${BRAVE_DIR}/browser/first_run/android/java/res/drawable"

XML_COUNT=0
copy_static_xml() {
  local src="$1"
  local dst="$2"
  if [[ ! -s "${src}" ]]; then
    echo "ERROR: Missing or empty static branding XML source: ${src}" >&2
    exit 1
  fi
  cp -f "${src}" "${dst}"
  if [[ ! -s "${dst}" ]]; then
    echo "ERROR: Static branding XML copy produced empty or missing file: ${dst}" >&2
    exit 1
  fi
  XML_COUNT=$((XML_COUNT + 1))
}

BRAVE_RES_VECTORS=(
  "ic_brave_logo.xml"
  "ic_brave.xml"
  "ic_brave_36.xml"
  "ic_channel_brave.xml"
  "ic_brave_notification.xml"
)

for vec in "${BRAVE_RES_VECTORS[@]}"; do
  copy_static_xml "${REPO_ROOT}/branding/android/drawable/${vec}" "${BRAVE_DIR}/android/java/brave-res/drawable/${vec}"
  echo " [OK] Copied ${vec} to android/java/brave-res/drawable/"
done

copy_static_xml "${REPO_ROOT}/branding/android/drawable/chrome_logo_on_circular_background.xml" \
                "${BRAVE_DIR}/android/java/res/drawable/chrome_logo_on_circular_background.xml"
echo " [OK] Copied chrome_logo_on_circular_background.xml to android/java/res/drawable/"

FIRST_RUN_VECTORS=(
  "ic_brave_splash.xml"
  "ic_brave_brand.xml"
  "onboarding_illustration.xml"
)

for vec in "${FIRST_RUN_VECTORS[@]}"; do
  copy_static_xml "${REPO_ROOT}/branding/android/drawable/${vec}" "${BRAVE_DIR}/browser/first_run/android/java/res/drawable/${vec}"
  echo " [OK] Copied ${vec} to browser/first_run/android/java/res/drawable/"
done

# 2. Overlay Android adaptive & themed vector icons into app/theme/brave/android/res_brave_base/ (and default/origin variants)
for theme_root in "${BRAVE_DIR}/app/theme/brave/android" "${BRAVE_DIR}/app/theme/brave_origin/android"; do
  for base_sub in "res_brave_base" "res_brave_default_base"; do
    target_base="${theme_root}/${base_sub}"
    mkdir -p "${target_base}/drawable" "${target_base}/drawable-night" "${target_base}/mipmap-anydpi-v26" "${target_base}/mipmap-nodpi"
    copy_static_xml "${REPO_ROOT}/branding/android/res_brave_base/drawable/themed_app_icon.xml" "${target_base}/drawable/themed_app_icon.xml"
    copy_static_xml "${REPO_ROOT}/branding/android/res_brave_base/drawable-night/themed_app_icon.xml" "${target_base}/drawable-night/themed_app_icon.xml"
    for xml_src in "${REPO_ROOT}/branding/android/res_brave_base/mipmap-anydpi-v26/"*.xml; do
      copy_static_xml "${xml_src}" "${target_base}/mipmap-anydpi-v26/$(basename "${xml_src}")"
    done
    for xml_src in "${REPO_ROOT}/branding/android/res_brave_base/mipmap-nodpi/"*.xml; do
      copy_static_xml "${xml_src}" "${target_base}/mipmap-nodpi/$(basename "${xml_src}")"
    done
  done
done
echo " [OK] Overlaid adaptive app_icon.xml, layered_app_icon.xml, and themed_app_icon.xml into res_brave_base/."

# 3. Overlay Shields toolbar vector drawables into app/theme/brave/android/shields_drawables/
THEME_ANDROID="${BRAVE_DIR}/app/theme/brave/android"
mkdir -p "${THEME_ANDROID}/shields_drawables"
for xml_src in "${REPO_ROOT}/branding/android/shields_drawables/"*.xml; do
  copy_static_xml "${xml_src}" "${THEME_ANDROID}/shields_drawables/$(basename "${xml_src}")"
  if [[ -d "${BRAVE_DIR}/node_modules/@brave/leo/tokens/android/drawable" ]]; then
    copy_static_xml "${xml_src}" "${BRAVE_DIR}/node_modules/@brave/leo/tokens/android/drawable/$(basename "${xml_src}")"
  fi
done
if [[ ${XML_COUNT} -lt 37 ]]; then
  echo "ERROR: Expected at least 37 static XML overlays, but copied ${XML_COUNT}." >&2
  exit 1
fi
echo " [OK] Overlaid Shields vector drawables into app/theme/brave/android/shields_drawables/ (${XML_COUNT} total XML files copied)."

# 4. Copy all static pre-rendered raster PNG and SVG logos from branding/brave-core-static/ into BRAVE_DIR
STATIC_DIR="${REPO_ROOT}/branding/brave-core-static"
if [[ ! -d "${STATIC_DIR}" ]]; then
  echo "ERROR: Missing static branding directory at ${STATIC_DIR}" >&2
  exit 1
fi

PNG_COUNT=0
SVG_COUNT=0
while IFS= read -r -d '' src_file; do
  rel_path="${src_file#${STATIC_DIR}/}"
  dest_file="${BRAVE_DIR}/${rel_path}"
  mkdir -p "$(dirname "${dest_file}")"
  cp -f "${src_file}" "${dest_file}"
  if [[ ! -s "${dest_file}" ]]; then
    echo "ERROR: Static branding file copy produced empty or missing file: ${dest_file}" >&2
    exit 1
  fi
  if [[ "${rel_path}" == *.png ]]; then
    PNG_COUNT=$((PNG_COUNT + 1))
  elif [[ "${rel_path}" == *.svg ]]; then
    SVG_COUNT=$((SVG_COUNT + 1))
  fi
done < <(find "${STATIC_DIR}" -type f \( -name "*.png" -o -name "*.svg" \) -print0 | sort -z)

if [[ ${PNG_COUNT} -ne 156 || ${SVG_COUNT} -ne 10 ]]; then
  echo "ERROR: Expected 156 static PNGs and 10 static SVGs in ${STATIC_DIR}, but copied ${PNG_COUNT} PNGs and ${SVG_COUNT} SVGs." >&2
  exit 1
fi
echo " [OK] Copied ${PNG_COUNT} static raster PNG logos and ${SVG_COUNT} static SVG logos into brave-core."

# 5. Prevent java_resources failure by removing any misplaced branding folders in brave-res
rm -rf "${BRAVE_DIR}/android/java/brave-res/mipmap-"* \
       "${BRAVE_DIR}/android/java/brave-res/res_brave"* \
       "${BRAVE_DIR}/android/java/brave-res/shields_drawables" 2>/dev/null || true

# 6. Clean up any old rasterized ic_brave_logo.png files in density folders
for density in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
  rm -f "${BRAVE_DIR}/android/java/brave-res/drawable-${density}/ic_brave_logo.png"
done

echo " [OK] Braving vector and raster assets applied cleanly to brave-core."
