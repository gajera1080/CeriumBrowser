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
        """All 10 Android vector logo drawables must exist and preserve exact upstream dp dimensions."""
        ANDROID_NS = "{http://schemas.android.com/apk/res/android}"
        drawable_dir = os.path.join(self.android_dir, "drawable")
        expected_dims = {
            "ic_brave_logo.xml": ("19dp", "23dp"),
            "ic_brave.xml": ("20dp", "20dp"),
            "ic_brave_36.xml": ("37dp", "37dp"),
            "brave_icon_search.xml": ("24dp", "24dp"),
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
        splash_root = ET.parse(os.path.join(drawable_dir, "ic_brave_splash.xml")).getroot()
        groups = [el.attrib.get(f"{ANDROID_NS}name") for el in splash_root.iter("group")]
        self.assertIn("brave_logo", groups, "ic_brave_splash.xml must contain <group android:name='brave_logo'>")

    def test_svg_validity(self):
        """All SVGs in branding/ must be valid XML."""
        svg_files = [f for f in os.listdir(self.branding_dir) if f.endswith(".svg")]
        self.assertGreater(len(svg_files), 0, "No SVG files found in branding/")
        for f in svg_files:
            p = os.path.join(self.branding_dir, f)
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

    def test_aapt2_compile_and_link(self):
        """Deep verification: compile and link all branding drawables with AAPT2 if available."""
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
