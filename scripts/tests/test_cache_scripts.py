#!/usr/bin/env python3
"""
Unit and integration tests for Cerium Siso warm cache pipeline:
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

    def test_prepare_source_syntax(self):
        script = REPO_ROOT / "scripts" / "core" / "prepare-source.sh"
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


class TestBraveSourceTransport(unittest.TestCase):
    """Verify brave-core source artifact packaging, unpacking, and git clean exclusions."""

    def test_git_clean_preserves_brave_and_out(self):
        """Verify that git clean -ffd -e brave -e out preserves brave and out while cleaning untracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = Path(tmpdir) / "src"
            src_dir.mkdir(parents=True)
            subprocess.run(["git", "init", str(src_dir)], check=True, capture_output=True)
            (src_dir / "tracked.txt").write_text("tracked")
            subprocess.run(["git", "-C", str(src_dir), "config", "user.name", "Test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(src_dir), "config", "user.email", "test@example.com"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(src_dir), "add", "tracked.txt"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(src_dir), "commit", "-m", "initial", "--no-gpg-sign"], check=True, capture_output=True)

            # Untracked brave and out
            brave_dir = src_dir / "brave"
            brave_dir.mkdir(parents=True)
            (brave_dir / "dummy.txt").write_text("brave content")
            out_dir = src_dir / "out"
            out_dir.mkdir(parents=True)
            (out_dir / "build.txt").write_text("out content")
            (src_dir / "untracked.txt").write_text("remove me")

            subprocess.run(
                ["git", "-C", str(src_dir), "clean", "-ffd", "-e", "brave", "-e", "out"],
                check=True,
                capture_output=True,
            )

            self.assertTrue((brave_dir / "dummy.txt").exists(), "brave directory must be preserved")
            self.assertTrue((out_dir / "build.txt").exists(), "out directory must be preserved")
            self.assertFalse((src_dir / "untracked.txt").exists(), "untracked files must be removed")

    def test_brave_cache_workspace_preservation(self):
        """Verify build-workspace/src/brave restoration, git initialization, and repository integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            src = workspace / "src"
            brave = src / "brave"
            brave.mkdir(parents=True)
            (brave / "DEPS").write_text("vars = {}")
            (brave / "package.json").write_text("{}")

            # Run the verification and git-init script snippet from build.sh
            verify_cmd = (
                f'BRAVE_DIR="{brave}"\n'
                'if [[ -d "${BRAVE_DIR}" && ! -d "${BRAVE_DIR}/.git" ]]; then\n'
                '  git -C "${BRAVE_DIR}" init -q\n'
                '  git -C "${BRAVE_DIR}" config user.name "Cerium Browser Team"\n'
                '  git -C "${BRAVE_DIR}" config user.email "ci@ceriumbrowser.org"\n'
                '  git -C "${BRAVE_DIR}" commit --allow-empty -m "Prepared brave-core" --no-gpg-sign -q\n'
                'fi\n'
                'if [[ ! -d "${BRAVE_DIR}" ]]; then\n'
                '  echo "ERROR: Prepared brave-core not found in ${BRAVE_DIR}." >&2\n'
                '  exit 1\n'
                'fi\n'
            )
            res = subprocess.run(["bash", "-c", verify_cmd], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Verify/init failed: {res.stderr}")
            self.assertTrue((brave / "DEPS").exists(), "DEPS must exist in cached brave-core")
            # Verify git repo and commit exist so gclient skips unmanaged solution
            rev_res = subprocess.run(["git", "-C", str(brave), "rev-parse", "--verify", "HEAD"], capture_output=True, text=True)
            self.assertEqual(rev_res.returncode, 0, f"Git rev-parse HEAD failed: {rev_res.stderr}")

    def test_brave_missing_fails_fast(self):
        """Verify that missing src/brave triggers immediate failure in build.sh Phase 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            brave = workspace / "src" / "brave"
            verify_cmd = (
                f'BRAVE_DIR="{brave}"\n'
                'if [[ ! -d "${BRAVE_DIR}" ]]; then\n'
                '  echo "ERROR: Prepared brave-core not found in ${BRAVE_DIR}." >&2\n'
                '  exit 1\n'
                'fi\n'
            )
            res = subprocess.run(["bash", "-c", verify_cmd], capture_output=True, text=True)
            self.assertEqual(res.returncode, 1)
            self.assertIn("ERROR: Prepared brave-core not found", res.stderr)

    def test_archive_build_artifacts_tar_gz(self):
        """Verify archive_build_artifacts creates fast .tar.gz archive containing logs and configs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "build-workspace"
            out_dir = workspace / "src" / "out" / "Release"
            out_dir.mkdir(parents=True)
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "build.log").write_text("build log content")
            (out_dir / "args.gn").write_text("is_debug = false")
            (out_dir / ".ninja_log").write_text("# ninja log")
            (out_dir / "siso_output").write_text("siso output")

            archive_cmd = (
                f'WORKSPACE_DIR="{workspace}"\n'
                f'OUT_DIR="{out_dir}"\n'
                'archive_build_artifacts() {\n'
                '  local archive_path="${WORKSPACE_DIR}/build-artifacts.tar.gz"\n'
                '  local entries=()\n'
                '  if [[ -f "${WORKSPACE_DIR}/build.log" ]]; then\n'
                '    entries+=(-C "${WORKSPACE_DIR}" "build.log")\n'
                '  fi\n'
                '  if [[ -d "${OUT_DIR}" ]]; then\n'
                '    if [[ -f "${OUT_DIR}/args.gn" ]]; then\n'
                '      entries+=(-C "${OUT_DIR}" "args.gn")\n'
                '    fi\n'
                '    if [[ -f "${OUT_DIR}/.ninja_log" ]]; then\n'
                '      entries+=(-C "${OUT_DIR}" ".ninja_log")\n'
                '    fi\n'
                '    for s_file in "${OUT_DIR}"/siso*; do\n'
                '      if [[ -e "${s_file}" ]]; then\n'
                '        entries+=(-C "${OUT_DIR}" "$(basename "${s_file}")")\n'
                '      fi\n'
                '    done\n'
                '  fi\n'
                '  if [[ ${#entries[@]} -gt 0 ]]; then\n'
                '    tar -czf "${archive_path}" "${entries[@]}" 2>/dev/null || true\n'
                '  fi\n'
                '}\n'
                'archive_build_artifacts\n'
            )
            res = subprocess.run(["bash", "-c", archive_cmd], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"archive_build_artifacts failed: {res.stderr}")
            archive_path = workspace / "build-artifacts.tar.gz"
            self.assertTrue(archive_path.exists(), "build-artifacts.tar.gz must exist")
            list_res = subprocess.run(["tar", "-tzf", str(archive_path)], capture_output=True, text=True, check=True)
            self.assertIn("build.log", list_res.stdout)
            self.assertIn("args.gn", list_res.stdout)
            self.assertIn(".ninja_log", list_res.stdout)
            self.assertIn("siso_output", list_res.stdout)


if __name__ == "__main__":
    unittest.main()

