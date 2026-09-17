#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BRAVE_DIR="${1:-}"
if [[ -z "${BRAVE_DIR}" ]]; then
  echo "Usage: $0 <path-to-brave-core>" >&2
  exit 1
fi

echo "Generating Android Assets..."

echo "Copying generated assets to brave-res..."
mkdir -p "${BRAVE_DIR}/android/java/brave-res/drawable-xxhdpi"
mkdir -p "${BRAVE_DIR}/android/java/brave-res/drawable-xxxhdpi"

cp -a "${REPO_ROOT}/branding/android/"* "${BRAVE_DIR}/android/java/brave-res/"

# Replace ic_brave_logo.xml with the generated fre_product_logo.png
cp "${REPO_ROOT}/branding/android/res_brave_default/drawable-xxhdpi/fre_product_logo.png" "${BRAVE_DIR}/android/java/brave-res/drawable-xxhdpi/ic_brave_logo.png"
cp "${REPO_ROOT}/branding/android/res_brave_default/drawable-xxxhdpi/fre_product_logo.png" "${BRAVE_DIR}/android/java/brave-res/drawable-xxxhdpi/ic_brave_logo.png"
rm -f "${BRAVE_DIR}/android/java/brave-res/drawable/ic_brave_logo.xml"


