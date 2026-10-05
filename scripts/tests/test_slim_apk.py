#!/usr/bin/env python3
# Copyright (c) 2026 The Braving Contributors. All rights reserved.
# Use of this source code is governed by the Mozilla Public License 2.0.

import os
import sys
import tempfile
import unittest
import zipfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts/android"))

import slim_apk


class TestSlimApk(unittest.TestCase):
    def test_parse_locale_from_path(self):
        # Fallback locale
        is_loc, lang, is_fallback = slim_apk.parse_locale_from_path("assets/fallback-locales/en-US.pak")
        self.assertTrue(is_loc)
        self.assertEqual(lang, "en-US")
        self.assertTrue(is_fallback)

        # Bundletool universal path format
        is_loc, lang, is_fallback = slim_apk.parse_locale_from_path("assets/locales#lang_fr/fr.pak")
        self.assertTrue(is_loc)
        self.assertEqual(lang, "fr")
        self.assertFalse(is_fallback)

        is_loc, lang, is_fallback = slim_apk.parse_locale_from_path("assets/locales#lang_es-419/es-419.pak")
        self.assertTrue(is_loc)
        self.assertEqual(lang, "es-419")
        self.assertFalse(is_fallback)

        # Standard APK path format
        is_loc, lang, is_fallback = slim_apk.parse_locale_from_path("assets/locales/de.pak")
        self.assertTrue(is_loc)
        self.assertEqual(lang, "de")
        self.assertFalse(is_fallback)

        # Non-locale assets
        is_loc, lang, is_fallback = slim_apk.parse_locale_from_path("assets/brave_resources.pak")
        self.assertFalse(is_loc)
        self.assertIsNone(lang)

        is_loc, lang, is_fallback = slim_apk.parse_locale_from_path("lib/arm64-v8a/libchrome.so")
        self.assertFalse(is_loc)

        is_loc, lang, is_fallback = slim_apk.parse_locale_from_path("AndroidManifest.xml")
        self.assertFalse(is_loc)

    def test_slim_apk_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_apk = os.path.join(tmpdir, "mock_input.apk")
            out_apk = os.path.join(tmpdir, "mock_output.apk")

            # Create mock APK with various files
            files_to_add = {
                "AndroidManifest.xml": b"<manifest></manifest>",
                "classes.dex": b"DEX DATA",
                "lib/arm64-v8a/libchrome.so": b"ELF NATIVE CODE",
                "assets/icudtl.dat": b"ICU DATA",
                "assets/fallback-locales/en-US.pak": b"FALLBACK EN",
                "assets/locales#lang_en-US/en-US.pak": b"LOCALE EN-US",
                "assets/locales#lang_es/es.pak": b"LOCALE ES",
                "assets/locales#lang_fr/fr.pak": b"LOCALE FR",
                "assets/locales#lang_af/af.pak": b"LOCALE AF",  # Should be pruned
                "assets/locales#lang_zu/zu.pak": b"LOCALE ZU",  # Should be pruned
                "assets/locales#lang_am/am.pak": b"LOCALE AM",  # Should be pruned
            }

            with zipfile.ZipFile(in_apk, "w") as z:
                for path, data in files_to_add.items():
                    z.writestr(path, data)

            keep = {"en-US", "es", "fr"}
            saved = slim_apk.slim_apk(in_apk, out_apk, keep_locales=keep, prune_locales=True)
            self.assertGreater(saved, 0)
            self.assertTrue(os.path.isfile(out_apk))

            with zipfile.ZipFile(out_apk, "r") as z:
                names = set(z.namelist())
                # Base files preserved
                self.assertIn("AndroidManifest.xml", names)
                self.assertIn("classes.dex", names)
                self.assertIn("lib/arm64-v8a/libchrome.so", names)
                self.assertIn("assets/icudtl.dat", names)
                self.assertIn("assets/fallback-locales/en-US.pak", names)
                # Kept locales preserved
                self.assertIn("assets/locales#lang_en-US/en-US.pak", names)
                self.assertIn("assets/locales#lang_es/es.pak", names)
                self.assertIn("assets/locales#lang_fr/fr.pak", names)
                # Pruned locales removed
                self.assertNotIn("assets/locales#lang_af/af.pak", names)
                self.assertNotIn("assets/locales#lang_zu/zu.pak", names)
                self.assertNotIn("assets/locales#lang_am/am.pak", names)

    def test_no_prune_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            in_apk = os.path.join(tmpdir, "mock_input.apk")
            out_apk = os.path.join(tmpdir, "mock_output.apk")

            files_to_add = {
                "AndroidManifest.xml": b"<manifest></manifest>",
                "assets/locales#lang_af/af.pak": b"LOCALE AF",
            }

            with zipfile.ZipFile(in_apk, "w") as z:
                for path, data in files_to_add.items():
                    z.writestr(path, data)

            slim_apk.slim_apk(in_apk, out_apk, prune_locales=False)
            with zipfile.ZipFile(out_apk, "r") as z:
                names = set(z.namelist())
                self.assertIn("assets/locales#lang_af/af.pak", names)


if __name__ == "__main__":
    unittest.main()
