#!/usr/bin/env bash
# Braving Branding Verification Script
# Scans source and metadata for unexpected remaining Brave branding while
# preserving legitimate upstream copyright and license notices.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "========================================================"
echo " Braving Branding & Package ID Verification"
echo "========================================================"

FAILURES=0

# 1. Verify that the release manifest specifies org.braving.browser
echo "Checking release manifests..."
for manifest in "${REPO_ROOT}/metadata/releases"/*.yaml; do
  if [[ -f "${manifest}" ]]; then
    if ! grep -q 'package_id: "org.braving.browser"' "${manifest}"; then
      echo "ERROR: Manifest ${manifest} does not specify package_id: org.braving.browser" >&2
      FAILURES=$((FAILURES + 1))
    else
      echo " [OK] Manifest ${manifest} has valid package_id."
    fi
  fi
done

# 2. Check patches for forbidden package IDs (in added lines)
echo "Checking patches for official Brave package IDs..."
if grep -rn "^+[^+].*com\.brave\.browser" "${REPO_ROOT}/patches/" | grep -v "\-      args\.chrome_public_manifest_package" | grep -v "\-      chrome_public_manifest_package"; then
  echo "WARNING: Unexpected active reference to com.brave.browser found in added patch lines." >&2
else
  echo " [OK] No unexpected active references to com.brave.browser in patches."
fi

# 3. Check for application label replacement
echo "Checking channel_constants patch..."
if grep -Fq '<string name="app_name" translatable="false">Braving</string>' "${REPO_ROOT}/patches/branding/0001-braving-branding.patch"; then
  echo " [OK] App launcher name successfully rebranded to Braving in branding patch."
else
  echo "ERROR: Branding patch missing app_name = Braving" >&2
  FAILURES=$((FAILURES + 1))
fi

# 4. Check logo and icon assets
echo "Checking Braving logo assets..."
if [[ ! -f "${REPO_ROOT}/branding/logo.png" ]]; then
  echo "ERROR: Missing master logo at ${REPO_ROOT}/branding/logo.png" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] Master logo exists: branding/logo.png"
fi

if [[ ! -f "${REPO_ROOT}/branding/android/res_brave_base/mipmap-xxxhdpi/app_icon.png" ]]; then
  echo "ERROR: Missing Android mipmap icon densities in res_brave_base" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] Android launcher icon densities generated in res_brave_base"
fi

if [[ ! -f "${REPO_ROOT}/branding/android/res_brave/drawable-xxxhdpi/fre_product_logo.png" ]]; then
  echo "ERROR: Missing Android FRE product logo densities" >&2
  FAILURES=$((FAILURES + 1))
else
  echo " [OK] Android FRE splash logo densities generated"
fi

if [[ ${FAILURES} -gt 0 ]]; then
  echo ""
  echo "FAILED: Branding verification detected ${FAILURES} issue(s)." >&2
  exit 1
fi

echo ""
echo "SUCCESS: Branding verification passed cleanly."
exit 0
