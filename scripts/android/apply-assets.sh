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




