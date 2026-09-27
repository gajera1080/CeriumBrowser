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
        """Dedicated shields drawables must exist and not contain upstream Brave lion path."""
        UPSTREAM_LION_SIG = "M74.68,37.99"
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
        """Launcher mipmap overrides in res_brave_base must be valid <vector> drawables."""
        base_dir = os.path.join(self.android_dir, "res_brave_base")
        expected_vectors = [
            "mipmap-anydpi-v26/app_icon.xml",
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
