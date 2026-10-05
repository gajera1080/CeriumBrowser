#!/usr/bin/env python3
"""
Unit tests for Braving branding assets, verifying XML/SVG validity,
AAPT2 ResStringPool UTF-8 limits (32,767 bytes max per string),
and presence of required de-branded vectors.
"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBrandingAssets(unittest.TestCase):
    def setUp(self):
        self.branding_dir = os.path.join(REPO_ROOT, "branding")
        self.android_dir = os.path.join(self.branding_dir, "android")

    def test_xml_syntax_validity(self):
        """All XML drawables must be well-formed XML."""
        xml_files = []
        for root, _, files in os.walk(self.android_dir):
            for f in files:
                if f.endswith(".xml"):
                    xml_files.append(os.path.join(root, f))

        self.assertGreater(len(xml_files), 0, "No XML drawables found")
        for path in xml_files:
            try:
                ET.parse(path)
            except Exception as e:
                self.fail(f"Invalid XML syntax in {path}: {e}")

    def test_aapt2_string_length_limits(self):
        """
        AAPT2 ResStringPool has a hard UTF-8 limit of 32,767 bytes (0x7fff) per string entry.
        Strings (such as vector pathData) exceeding this cause compile_resources failure.
        """
        MAX_LEN = 32767
        oversized = []

        for root, _, files in os.walk(self.android_dir):
            for f in files:
                if f.endswith(".xml"):
                    p = os.path.join(root, f)
                    try:
                        tree = ET.parse(p)
                        for i, el in enumerate(tree.iter()):
                            for k, v in el.attrib.items():
                                encoded_len = len(v.encode("utf-8"))
                                if encoded_len > MAX_LEN:
                                    attr_name = k.split("}")[-1]
                                    oversized.append(f"{f} element#{i} {attr_name}: {encoded_len} bytes > {MAX_LEN}")
                    except Exception as e:
                        self.fail(f"Error reading {p}: {e}")

        self.assertEqual(oversized, [], f"Found attributes exceeding AAPT2 string length limit:\n" + "\n".join(oversized))

    def test_shields_drawables_exist_and_debranded(self):
        """Dedicated shields drawables must exist, be 24dp x 24dp, use colored ON icon, and not contain upstream Brave lion path."""
        UPSTREAM_LION_SIG = "M74.68,37.99"
        ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
        shields_dir = os.path.join(self.android_dir, "shields_drawables")
        required = [
            "ic_social_brave_release_favicon_fullheight_color.xml",
            "ic_social_brave_monochrome_favicon_fullheight_color.xml",
            "ic_social_brave_outline_favicon_fullheight.xml",
            "ic_social_brave_carved_favicon_fullheight.xml",
        ]
        for name in required:
            path = os.path.join(shields_dir, name)
            self.assertTrue(os.path.isfile(path), f"Missing {name}")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn(UPSTREAM_LION_SIG, content, f"{name} contains upstream lion signature")
            root = ET.parse(path).getroot()
            self.assertEqual(root.attrib.get(f"{ANDROID_NS}width"), "24dp", f"{name} width must be 24dp")
            self.assertEqual(root.attrib.get(f"{ANDROID_NS}height"), "24dp", f"{name} height must be 24dp")

        # Verify ON shields icon uses the 4 colored Braving gradients instead of flat white
        on_path = os.path.join(shields_dir, "ic_social_brave_release_favicon_fullheight_color.xml")
        with open(on_path, "r", encoding="utf-8") as f:
            on_content = f.read()
        self.assertNotIn('fillColor="#ffffff"', on_content.lower())
        for grad_color in ("#fffd8c57", "#ff0091e6", "#fffce01f", "#ff8bd01d"):
            self.assertIn(grad_color, on_content.lower(), f"Missing gradient color {grad_color} in ON shields icon")

        # Verify OFF/monochrome/carved shields icons use the 4 grayscale Braving ribbon paths (not invisible white stroke)
        for off_name in (
            "ic_social_brave_monochrome_favicon_fullheight_color.xml",
            "ic_social_brave_outline_favicon_fullheight.xml",
            "ic_social_brave_carved_favicon_fullheight.xml",
        ):
            off_path = os.path.join(shields_dir, off_name)
            with open(off_path, "r", encoding="utf-8") as f:
                off_content = f.read()
            self.assertNotIn('strokecolor="#ffffff"', off_content.lower(), f"{off_name} must not use white stroke")
            self.assertEqual(off_content.count("<path"), 4, f"{off_name} must contain the 4 Braving ribbon paths")

    def test_all_vector_logo_drawables_exact_dimensions(self):
        """All 9 Android vector logo drawables must exist and preserve exact upstream dp dimensions."""
        ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
        drawable_dir = os.path.join(self.android_dir, "drawable")
        expected_dims = {
            "ic_brave_logo.xml": ("19dp", "23dp"),
            "ic_brave.xml": ("20dp", "20dp"),
            "ic_brave_36.xml": ("37dp", "37dp"),
            "ic_channel_brave.xml": ("20dp", "20dp"),
            "ic_brave_notification.xml": ("39dp", "50dp"),
            "chrome_logo_on_circular_background.xml": ("31dp", "31dp"),
            "ic_brave_splash.xml": ("288dp", "288dp"),
            "ic_brave_brand.xml": ("168dp", "52dp"),
            "onboarding_illustration.xml": ("302dp", "302dp"),
        }
        for name, (exp_w, exp_h) in expected_dims.items():
            path = os.path.join(drawable_dir, name)
            self.assertTrue(os.path.isfile(path), f"Missing vector logo drawable {name}")
            root = ET.parse(path).getroot()
            self.assertEqual(root.tag, "vector", f"{name} must be a <vector>")
            self.assertEqual(root.attrib.get(f"{ANDROID_NS}width"), exp_w, f"{name} width mismatch")
            self.assertEqual(root.attrib.get(f"{ANDROID_NS}height"), exp_h, f"{name} height mismatch")
            if name == "ic_brave_logo.xml":
                self.assertEqual(root.attrib.get(f"{ANDROID_NS}viewportWidth"), "19")
                self.assertEqual(root.attrib.get(f"{ANDROID_NS}viewportHeight"), "23")

        # Verify ic_brave_splash.xml preserves the <group android:name="brave_logo"> animator target
        # and suppresses Android Lint VectorRaster (>200dp)
        TOOLS_NS = "{http://schemas.android.com/tools}"
        splash_root = ET.parse(os.path.join(drawable_dir, "ic_brave_splash.xml")).getroot()
        groups = [el.attrib.get(f"{ANDROID_NS}name") for el in splash_root.iter("group")]
        self.assertIn("brave_logo", groups, "ic_brave_splash.xml must contain <group android:name='brave_logo'>")
        self.assertIn(
            "VectorRaster",
            splash_root.attrib.get(f"{TOOLS_NS}ignore", ""),
            "ic_brave_splash.xml (>200dp) must include tools:ignore='VectorRaster' for Android Lint",
        )

        onboard_root = ET.parse(os.path.join(drawable_dir, "onboarding_illustration.xml")).getroot()
        self.assertIn(
            "VectorRaster",
            onboard_root.attrib.get(f"{TOOLS_NS}ignore", ""),
            "onboarding_illustration.xml (>200dp) must include tools:ignore='VectorRaster' for Android Lint",
        )

        # Verify ic_brave_brand.xml references @color/brave_brand_text_color so Android Lint UnusedResources passes
        with open(os.path.join(drawable_dir, "ic_brave_brand.xml"), "r", encoding="utf-8") as f:
            brand_xml = f.read()
        self.assertIn(
            "@color/brave_brand_text_color",
            brand_xml,
            "ic_brave_brand.xml must reference @color/brave_brand_text_color to avoid Android Lint UnusedResources",
        )

    def test_svg_validity(self):
        """All SVGs in branding/ (including static brave-core-static SVGs) must be valid XML."""
        svg_files = []
        for root, _, files in os.walk(self.branding_dir):
            for f in files:
                if f.endswith(".svg"):
                    svg_files.append(os.path.join(root, f))
        self.assertEqual(len(svg_files), 15, f"Expected 15 SVG files in branding/, found {len(svg_files)}")
        for p in svg_files:
            try:
                ET.parse(p)
            except Exception as e:
                self.fail(f"Invalid SVG XML syntax in {p}: {e}")

    def test_launcher_mipmap_vectors(self):
        """Launcher mipmap overrides in res_brave_base must have adaptive-icon container and valid <vector> layers."""
        base_dir = os.path.join(self.android_dir, "res_brave_base")
        app_icon_path = os.path.join(base_dir, "mipmap-anydpi-v26/app_icon.xml")
        self.assertTrue(os.path.isfile(app_icon_path), "Missing mipmap-anydpi-v26/app_icon.xml")
        app_icon_root = ET.parse(app_icon_path).getroot()
        self.assertEqual(app_icon_root.tag, "adaptive-icon", "app_icon.xml must be an <adaptive-icon> container")

        expected_vectors = [
            "mipmap-anydpi-v26/layered_app_icon.xml",
            "mipmap-anydpi-v26/layered_app_icon_background.xml",
            "mipmap-nodpi/layered_app_icon_foreground.xml",
        ]
        for rel_path in expected_vectors:
            full_path = os.path.join(base_dir, rel_path)
            self.assertTrue(os.path.isfile(full_path), f"Missing launcher vector {rel_path}")
            root = ET.parse(full_path).getroot()
            self.assertEqual(root.tag, "vector", f"{rel_path} must be a <vector> drawable, got <{root.tag}>")

    def test_static_logos_exist_and_exact_dimensions(self):
        """All 156 static PNGs and 10 static SVGs in branding/brave-core-static/ must exist and match exact expected dimensions."""
        import struct

        static_dir = os.path.join(self.branding_dir, "brave-core-static")
        self.assertTrue(os.path.isdir(static_dir), f"Missing {static_dir}")

        densities_app_brave = {"mdpi": (48, 48), "hdpi": (72, 72), "xhdpi": (96, 96), "xxhdpi": (144, 144), "xxxhdpi": (192, 192)}
        densities_app_origin = {"mdpi": (72, 72), "hdpi": (48, 48), "xhdpi": (96, 96), "xxhdpi": (144, 144), "xxxhdpi": (192, 192)}
        densities_layered = {"mdpi": (108, 108), "hdpi": (162, 162), "xhdpi": (216, 216), "xxhdpi": (324, 324), "xxxhdpi": (432, 432)}
        densities_fre = {"mdpi": (96, 96), "hdpi": (144, 144), "xhdpi": (192, 192), "xxhdpi": (288, 288), "xxxhdpi": (384, 384)}
        densities_btn = {"mdpi": (28, 28), "hdpi": (42, 42), "xhdpi": (56, 56), "xxhdpi": (84, 84), "xxxhdpi": (112, 112)}
        densities_chrome = {"mdpi": (24, 24), "hdpi": (36, 36), "xhdpi": (48, 48), "xxhdpi": (72, 72), "xxxhdpi": (96, 96)}
        densities_chrome16 = {"mdpi": (16, 16), "hdpi": (24, 24), "xhdpi": (32, 32), "xxhdpi": (48, 48), "xxxhdpi": (64, 64)}

        expected_pngs = {}
        for theme_brand, d_app in (("brave", densities_app_brave), ("brave_origin", densities_app_origin)):
            for d, sz in d_app.items():
                expected_pngs[f"app/theme/{theme_brand}/android/mipmap-{d}/app_icon.png"] = sz
            for base_name in ("res_brave_base", "res_brave_default_base"):
                for d, sz in d_app.items():
                    expected_pngs[f"app/theme/{theme_brand}/android/{base_name}/mipmap-{d}/app_icon.png"] = sz
                for d, sz in densities_layered.items():
                    expected_pngs[f"app/theme/{theme_brand}/android/{base_name}/mipmap-{d}/layered_app_icon.png"] = sz
                    expected_pngs[f"app/theme/{theme_brand}/android/{base_name}/mipmap-{d}/layered_app_icon_background.png"] = sz
            for res_name in ("res_brave", "res_brave_default"):
                for d, sz in densities_fre.items():
                    expected_pngs[f"app/theme/{theme_brand}/android/{res_name}/drawable-{d}/fre_product_logo.png"] = sz

        for d, sz in densities_app_brave.items():
            expected_pngs[f"app/theme/brave/android/res_brave_dev_base/mipmap-{d}/app_icon.png"] = sz

        for d in densities_btn:
            expected_pngs[f"android/java/brave-res/drawable-{d}/btn_brave.png"] = densities_btn[d]
            expected_pngs[f"android/java/brave-res/drawable-{d}/btn_brave_off.png"] = densities_btn[d]
            expected_pngs[f"android/java/res/drawable-{d}/ic_chrome.png"] = densities_chrome[d]
            expected_pngs[f"android/java/res/drawable-{d}/chromelogo16.png"] = densities_chrome16[d]

        expected_pngs.update({
            "app/theme/default_100_percent/brave/linux/product_logo_16.png": (16, 16),
            "app/theme/default_100_percent/brave/linux/product_logo_32.png": (32, 32),
            "app/theme/default_100_percent/brave/product_logo_16.png": (16, 16),
            "app/theme/default_100_percent/brave/product_logo_32.png": (32, 32),
            "app/theme/default_100_percent/brave/product_logo_name_22.png": (70, 22),
            "app/theme/default_100_percent/brave/product_logo_name_22_white.png": (70, 22),
            "app/theme/default_100_percent/brave/product_logo_name_48.png": (154, 48),
            "app/theme/default_100_percent/brave/product_logo_white.png": (184, 58),
            "app/theme/default_100_percent/brave_origin/linux/product_logo_16.png": (16, 16),
            "app/theme/default_100_percent/brave_origin/linux/product_logo_32.png": (32, 32),
            "app/theme/default_100_percent/brave_origin/product_logo_16.png": (16, 16),
            "app/theme/default_100_percent/brave_origin/product_logo_32.png": (32, 32),
            "app/theme/default_100_percent/brave_origin/product_logo_name_22.png": (71, 22),
            "app/theme/default_100_percent/brave_origin/product_logo_name_22_white.png": (63, 20),
            "app/theme/default_100_percent/brave_origin/product_logo_name_48.png": (155, 48),
            "app/theme/default_100_percent/brave_origin/product_logo_white.png": (184, 57),
            "app/theme/default_200_percent/brave/product_logo_16.png": (32, 32),
            "app/theme/default_200_percent/brave/product_logo_32.png": (64, 64),
            "app/theme/default_200_percent/brave/product_logo_name_22.png": (142, 44),
            "app/theme/default_200_percent/brave/product_logo_name_22_white.png": (126, 39),
            "app/theme/default_200_percent/brave/product_logo_name_48.png": (309, 96),
            "app/theme/default_200_percent/brave/product_logo_white.png": (368, 114),
            "app/theme/default_200_percent/brave_origin/product_logo_16.png": (32, 32),
            "app/theme/default_200_percent/brave_origin/product_logo_32.png": (64, 64),
            "app/theme/default_200_percent/brave_origin/product_logo_name_22.png": (142, 44),
            "app/theme/default_200_percent/brave_origin/product_logo_name_22_white.png": (126, 39),
            "app/theme/default_200_percent/brave_origin/product_logo_name_48.png": (309, 96),
            "app/theme/default_200_percent/brave_origin/product_logo_white.png": (368, 114),
            "app/theme/brave/product_logo_24.png": (24, 24),
            "app/theme/brave/product_logo_48.png": (48, 48),
            "app/theme/brave/product_logo_64.png": (64, 64),
            "app/theme/brave/product_logo_128.png": (128, 128),
            "app/theme/brave/product_logo_256.png": (256, 256),
            "app/theme/brave/linux/product_logo_24.png": (24, 24),
            "app/theme/brave/linux/product_logo_48.png": (48, 48),
            "app/theme/brave/linux/product_logo_64.png": (64, 64),
            "app/theme/brave/linux/product_logo_128.png": (128, 128),
            "app/theme/brave/linux/product_logo_256.png": (256, 256),
            "app/theme/brave/win/tiles/Logo.png": (600, 600),
            "app/theme/brave/win/tiles/SmallLogo.png": (176, 176),
            "app/theme/brave/product_logo_22_mono.png": (22, 22),
        })

        self.assertEqual(len(expected_pngs), 156)
        for rel_path, exp_sz in expected_pngs.items():
            full_path = os.path.join(static_dir, rel_path)
            self.assertTrue(os.path.isfile(full_path), f"Missing static PNG: {rel_path}")
            self.assertGreater(os.path.getsize(full_path), 36, f"Empty/truncated static PNG: {rel_path}")
            with open(full_path, "rb") as fp:
                data = fp.read()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", f"Invalid PNG magic header in {rel_path}")
            self.assertEqual(data[12:16], b"IHDR", f"Missing PNG IHDR chunk in {rel_path}")
            self.assertTrue(data.endswith(b"IEND\xaeB`\x82"), f"Missing PNG IEND trailer in {rel_path}")
            w, h = struct.unpack(">II", data[16:24])
            self.assertEqual((w, h), exp_sz, f"Dimension mismatch for {rel_path}: got {(w, h)}, expected {exp_sz}")

        expected_svgs = {
            "app/theme/brave/product_logo.svg": ("256", "256"),
            "app/theme/brave/password_manager_logo.svg": ("180", "186"),
            "app/theme/brave/product_logo_animation.svg": ("256", "256"),
            "app/theme/brave_origin/product_logo.svg": ("1024", "1024"),
            "app/theme/brave_origin/password_manager_logo.svg": ("180", "186"),
            "app/theme/brave_origin/product_logo_animation.svg": ("1024", "1024"),
            "components/brave_welcome_ui/components/images/lion_logo.svg": ("100", "129"),
            "components/brave_welcome_ui/components/images/welcome_shields.svg": ("394px", "233px"),
            "components/brave_account/resources/images/full_brave_brand.svg": ("129", "40"),
            "components/brave_account/resources/images/full_brave_brand_dark.svg": ("129", "40"),
        }
        self.assertEqual(len(expected_svgs), 10)
        for rel_svg, (exp_w, exp_h) in expected_svgs.items():
            full_svg = os.path.join(static_dir, rel_svg)
            self.assertTrue(os.path.isfile(full_svg), f"Missing static SVG: {rel_svg}")
            root = ET.parse(full_svg).getroot()
            self.assertEqual(root.attrib.get("width"), exp_w, f"{rel_svg} width mismatch")
            self.assertEqual(root.attrib.get("height"), exp_h, f"{rel_svg} height mismatch")
            self.assertEqual(root.attrib.get("viewBox"), "0 0 1254 1254", f"{rel_svg} viewBox mismatch")

        # Verify no extra/stray files exist in branding/brave-core-static/
        actual_files = set()
        for root_dir, _, files in os.walk(static_dir):
            for f in files:
                actual_files.add(os.path.relpath(os.path.join(root_dir, f), static_dir).replace("\\", "/"))
        expected_all = set(expected_pngs.keys()) | set(expected_svgs.keys())
        self.assertEqual(actual_files, expected_all, f"Stray or missing files in brave-core-static: {actual_files ^ expected_all}")

    def test_apply_assets_copies_static_files_without_dynamic_generation(self):
        """apply-assets.sh must copy all static XML, PNG, and SVG files cleanly without dynamic rendering."""
        import subprocess
        import tempfile

        apply_script = os.path.join(REPO_ROOT, "scripts/android/apply-assets.sh")
        with open(apply_script, "r", encoding="utf-8") as f:
            script_content = f.read()
        self.assertNotIn("rsvg-convert", script_content, "apply-assets.sh must not use rsvg-convert")
        self.assertNotIn("from PIL", script_content, "apply-assets.sh must not import PIL")
        self.assertNotIn("ImageDraw", script_content, "apply-assets.sh must not use ImageDraw")

        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(["bash", apply_script, tmpdir], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"apply-assets.sh failed: {res.stderr}\n{res.stdout}")

            copied_pngs = []
            copied_svgs = []
            copied_xmls = []
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    full_p = os.path.join(root, f)
                    self.assertGreater(os.path.getsize(full_p), 0, f"Copied empty file: {full_p}")
                    if f.endswith(".png"):
                        copied_pngs.append(full_p)
                    elif f.endswith(".svg"):
                        copied_svgs.append(full_p)
                    elif f.endswith(".xml"):
                        copied_xmls.append(full_p)

            self.assertEqual(len(copied_pngs), 156, f"Expected 156 copied PNGs, found {len(copied_pngs)}")
            self.assertEqual(len(copied_svgs), 10, f"Expected 10 copied SVGs, found {len(copied_svgs)}")
            self.assertEqual(len(copied_xmls), 37, f"Expected 37 copied XMLs, found {len(copied_xmls)}")

    def test_apply_assets_modern_build_gn_skips_and_cleans_unlisted_drawables(self):
        """On modern versions where android/BUILD.gn does not track btn_brave or obsolete drawables, apply-assets.sh must not copy or leave unlisted drawables."""
        import subprocess
        import tempfile

        apply_script = os.path.join(REPO_ROOT, "scripts/android/apply-assets.sh")
        with tempfile.TemporaryDirectory() as tmpdir:
            android_dir = os.path.join(tmpdir, "android")
            os.makedirs(android_dir, exist_ok=True)
            build_gn = os.path.join(android_dir, "BUILD.gn")
            with open(build_gn, "w", encoding="utf-8") as f:
                f.write('android_resources("java_resources") {\n  sources = [ "java/brave-res/drawable/ic_brave_logo.xml" ]\n}\n')

            # Pre-seed stale drawables to verify cleanup
            stale_dir = os.path.join(tmpdir, "android/java/brave-res/drawable-hdpi")
            os.makedirs(stale_dir, exist_ok=True)
            stale_btn = os.path.join(stale_dir, "btn_brave.png")
            stale_custom = os.path.join(stale_dir, "unlisted_stale.png")
            with open(stale_btn, "wb") as f:
                f.write(b"stale")
            with open(stale_custom, "wb") as f:
                f.write(b"stale_custom")

            res = subprocess.run(["bash", apply_script, tmpdir], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"apply-assets.sh failed: {res.stderr}\n{res.stdout}")

            copied_pngs = []
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith(".png"):
                        copied_pngs.append(os.path.join(root, f))
                    self.assertNotIn("btn_brave", f, f"btn_brave file must not exist on modern builds: {f}")

            self.assertEqual(len(copied_pngs), 146, f"Expected 146 copied PNGs on modern build, found {len(copied_pngs)}")
            self.assertFalse(os.path.exists(stale_btn), "Stale btn_brave.png was not cleaned up")
            self.assertFalse(os.path.exists(stale_custom), "Stale unlisted_stale.png was not cleaned up")

    def test_apply_assets_legacy_build_gn_includes_tracked_drawables(self):
        """On legacy versions where android/BUILD.gn lists all 10 btn_brave drawables, apply-assets.sh must copy all 156 PNGs."""
        import subprocess
        import tempfile

        apply_script = os.path.join(REPO_ROOT, "scripts/android/apply-assets.sh")
        densities = ["hdpi", "mdpi", "xhdpi", "xxhdpi", "xxxhdpi"]
        legacy_sources = []
        for d in densities:
            legacy_sources.append(f'    "java/brave-res/drawable-{d}/btn_brave.png",')
            legacy_sources.append(f'    "java/brave-res/drawable-{d}/btn_brave_off.png",')
        sources_str = "\n".join(legacy_sources)

        with tempfile.TemporaryDirectory() as tmpdir:
            android_dir = os.path.join(tmpdir, "android")
            os.makedirs(android_dir, exist_ok=True)
            build_gn = os.path.join(android_dir, "BUILD.gn")
            with open(build_gn, "w", encoding="utf-8") as f:
                f.write(f'android_resources("java_resources") {{\n  sources = [\n{sources_str}\n  ]\n}}\n')

            res = subprocess.run(["bash", apply_script, tmpdir], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"apply-assets.sh failed: {res.stderr}\n{res.stdout}")

            copied_pngs = [os.path.join(root, f) for root, _, files in os.walk(tmpdir) for f in files if f.endswith(".png")]
            self.assertEqual(len(copied_pngs), 156, f"Expected 156 copied PNGs on legacy build, found {len(copied_pngs)}")
            btn_brave_hdpi = os.path.join(tmpdir, "android/java/brave-res/drawable-hdpi/btn_brave.png")
            self.assertTrue(os.path.isfile(btn_brave_hdpi), "btn_brave.png was not copied on legacy build")

    def test_apply_assets_selective_build_gn_tracks_individual_drawables(self):
        """When android/BUILD.gn only tracks a specific drawable, only that exact drawable is copied."""
        import subprocess
        import tempfile

        apply_script = os.path.join(REPO_ROOT, "scripts/android/apply-assets.sh")
        with tempfile.TemporaryDirectory() as tmpdir:
            android_dir = os.path.join(tmpdir, "android")
            os.makedirs(android_dir, exist_ok=True)
            build_gn = os.path.join(android_dir, "BUILD.gn")
            with open(build_gn, "w", encoding="utf-8") as f:
                f.write('android_resources("java_resources") {\n  sources = [ "java/brave-res/drawable-hdpi/btn_brave.png" ]\n}\n')

            res = subprocess.run(["bash", apply_script, tmpdir], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"apply-assets.sh failed: {res.stderr}\n{res.stdout}")

            copied_pngs = [os.path.join(root, f) for root, _, files in os.walk(tmpdir) for f in files if f.endswith(".png")]
            self.assertEqual(len(copied_pngs), 147, f"Expected 147 copied PNGs (146 base + 1 selective), found {len(copied_pngs)}")
            self.assertTrue(os.path.isfile(os.path.join(tmpdir, "android/java/brave-res/drawable-hdpi/btn_brave.png")))
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "android/java/brave-res/drawable-hdpi/btn_brave_off.png")))
            self.assertFalse(os.path.exists(os.path.join(tmpdir, "android/java/brave-res/drawable-mdpi/btn_brave.png")))

    def test_aapt2_compile_and_link(self):
        """Deep verification: compile and link all branding XML and Android PNG drawables with AAPT2 if available."""
        import glob
        import shutil
        import subprocess
        import tempfile

        aapt2_candidates = [
            "/home/pc/Android/Sdk/build-tools/34.0.0/aapt2",
            shutil.which("aapt2"),
        ] + glob.glob(os.path.join(REPO_ROOT, "build-workspace/src/third_party/android_build_tools/aapt2/*/aapt2"))

        aapt2_bin = next((c for c in aapt2_candidates if c and os.path.isfile(c) and os.access(c, os.X_OK)), None)
        if not aapt2_bin:
            self.skipTest("aapt2 binary not available in environment")

        jar_candidates = glob.glob("/home/pc/Android/Sdk/platforms/*/android.jar") + \
                         glob.glob(os.path.join(REPO_ROOT, "build-workspace/src/third_party/android_sdk/public/platforms/*/android.jar"))
        android_jar = next((j for j in jar_candidates if os.path.isfile(j)), None)
        if not android_jar:
            self.skipTest("android.jar not available in environment")

        with tempfile.TemporaryDirectory() as tmpdir:
            res_base = os.path.join(tmpdir, "res")
            for root, _, files in os.walk(self.android_dir):
                for f in files:
                    if f.endswith(".xml"):
                        parent_folder = os.path.basename(root)
                        if not parent_folder.startswith(("drawable", "mipmap", "values")):
                            parent_folder = "drawable"
                        target_dir = os.path.join(res_base, parent_folder)
                        os.makedirs(target_dir, exist_ok=True)
                        shutil.copy(os.path.join(root, f), os.path.join(target_dir, f))

            # Also copy Android density raster PNGs from branding/brave-core-static/ to verify AAPT2 PNG compilation
            static_dir = os.path.join(self.branding_dir, "brave-core-static")
            android_png_roots = [
                os.path.join(static_dir, "android/java/brave-res"),
                os.path.join(static_dir, "android/java/res"),
                os.path.join(static_dir, "app/theme/brave/android/res_brave"),
                os.path.join(static_dir, "app/theme/brave/android/res_brave_base"),
            ]
            for png_root in android_png_roots:
                for root, _, files in os.walk(png_root):
                    for f in files:
                        if f.endswith(".png"):
                            parent_folder = os.path.basename(root)
                            target_dir = os.path.join(res_base, parent_folder)
                            os.makedirs(target_dir, exist_ok=True)
                            shutil.copy(os.path.join(root, f), os.path.join(target_dir, f))

            values_dir = os.path.join(res_base, "values")
            os.makedirs(values_dir, exist_ok=True)
            with open(os.path.join(values_dir, "colors.xml"), "w", encoding="utf-8") as cf:
                cf.write(
                    '<?xml version="1.0" encoding="utf-8"?>\n'
                    "<resources>\n"
                    '    <color name="brave_brand_text_color">#1C1C1D</color>\n'
                    '    <color name="shield_text_color">#212529</color>\n'
                    "</resources>\n"
                )

            compiled_dir = os.path.join(tmpdir, "compiled")
            os.makedirs(compiled_dir, exist_ok=True)
            compile_res = subprocess.run(
                [aapt2_bin, "compile", "--dir", res_base, "-o", compiled_dir],
                capture_output=True, text=True
            )
            self.assertEqual(compile_res.returncode, 0, f"AAPT2 compile failed: {compile_res.stderr}")

            manifest = os.path.join(tmpdir, "AndroidManifest.xml")
            with open(manifest, "w", encoding="utf-8") as mf:
                mf.write('<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.braving.browser" />\n')

            flats = [os.path.join(compiled_dir, f) for f in os.listdir(compiled_dir) if f.endswith(".flat")]
            link_res = subprocess.run(
                [aapt2_bin, "link", "-I", android_jar, "--manifest", manifest, "--min-sdk-version", "29", "-o",
                 os.path.join(tmpdir, "out.apk"), "--auto-add-overlay", "--no-version-vectors", "--no-xml-namespaces"] + flats,
                capture_output=True, text=True
            )
            self.assertEqual(link_res.returncode, 0, f"AAPT2 link failed: {link_res.stderr}")
            self.assertNotIn("STRING_TOO_LARGE", link_res.stderr, "AAPT2 reported STRING_TOO_LARGE error on stderr")
            self.assertNotIn("error:", link_res.stderr, f"AAPT2 link wrote errors to stderr: {link_res.stderr}")

if __name__ == "__main__":
    unittest.main()
