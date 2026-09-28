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

BRAVE_RES_VECTORS=(
  "ic_brave_logo.xml"
  "ic_brave.xml"
  "ic_brave_36.xml"
  "brave_icon_search.xml"
  "ic_channel_brave.xml"
  "ic_brave_notification.xml"
)

for vec in "${BRAVE_RES_VECTORS[@]}"; do
  if [[ -f "${REPO_ROOT}/branding/android/drawable/${vec}" ]]; then
    cp -f "${REPO_ROOT}/branding/android/drawable/${vec}" "${BRAVE_DIR}/android/java/brave-res/drawable/${vec}"
    echo " [OK] Copied ${vec} to android/java/brave-res/drawable/"
  fi
done

if [[ -f "${REPO_ROOT}/branding/android/drawable/chrome_logo_on_circular_background.xml" ]]; then
  cp -f "${REPO_ROOT}/branding/android/drawable/chrome_logo_on_circular_background.xml" \
        "${BRAVE_DIR}/android/java/res/drawable/chrome_logo_on_circular_background.xml"
  echo " [OK] Copied chrome_logo_on_circular_background.xml to android/java/res/drawable/"
fi

FIRST_RUN_VECTORS=(
  "ic_brave_splash.xml"
  "ic_brave_brand.xml"
  "onboarding_illustration.xml"
)

for vec in "${FIRST_RUN_VECTORS[@]}"; do
  if [[ -f "${REPO_ROOT}/branding/android/drawable/${vec}" ]]; then
    cp -f "${REPO_ROOT}/branding/android/drawable/${vec}" "${BRAVE_DIR}/browser/first_run/android/java/res/drawable/${vec}"
    echo " [OK] Copied ${vec} to browser/first_run/android/java/res/drawable/"
  fi
done

# 2. Overlay Android adaptive & themed vector icons into app/theme/brave/android/res_brave_base/ (and default/origin variants)
for theme_root in "${BRAVE_DIR}/app/theme/brave/android" "${BRAVE_DIR}/app/theme/brave_origin/android"; do
  if [[ -d "${theme_root}" ]]; then
    for base_sub in "res_brave_base" "res_brave_default_base"; do
      target_base="${theme_root}/${base_sub}"
      if [[ -d "${target_base}" ]]; then
        mkdir -p "${target_base}/drawable" "${target_base}/drawable-night" "${target_base}/mipmap-anydpi-v26" "${target_base}/mipmap-nodpi"
        if [[ -f "${REPO_ROOT}/branding/android/res_brave_base/drawable/themed_app_icon.xml" ]]; then
          cp -f "${REPO_ROOT}/branding/android/res_brave_base/drawable/themed_app_icon.xml" "${target_base}/drawable/themed_app_icon.xml"
        fi
        if [[ -f "${REPO_ROOT}/branding/android/res_brave_base/drawable-night/themed_app_icon.xml" ]]; then
          cp -f "${REPO_ROOT}/branding/android/res_brave_base/drawable-night/themed_app_icon.xml" "${target_base}/drawable-night/themed_app_icon.xml"
        fi
        if [[ -d "${REPO_ROOT}/branding/android/res_brave_base/mipmap-anydpi-v26" ]]; then
          cp -f "${REPO_ROOT}/branding/android/res_brave_base/mipmap-anydpi-v26/"*.xml "${target_base}/mipmap-anydpi-v26/"
        fi
        if [[ -d "${REPO_ROOT}/branding/android/res_brave_base/mipmap-nodpi" ]]; then
          cp -f "${REPO_ROOT}/branding/android/res_brave_base/mipmap-nodpi/"*.xml "${target_base}/mipmap-nodpi/"
        fi
      fi
    done
  fi
done
echo " [OK] Overlaid adaptive app_icon.xml, layered_app_icon.xml, and themed_app_icon.xml into res_brave_base/."

# 3. Overlay Shields toolbar vector drawables into app/theme/brave/android/shields_drawables/
THEME_ANDROID="${BRAVE_DIR}/app/theme/brave/android"
if [[ -d "${THEME_ANDROID}" && -d "${REPO_ROOT}/branding/android/shields_drawables" ]]; then
  mkdir -p "${THEME_ANDROID}/shields_drawables"
  cp -f "${REPO_ROOT}/branding/android/shields_drawables/"*.xml "${THEME_ANDROID}/shields_drawables/"
  if [[ -d "${BRAVE_DIR}/node_modules/@brave/leo/tokens/android/drawable" ]]; then
    cp -f "${REPO_ROOT}/branding/android/shields_drawables/"*.xml "${BRAVE_DIR}/node_modules/@brave/leo/tokens/android/drawable/"
  fi
  echo " [OK] Overlaid Shields vector drawables into app/theme/brave/android/shields_drawables/."
fi

# 4. Generate and overwrite all release-channel raster PNG logos in BRAVE_DIR at exact original pixel dimensions
python3 - "${REPO_ROOT}" "${BRAVE_DIR}" <<'PYEOF'
import os
import re
import sys
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

repo_root, brave_dir = sys.argv[1], sys.argv[2]
svg_path = os.path.join(repo_root, "branding", "logo.svg")

svg_tree = ET.parse(svg_path)
svg_root = svg_tree.getroot()
ns_svg = "{http://www.w3.org/2000/svg}"

def hex_to_rgba(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)

grads = {}
for lg in svg_root.findall(f".//{ns_svg}linearGradient"):
    gid = lg.attrib["id"]
    stops = []
    for st in lg.findall(f"{ns_svg}stop"):
        off_str = st.attrib["offset"].replace("%", "")
        off = float(off_str) / 100.0 if "%" in st.attrib["offset"] else float(off_str)
        stops.append((off, hex_to_rgba(st.attrib["stop-color"])))
    grads[gid] = {
        "x1": float(lg.attrib["x1"]),
        "y1": float(lg.attrib["y1"]),
        "x2": float(lg.attrib["x2"]),
        "y2": float(lg.attrib["y2"]),
        "stops": stops,
    }

def eval_stops(stops, t):
    if t <= stops[0][0]:
        return stops[0][1]
    if t >= stops[-1][0]:
        return stops[-1][1]
    for i in range(len(stops) - 1):
        o0, c0 = stops[i]
        o1, c1 = stops[i + 1]
        if o0 <= t <= o1:
            u = (t - o0) / (o1 - o0) if o1 > o0 else 0.0
            return tuple(int(round(c0[j] + u * (c1[j] - c0[j]))) for j in range(4))
    return stops[-1][1]

def make_grad_image(size, g):
    x1, y1, x2, y2 = g["x1"], g["y1"], g["x2"], g["y2"]
    stops = g["stops"]
    if abs(x2 - x1) < 1e-6:
        strip = Image.new("RGBA", (1, size))
        px = strip.load()
        for y in range(size):
            t = (y - y1) / (y2 - y1)
            px[0, y] = eval_stops(stops, t)
        return strip.resize((size, size), Image.Resampling.NEAREST)
    else:
        strip = Image.new("RGBA", (size, 1))
        px = strip.load()
        for x in range(size):
            t = (x - x1) / (x2 - x1)
            px[x, 0] = eval_stops(stops, t)
        return strip.resize((size, size), Image.Resampling.NEAREST)

def parse_cubic_poly(d):
    tokens = re.findall(r"[MCZ]|[-+]?\d*\.?\d+", d)
    pts = []
    i = 0
    cx, cy = 0.0, 0.0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "M":
            cx, cy = float(tokens[i + 1]), float(tokens[i + 2])
            pts.append((cx, cy))
            i += 3
        elif tok == "C":
            i += 1
            while i < len(tokens) and tokens[i] not in ("M", "C", "Z"):
                x1, y1 = float(tokens[i]), float(tokens[i + 1])
                x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
                x3, y3 = float(tokens[i + 4]), float(tokens[i + 5])
                for s in (0.5, 1.0):
                    mt = 1.0 - s
                    px = mt**3 * cx + 3 * mt**2 * s * x1 + 3 * mt * s**2 * x2 + s**3 * x3
                    py = mt**3 * cy + 3 * mt**2 * s * y1 + 3 * mt * s**2 * y2 + s**3 * y3
                    pts.append((px, py))
                cx, cy = x3, y3
                i += 6
        else:
            i += 1
    return pts

SIZE = 1254
master_color = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
master_white = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
white_solid = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 255))

for p in svg_root.findall(f".//{ns_svg}path"):
    gid = p.attrib["fill"].replace("url(#", "").replace(")", "")
    pts = parse_cubic_poly(p.attrib["d"])
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    grad_im = make_grad_image(SIZE, grads[gid])
    master_color.paste(grad_im, (0, 0), mask)
    master_white.paste(white_solid, (0, 0), mask)

# Create grayscale/off master from master_color
r, g, b, a = master_color.split()
gray_l = master_color.convert("L")
master_gray = Image.merge("RGBA", (gray_l, gray_l, gray_l, a))

# Create adaptive foreground master (scaled to 0.66 safe zone centered in 1254x1254)
fg_scale = 0.66
fg_dim = int(round(SIZE * fg_scale))
fg_resized = master_color.resize((fg_dim, fg_dim), Image.Resampling.LANCZOS)
master_layered_fg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
offset = (SIZE - fg_dim) // 2
master_layered_fg.paste(fg_resized, (offset, offset), fg_resized)

def save_exact(src_master, rel_path, fallback_size):
    full_path = os.path.join(brave_dir, rel_path)
    if os.path.isfile(full_path):
        with Image.open(full_path) as existing:
            w, h = existing.size
    else:
        if fallback_size is None:
            return False
        w, h = fallback_size
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

    if src_master == "SOLID_WHITE":
        out = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    elif w == h:
        out = src_master.resize((w, h), Image.Resampling.LANCZOS)
    else:
        side = min(w, h)
        icon = src_master.resize((side, side), Image.Resampling.LANCZOS)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(icon, ((w - side) // 2, (h - side) // 2), icon)

    out.save(full_path, format="PNG")
    return True

densities_app_icon = {
    "mdpi": (48, 48),
    "hdpi": (72, 72),
    "xhdpi": (96, 96),
    "xxhdpi": (144, 144),
    "xxxhdpi": (192, 192),
}
densities_layered = {
    "mdpi": (108, 108),
    "hdpi": (162, 162),
    "xhdpi": (216, 216),
    "xxhdpi": (324, 324),
    "xxxhdpi": (432, 432),
}
densities_fre = {
    "mdpi": (96, 96),
    "hdpi": (144, 144),
    "xhdpi": (192, 192),
    "xxhdpi": (288, 288),
    "xxxhdpi": (384, 384),
}
densities_btn = {
    "mdpi": (28, 28),
    "hdpi": (42, 42),
    "xhdpi": (56, 56),
    "xxhdpi": (84, 84),
    "xxxhdpi": (112, 112),
}
densities_chrome = {
    "mdpi": (24, 24),
    "hdpi": (36, 36),
    "xhdpi": (48, 48),
    "xxhdpi": (72, 72),
    "xxxhdpi": (96, 96),
}
densities_chrome16 = {
    "mdpi": (16, 16),
    "hdpi": (24, 24),
    "xhdpi": (32, 32),
    "xxhdpi": (48, 48),
    "xxxhdpi": (64, 64),
}

count = 0
for theme_brand in ("brave", "brave_origin"):
    # Legacy mipmap-* app_icon.png
    for d, sz in densities_app_icon.items():
        if save_exact(master_color, f"app/theme/{theme_brand}/android/mipmap-{d}/app_icon.png", sz if theme_brand == "brave" else None):
            count += 1
    # res_brave_base and res_brave_default_base
    for base_name in ("res_brave_base", "res_brave_default_base", "res_brave_dev_base"):
        for d, sz in densities_app_icon.items():
            if save_exact(master_color, f"app/theme/{theme_brand}/android/{base_name}/mipmap-{d}/app_icon.png", None):
                count += 1
        for d, sz in densities_layered.items():
            if save_exact(master_layered_fg, f"app/theme/{theme_brand}/android/{base_name}/mipmap-{d}/layered_app_icon.png", None):
                count += 1
            if save_exact("SOLID_WHITE", f"app/theme/{theme_brand}/android/{base_name}/mipmap-{d}/layered_app_icon_background.png", None):
                count += 1
    # fre_product_logo.png
    for res_name in ("res_brave", "res_brave_default"):
        for d, sz in densities_fre.items():
            if save_exact(master_color, f"app/theme/{theme_brand}/android/{res_name}/drawable-{d}/fre_product_logo.png", None):
                count += 1

# btn_brave.png, btn_brave_off.png, ic_chrome.png, chromelogo16.png
for d in densities_btn:
    if save_exact(master_color, f"android/java/brave-res/drawable-{d}/btn_brave.png", densities_btn[d]):
        count += 1
    if save_exact(master_gray, f"android/java/brave-res/drawable-{d}/btn_brave_off.png", densities_btn[d]):
        count += 1
    if save_exact(master_white, f"android/java/res/drawable-{d}/ic_chrome.png", densities_chrome[d]):
        count += 1
    if save_exact(master_color, f"android/java/res/drawable-{d}/chromelogo16.png", densities_chrome16[d]):
        count += 1

# Theme product_logo_*.png across 100%, 200%, and app/theme/brave/
for scale_dir in ("default_100_percent", "default_200_percent"):
    for theme_brand in ("brave", "brave_origin"):
        base = f"app/theme/{scale_dir}/{theme_brand}"
        for name in ("product_logo_16.png", "product_logo_32.png", "product_logo_name_22.png", "product_logo_name_48.png", "linux/product_logo_16.png", "linux/product_logo_32.png"):
            if save_exact(master_color, f"{base}/{name}", None):
                count += 1
        for name in ("product_logo_name_22_white.png", "product_logo_white.png"):
            if save_exact(master_white, f"{base}/{name}", None):
                count += 1

for name in ("product_logo_24.png", "product_logo_48.png", "product_logo_64.png", "product_logo_128.png", "product_logo_256.png",
             "linux/product_logo_24.png", "linux/product_logo_48.png", "linux/product_logo_64.png", "linux/product_logo_128.png", "linux/product_logo_256.png",
             "win/tiles/Logo.png", "win/tiles/SmallLogo.png"):
    if save_exact(master_color, f"app/theme/brave/{name}", None):
        count += 1
if save_exact(master_white, "app/theme/brave/product_logo_22_mono.png", None):
    count += 1

with open(svg_path, "r", encoding="utf-8") as sf:
    master_svg_text = sf.read()

svg_targets = [
    "app/theme/brave/product_logo.svg",
    "app/theme/brave/password_manager_logo.svg",
    "app/theme/brave/product_logo_animation.svg",
    "app/theme/brave_origin/product_logo.svg",
    "app/theme/brave_origin/password_manager_logo.svg",
    "app/theme/brave_origin/product_logo_animation.svg",
    "components/brave_welcome_ui/components/images/lion_logo.svg",
    "components/brave_welcome_ui/components/images/welcome_shields.svg",
    "components/brave_account/resources/images/full_brave_brand.svg",
    "components/brave_account/resources/images/full_brave_brand_dark.svg",
]
svg_count = 0
for rel_svg in svg_targets:
    target_svg = os.path.join(brave_dir, rel_svg)
    if not os.path.isfile(target_svg):
        continue
    try:
        orig_root = ET.parse(target_svg).getroot()
        orig_w = orig_root.attrib.get("width", "1254")
        orig_h = orig_root.attrib.get("height", "1254")
    except Exception:
        orig_w, orig_h = "1254", "1254"
    customized_svg = re.sub(
        r'<svg\b[^>]*>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{orig_w}" height="{orig_h}" viewBox="0 0 1254 1254">',
        master_svg_text,
        count=1,
    )
    with open(target_svg, "w", encoding="utf-8") as tf:
        tf.write(customized_svg)
    svg_count += 1

print(f" [OK] Generated and replaced {count} raster PNG logos and {svg_count} SVG logos at exact original dimensions.")
PYEOF

# 5. Prevent java_resources failure by removing any misplaced branding folders in brave-res
rm -rf "${BRAVE_DIR}/android/java/brave-res/mipmap-"* \
       "${BRAVE_DIR}/android/java/brave-res/res_brave"* \
       "${BRAVE_DIR}/android/java/brave-res/shields_drawables" 2>/dev/null || true

# 6. Clean up any old rasterized ic_brave_logo.png files in density folders
for density in mdpi hdpi xhdpi xxhdpi xxxhdpi; do
  rm -f "${BRAVE_DIR}/android/java/brave-res/drawable-${density}/ic_brave_logo.png"
done

echo " [OK] Braving vector and raster assets applied cleanly to brave-core."
