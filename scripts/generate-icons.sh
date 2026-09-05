#!/usr/bin/env bash
# Braving Icon Generation Script
# Generates all Android mipmap and drawable densities from branding/logo.png

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SRC_LOGO="${REPO_ROOT}/branding/logo.png"

if [[ ! -f "${SRC_LOGO}" ]]; then
  echo "ERROR: Source logo not found at ${SRC_LOGO}" >&2
  exit 1
fi

echo "========================================================"
echo " Generating Android Assets from ${SRC_LOGO}"
echo "========================================================"

python3 - "${SRC_LOGO}" "${REPO_ROOT}" <<'PYEOF'
import os, sys
from PIL import Image

src_img = Image.open(sys.argv[1]).convert('RGBA')
braving_root = sys.argv[2]

legacy_sizes = {
    'mipmap-mdpi': 48,
    'mipmap-hdpi': 72,
    'mipmap-xhdpi': 96,
    'mipmap-xxhdpi': 144,
    'mipmap-xxxhdpi': 192,
}

adaptive_sizes = {
    'mipmap-mdpi': 108,
    'mipmap-hdpi': 162,
    'mipmap-xhdpi': 216,
    'mipmap-xxhdpi': 324,
    'mipmap-xxxhdpi': 432,
}

fre_sizes = {
    'drawable-mdpi': 96,
    'drawable-hdpi': 144,
    'drawable-xhdpi': 192,
    'drawable-xxhdpi': 288,
    'drawable-xxxhdpi': 384,
}

branding_base = os.path.join(braving_root, 'branding/android')

# 1. Base channel icons (res_brave_base, res_brave_default_base)
for base_name in ['res_brave_base', 'res_brave_default_base']:
    target = os.path.join(branding_base, base_name)
    for density, sz in legacy_sizes.items():
        d_path = os.path.join(target, density)
        os.makedirs(d_path, exist_ok=True)
        inner_sz = int(sz * 0.88)
        inner = src_img.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
        offset = (sz - inner_sz) // 2
        canvas.paste(inner, (offset, offset), inner)
        canvas.save(os.path.join(d_path, 'app_icon.png'), 'PNG')

    for density, sz in adaptive_sizes.items():
        d_path = os.path.join(target, density)
        os.makedirs(d_path, exist_ok=True)
        inner_sz = int(sz * 0.68)
        inner = src_img.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
        offset = (sz - inner_sz) // 2
        canvas.paste(inner, (offset, offset), inner)
        canvas.save(os.path.join(d_path, 'layered_app_icon.png'), 'PNG')

# 2. FRE splash logos (res_brave, res_brave_default)
for fre_name in ['res_brave', 'res_brave_default']:
    target = os.path.join(branding_base, fre_name)
    for density, sz in fre_sizes.items():
        d_path = os.path.join(target, density)
        os.makedirs(d_path, exist_ok=True)
        inner = src_img.resize((sz, sz), Image.Resampling.LANCZOS)
        inner.save(os.path.join(d_path, 'fre_product_logo.png'), 'PNG')

# 3. Direct top-level mipmap fallback icons
for density, sz in legacy_sizes.items():
    d_path = os.path.join(branding_base, density)
    os.makedirs(d_path, exist_ok=True)
    inner_sz = int(sz * 0.88)
    inner = src_img.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
    offset = (sz - inner_sz) // 2
    canvas.paste(inner, (offset, offset), inner)
    canvas.save(os.path.join(d_path, 'app_icon.png'), 'PNG')

print(' [OK] Android icon sets generated successfully.')
PYEOF

echo "All Android branding assets updated."
