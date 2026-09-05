#!/usr/bin/env bash
# Braving Reproducible Build Comparator
# Usage: ./scripts/verify-reproducibility.sh <apk_1> <apk_2>

set -euo pipefail

APK1="${1:-}"
APK2="${2:-}"

if [[ -z "${APK1}" || -z "${APK2}" ]]; then
  echo "Usage: $0 <path_to_first_apk> <path_to_second_apk>" >&2
  exit 1
fi

if [[ ! -f "${APK1}" || ! -f "${APK2}" ]]; then
  echo "ERROR: One or both APK files do not exist." >&2
  exit 1
fi

echo "========================================================"
echo " Braving Reproducibility Verification"
echo " Build 1: ${APK1}"
echo " Build 2: ${APK2}"
echo "========================================================"

HASH1=$(sha256sum "${APK1}" | awk '{print $1}')
HASH2=$(sha256sum "${APK2}" | awk '{print $1}')

echo "SHA256 (Build 1): ${HASH1}"
echo "SHA256 (Build 2): ${HASH2}"

if [[ "${HASH1}" == "${HASH2}" ]]; then
  echo ""
  echo "SUCCESS: Bit-for-bit identical APKs produced. Build is 100% reproducible!"
  exit 0
fi

echo ""
echo "DIFFERENCE DETECTED. Analyzing internal differences with diffoscope/zipcmp..."

if command -v diffoscope >/dev/null 2>&1; then
  diffoscope "${APK1}" "${APK2}" || true
else
  echo "Comparing zip directory structures..."
  unzip -l "${APK1}" > /tmp/apk1_list.txt
  unzip -l "${APK2}" > /tmp/apk2_list.txt
  diff -u /tmp/apk1_list.txt /tmp/apk2_list.txt || true
fi

echo ""
echo "NOTICE: Check for timestamps, debug symbols, or signing metadata differences."
exit 1
