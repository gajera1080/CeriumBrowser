#!/usr/bin/env bash
# Braving Icon & Vector Asset Generation Script
# Generates all Android mipmap, drawable densities, adaptive layers,
# themed vector icons, and Braving Shields toolbar vector drawables from branding/logo.png

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

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

src_path = sys.argv[1]
braving_root = sys.argv[2]
src_img = Image.open(src_path).convert('RGBA')

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
    
    # 1a. Legacy icons
    for density, sz in legacy_sizes.items():
        d_path = os.path.join(target, density)
        os.makedirs(d_path, exist_ok=True)
        inner_sz = int(sz * 0.88)
        inner = src_img.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
        offset = (sz - inner_sz) // 2
        canvas.paste(inner, (offset, offset), inner)
        canvas.save(os.path.join(d_path, 'app_icon.png'), 'PNG')

    # 1b. Adaptive foreground & background
    for density, sz in adaptive_sizes.items():
        d_path = os.path.join(target, density)
        os.makedirs(d_path, exist_ok=True)
        
        # Foreground
        inner_sz = int(sz * 0.68)
        inner = src_img.resize((inner_sz, inner_sz), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
        offset = (sz - inner_sz) // 2
        canvas.paste(inner, (offset, offset), inner)
        canvas.save(os.path.join(d_path, 'layered_app_icon.png'), 'PNG')
        
        # Background: clean solid white canvas for crisp contrast
        bg = Image.new('RGBA', (sz, sz), (255, 255, 255, 255))
        bg.save(os.path.join(d_path, 'layered_app_icon_background.png'), 'PNG')

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

print(' [OK] Android raster icon sets (legacy, adaptive, splash) generated.')

# 4. Android 13+ Themed Vector Icon (themed_app_icon.xml)
# Clean shield vector inside 108dp safe viewport, tintable by Android Material You
themed_icon_xml = '''<?xml version="1.0" encoding="utf-8"?>
<!-- Braving Android 13+ Monochrome Themed App Icon -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="108"
    android:viewportHeight="108">
  <path
      android:pathData="M54,22L27,34v20c0,18.8 11.5,36.4 27,40.7c15.5,-4.3 27,-21.9 27,-40.7V34L54,22zM54,28.4l21.6,9.6v16c0,15.1 -9.2,29.6 -21.6,33.2C41.6,83.6 32.4,69.1 32.4,54V38L54,28.4zM48.2,64.2L36.8,52.8l3.4,-3.4l8,8l18,-18l3.4,3.4L48.2,64.2z"
      android:fillColor="#000000"
      android:fillType="evenOdd"/>
</vector>
'''

for base_name in ['res_brave_base', 'res_brave_default_base']:
    for draw_dir in ['drawable', 'drawable-night']:
        d_path = os.path.join(branding_base, base_name, draw_dir)
        os.makedirs(d_path, exist_ok=True)
        with open(os.path.join(d_path, 'themed_app_icon.xml'), 'w') as f:
            f.write(themed_icon_xml)

print(' [OK] Android 13+ themed_app_icon.xml vector drawables generated (drawable and drawable-night).')

# 5. Dedicated Braving Shields Toolbar Vector Drawables
# Replaces ic_social_brave_release_favicon_fullheight_color and variants
shields_drawables_dir = os.path.join(branding_base, 'shields_drawables')
os.makedirs(shields_drawables_dir, exist_ok=True)

# 5a. Active Braving Shields icon: vibrant blue shield with white checkmark
shields_active_xml = '''<?xml version="1.0" encoding="utf-8"?>
<!-- Braving Shields Active Toolbar Icon -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
  <path
      android:fillColor="#2563EB"
      android:pathData="M12,2L4,5.5v5.5c0,5.25 3.4,10.15 8,11.35c4.6,-1.2 8,-6.1 8,-11.35V5.5L12,2z"/>
  <path
      android:fillColor="#FFFFFF"
      android:pathData="M10.5,15.5l-3.5,-3.5 1.41,-1.41L10.5,12.67l5.59,-5.59L17.5,8.5z"/>
</vector>
'''

# 5b. Monochrome/Inactive Braving Shields icon: grey shield with pause indicator
shields_monochrome_xml = '''<?xml version="1.0" encoding="utf-8"?>
<!-- Braving Shields Inactive / Paused Toolbar Icon -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
  <path
      android:fillColor="#8E8E93"
      android:pathData="M12,2L4,5.5v5.5c0,5.25 3.4,10.15 8,11.35c4.6,-1.2 8,-6.1 8,-11.35V5.5L12,2z"/>
  <path
      android:fillColor="#F2F2F7"
      android:pathData="M10,9h1.5v6H10zM12.5,9H14v6h-1.5z"/>
</vector>
'''

# 5c. Outline Braving Shields icon
shields_outline_xml = '''<?xml version="1.0" encoding="utf-8"?>
<!-- Braving Shields Outline Icon -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
  <path
      android:fillColor="#8E8E93"
      android:pathData="M12,2L4,5.5v5.5c0,5.25 3.4,10.15 8,11.35c4.6,-1.2 8,-6.1 8,-11.35V5.5L12,2zM12,3.9l6.5,2.85v4.25c0,4.25 -2.75,8.2 -6.5,9.25c-3.75,-1.05 -6.5,-5 -6.5,-9.25V6.75L12,3.9z"/>
</vector>
'''

# 5d. Carved Braving Shields icon
shields_carved_xml = '''<?xml version="1.0" encoding="utf-8"?>
<!-- Braving Shields Carved Icon -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
  <path
      android:fillColor="#636366"
      android:pathData="M12,2L4,5.5v5.5c0,5.25 3.4,10.15 8,11.35c4.6,-1.2 8,-6.1 8,-11.35V5.5L12,2z"/>
</vector>
'''

vector_map = {
    'ic_social_brave_release_favicon_fullheight_color.xml': shields_active_xml,
    'ic_social_brave_monochrome_favicon_fullheight_color.xml': shields_monochrome_xml,
    'ic_social_brave_outline_favicon_fullheight.xml': shields_outline_xml,
    'ic_social_brave_carved_favicon_fullheight.xml': shields_carved_xml,
}

for fname, xml_content in vector_map.items():
    with open(os.path.join(shields_drawables_dir, fname), 'w') as f:
        f.write(xml_content)

print(' [OK] Dedicated Braving Shields vector drawables generated in shields_drawables/.')
PYEOF

echo ""
echo "All Android branding assets updated successfully."
