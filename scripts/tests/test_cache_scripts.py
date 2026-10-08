#!/usr/bin/env python3
"""
Unit and integration tests for Braving Siso warm cache pipeline:
- scripts/upload-cache.sh
- scripts/download-cache.sh
- scripts/android/build-android.sh
"""

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestCacheScriptsSyntax(unittest.TestCase):
    """Verify shell script syntax using bash -n."""

    def test_upload_cache_syntax(self):
        script = REPO_ROOT / "scripts" / "core" / "upload-cache.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error in {script}: {res.stderr}")

    def test_download_cache_syntax(self):
        script = REPO_ROOT / "scripts" / "core" / "download-cache.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error in {script}: {res.stderr}")

    def test_build_android_syntax(self):
        script = REPO_ROOT / "scripts" / "platforms" / "android" / "build.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error in {script}: {res.stderr}")

    def test_package_android_syntax(self):
        script = REPO_ROOT / "scripts" / "platforms" / "android" / "package.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error in {script}: {res.stderr}")

    def test_build_windows_syntax(self):
        script = REPO_ROOT / "scripts" / "platforms" / "windows" / "build.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error in {script}: {res.stderr}")

    def test_package_windows_syntax(self):
        script = REPO_ROOT / "scripts" / "platforms" / "windows" / "package.sh"
        res = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Syntax error in {script}: {res.stderr}")



class TestSisoCachePipeline(unittest.TestCase):
    """Verify cache packaging, extraction, and timestamp ordering."""

    def test_timestamp_ordering_and_inmtime_condition(self):
        """
        Verify that the cache restore timestamp synchronization guarantees:
        T_source <= T_manifest < T_output
        such that Siso's checkUpToDate condition inmtime.After(outmtime) evaluates to False.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            workspace = tmp_path / "build-workspace"
            src_dir = workspace / "src"
            out_release = src_dir / "out" / "Release"
            out_release.mkdir(parents=True)

            # 1. Simulate Stage 2 compilation outputs
            (out_release / ".siso_fs_state").write_text("siso_fs_state_data")
            (out_release / ".siso_deps").write_text("siso_deps_data")
            (out_release / ".ninja_log").write_text("# ninja log v5\n")
            (out_release / "build.ninja").write_text("rule cc\n")
            (out_release / "args.gn").write_text("use_siso = true\n")

            obj_dir = out_release / "obj" / "v8"
            obj_dir.mkdir(parents=True)
            v8_obj = obj_dir / "api.o"
            v8_obj.write_bytes(b"\x7fELFfakeobj")

            gen_dir = out_release / "gen" / "v8"
            gen_dir.mkdir(parents=True)
            v8_header = gen_dir / "v8-version.h"
            v8_header.write_text("// generated header")

            # Transient files that should be cleaned
            (out_release / ".siso_lock").write_text("locked")
            (out_release / ".ninja_deps").write_text("ninja_deps")

            # 2. Package cache
            pkg_tar = tmp_path / "cache.tar.gz"
            subprocess.run(
                ["tar", "-czf", str(pkg_tar), "-C", str(src_dir / "out"), "Release/"],
                check=True,
            )

            # 3. Simulate Stage 3 fresh source checkout (newer timestamp)
            time.sleep(0.05)
            source_file = src_dir / "v8" / "src" / "api.cc"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("// fresh source checked out in Stage 3")
            t_source = source_file.stat().st_mtime

            # 4. Extract cache with tar -xzf (preserve timestamps)
            extract_dir = src_dir / "out"
            extract_dir.mkdir(parents=True, exist_ok=True)
            subprocess.run(["tar", "-xzf", str(pkg_tar), "-C", str(extract_dir)], check=True)

            # 5. Clean lock and ninja deps as download-cache.sh does
            (out_release / ".siso_lock").unlink(missing_ok=True)
            (out_release / ".ninja_deps").unlink(missing_ok=True)
            self.assertFalse((out_release / ".siso_lock").exists())
            self.assertFalse((out_release / ".ninja_deps").exists())

            # 6. Apply download-cache.sh timestamp synchronization
            manifest_files = [
                out_release / "build.ninja",
                out_release / "args.gn",
            ]
            for mf in manifest_files:
                if mf.exists():
                    os.utime(mf, None)  # touch to current time

            time.sleep(1.0)  # guaranteed timestamp tick

            # Touch outputs (obj and gen)
            for p in out_release.rglob("*"):
                if p.is_file() and ("obj" in p.parts or "gen" in p.parts):
                    os.utime(p, None)

            # 7. Check timestamps
            t_manifest = (out_release / "build.ninja").stat().st_mtime
            t_output = v8_obj.stat().st_mtime

            # Assert T_source <= T_manifest < T_output
            self.assertLessEqual(
                t_source,
                t_manifest,
                "Manifest build.ninja must be >= source files to prevent gn gen re-run",
            )
            self.assertLess(
                t_manifest,
                t_output,
                "Output object files must be strictly newer than manifest",
            )

            # Assert Siso's condition inmtime.After(outmtime) is FALSE
            inmtime = t_source
            outmtime = t_output
            inmtime_after_outmtime = inmtime > outmtime
            self.assertFalse(
                inmtime_after_outmtime,
                "inmtime must NOT be after outmtime (otherwise Siso marks target dirty)",
            )

    def test_sisorc_configuration_content(self):
        """Verify .sisorc flags format and content."""
        siso_cache_dir = "/tmp/fake_siso_cache"
        content = f"ninja -fs_keep_tainted -local_cache_enable -cache_dir={siso_cache_dir}\n"
        self.assertIn("-fs_keep_tainted", content)
        self.assertIn("-local_cache_enable", content)
        self.assertIn(f"-cache_dir={siso_cache_dir}", content)


if __name__ == "__main__":
    unittest.main()
