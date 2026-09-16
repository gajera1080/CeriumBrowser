#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAVE_DIR="$1"

echo "Generating Android Assets..."

echo "Copying generated assets to brave-res..."
cp -a "${REPO_ROOT}/branding/android/"* "${BRAVE_DIR}/android/java/brave-res/"

# Replace ic_brave_logo.xml with the generated fre_product_logo.png
# Wait, Android requires XML for Vector drawables, but if we delete it, and Android falls back to mipmap/drawable?
# Actually, the First Run Experience explicitly references @drawable/ic_brave_logo!
# If we replace it with a PNG, we must name it ic_brave_logo.png!
cp "${REPO_ROOT}/branding/android/res_brave_default/drawable-xxhdpi/fre_product_logo.png" "${BRAVE_DIR}/android/java/brave-res/drawable-xxhdpi/ic_brave_logo.png" || true
cp "${REPO_ROOT}/branding/android/res_brave_default/drawable-xxxhdpi/fre_product_logo.png" "${BRAVE_DIR}/android/java/brave-res/drawable-xxxhdpi/ic_brave_logo.png" || true
rm -f "${BRAVE_DIR}/android/java/brave-res/drawable/ic_brave_logo.xml"


