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

# 2. Prevent java_resources failure by removing any misplaced branding folders in brave-res
rm -rf "${BRAVE_DIR}/android/java/brave-res/mipmap-"* \
       "${BRAVE_DIR}/android/java/brave-res/res_brave"* \
       "${BRAVE_DIR}/android/java/brave-res/shields_drawables" 2>/dev/null || true

# 3. Clean up any old rasterized ic_brave_logo.png files in density folders
for density in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
  rm -f "${BRAVE_DIR}/android/java/brave-res/drawable-${density}/ic_brave_logo.png"
done

echo " [OK] Braving vector assets applied cleanly without polluting brave-res."




