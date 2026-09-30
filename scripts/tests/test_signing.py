#!/usr/bin/env python3
"""
Unit and integration tests for Braving Android APK release signing:
- scripts/android/sign-apk.sh
- scripts/android/build-android.sh
- .gitlab-ci.yml signing integration
"""

import base64
import glob
import hashlib
import http.server
import json
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SIGN_SCRIPT = REPO_ROOT / "scripts" / "android" / "sign-apk.sh"

# Minimal valid compiled binary AndroidManifest.xml (package="org.braving.browser", minSdkVersion=29)
MINIMAL_BINARY_MANIFEST_B64 = (
    "AwAIAEADAAABABwABAIAAAwAAAAAAAAAAAAAAEwAAAAAAAAAAAAAAB4AAABEAAAAegAAAIIAAACU"
    "AAAA7AAAAAABAAAqAQAAPAEAAHABAACkAQAADQBtAGkAbgBTAGQAawBWAGUAcgBzAGkAbwBuAAAA"
    "EQBjAG8AbQBwAGkAbABlAFMAZABrAFYAZQByAHMAaQBvAG4AAAAZAGMAbwBtAHAAaQBsAGUAUwBk"
    "AGsAVgBlAHIAcwBpAG8AbgBDAG8AZABlAG4AYQBtAGUAAAACADEANgAAAAcAYQBuAGQAcgBvAGkA"
    "ZAAAACoAaAB0AHQAcAA6AC8ALwBzAGMAaABlAG0AYQBzAC4AYQBuAGQAcgBvAGkAZAAuAGMAbwBt"
    "AC8AYQBwAGsALwByAGUAcwAvAGEAbgBkAHIAbwBpAGQAAAAIAG0AYQBuAGkAZgBlAHMAdAAAABMA"
    "bwByAGcALgBiAHIAYQB2AGkAbgBnAC4AYgByAG8AdwBzAGUAcgAAAAcAcABhAGMAawBhAGcAZQAA"
    "ABgAcABsAGEAdABmAG8AcgBtAEIAdQBpAGwAZABWAGUAcgBzAGkAbwBuAEMAbwBkAGUAAAAYAHAA"
    "bABhAHQAZgBvAHIAbQBCAHUAaQBsAGQAVgBlAHIAcwBpAG8AbgBOAGEAbQBlAAAACAB1AHMAZQBz"
    "AC0AcwBkAGsAAACAAQgAFAAAAAwCAQFyBQEBcwUBAQABEAAYAAAAAQAAAP////8EAAAABQAAAAIB"
    "EACIAAAAAQAAAP//////////BgAAABQAFAAFAAAAAAAAAAUAAAABAAAA/////wgAABAkAAAABQAA"
    "AAIAAAADAAAACAAAAwMAAAD/////CAAAAAcAAAAIAAADBwAAAP////8JAAAA/////wgAABAkAAAA"
    "/////woAAAD/////CAAAEBAAAAACARAAOAAAAAAAAAD//////////wsAAAAUABQAAQAAAAAAAAAF"
    "AAAAAAAAAP////8IAAAQHQAAAAMBEAAYAAAAAAAAAP//////////CwAAAAMBEAAYAAAAAQAAAP//"
    "////////BgAAAAEBEAAYAAAAAQAAAP////8EAAAABQAAAA=="
)


def create_minimal_apk(apk_path: Path) -> None:
    apk_path.parent.mkdir(parents=True, exist_ok=True)
    axml_bytes = base64.b64decode(MINIMAL_BINARY_MANIFEST_B64)
    with zipfile.ZipFile(apk_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("AndroidManifest.xml", axml_bytes)
        zf.writestr("classes.dex", b"dex\n035\x00" + b"\x00" * 32)


class TestGitLabCISigningConfig(unittest.TestCase):
    """Validate .gitlab-ci.yml signing configuration."""

    def test_gitlab_ci_signing_step_configured(self):
        ci_file = REPO_ROOT / ".gitlab-ci.yml"
        with open(ci_file, "r", encoding="utf-8") as f:
            ci_data = yaml.safe_load(f)

        self.assertIn("build_android", ci_data)
        build_job = ci_data["build_android"]
        job_vars = build_job.get("variables", {})

        self.assertEqual(job_vars.get("ANDROID_KEYSTORE_FILE"), "braving_android.jks")
        self.assertEqual(job_vars.get("ANDROID_KEY_ALIAS"), "braving")

        # Never hardcode KEY_PASSWORD_ANDROID in .gitlab-ci.yml
        global_vars = ci_data.get("variables", {})
        self.assertNotIn("KEY_PASSWORD_ANDROID", global_vars)
        self.assertNotIn("KEY_PASSWORD_ANDROID", job_vars)

        scripts = build_job.get("script", [])
        script_joined = "\n".join(scripts)
        self.assertIn("./scripts/android/sign-apk.sh --preflight", script_joined)
        self.assertIn("./scripts/android/sign-apk.sh", script_joined)

        # Ensure preflight runs before build-android.sh and signing runs after
        idx_preflight = next(i for i, s in enumerate(scripts) if "sign-apk.sh --preflight" in s)
        idx_build = next(i for i, s in enumerate(scripts) if "build-android.sh" in s)
        idx_sign = next(i for i, s in enumerate(scripts) if s.strip() == "./scripts/android/sign-apk.sh")
        self.assertLess(idx_preflight, idx_build, "Preflight check must run before build-android.sh")
        self.assertLess(idx_build, idx_sign, "APK signing step must run after build-android.sh")


class TestSignApkScriptUnit(unittest.TestCase):
    """Unit and mock-server tests for sign-apk.sh that run in any environment."""

    def test_dry_run_succeeds_without_secrets(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        res = subprocess.run(
            ["bash", str(SIGN_SCRIPT), "--dry-run"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Dry-run failed: {res.stderr}")
        self.assertIn("braving_android.jks", res.stdout)
        self.assertIn("braving", res.stdout)
        self.assertIn("KEY_PASSWORD_ANDROID", res.stdout)

    def test_missing_password_fails_loudly(self):
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        res = subprocess.run(
            ["bash", str(SIGN_SCRIPT), "--preflight"],
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("KEY_PASSWORD_ANDROID", res.stderr)

    def test_missing_keystore_fails_without_leaking_secret(self):
        secret = "MyUltraSecret$KeyPass!987654"
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "KEY_PASSWORD_ANDROID": secret,
                "SECURE_FILES_DIR": os.path.join(tmpdir, ".secure_files"),
                "CI_PROJECT_DIR": tmpdir,
            }
            res = subprocess.run(
                ["bash", str(SIGN_SCRIPT), "--preflight"],
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("braving_android.jks", res.stderr)
            self.assertNotIn(secret, res.stdout, "Secret password leaked to stdout!")
            self.assertNotIn(secret, res.stderr, "Secret password leaked to stderr!")

    def test_gitlab_secure_files_api_download_and_mock_signing(self):
        """
        Test end-to-end GitLab Secure Files API download of `braving_android.jks`,
        SHA256 verification, zipalign + apksigner invocation, and artifact synchronization.
        """
        fake_keystore_bytes = b"FAKE_JKS_KEYSTORE_CONTENT_FOR_UNIT_TEST"
        expected_sha256 = hashlib.sha256(fake_keystore_bytes).hexdigest()
        secret_pass = "Special$Pass'\"\\#2026!"
        requests_log = []

        class MockGitLabHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests_log.append((self.path, self.headers.get("JOB-TOKEN")))
                if self.headers.get("JOB-TOKEN") != "glpat-job-token-123":
                    self.send_response(401)
                    self.end_headers()
                    return

                if self.path.startswith("/api/v4/projects/42/secure_files?"):
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    payload = [
                        {
                            "id": 99,
                            "name": "braving_android.jks ",  # include trailing space as in user prompt
                            "checksum": expected_sha256,
                            "checksum_algorithm": "sha256",
                        }
                    ]
                    self.wfile.write(json.dumps(payload).encode("utf-8"))
                elif self.path == "/api/v4/projects/42/secure_files/99/download":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.end_headers()
                    self.wfile.write(fake_keystore_bytes)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), MockGitLabHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                bin_dir = tmp_path / "mock_bin"
                bin_dir.mkdir()

                # Create mock keytool, zipalign, and apksigner
                mock_keytool = bin_dir / "keytool"
                mock_keytool.write_text(
                    "#!/usr/bin/env bash\n"
                    'if [[ "${BRAVING_KS_PASS:-}" != "' + secret_pass.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$") + '" ]]; then exit 1; fi\n'
                    "exit 0\n"
                )
                mock_keytool.chmod(0o755)

                mock_zipalign = bin_dir / "zipalign"
                mock_zipalign.write_text(
                    "#!/usr/bin/env bash\n"
                    '# zipalign -p -f 4 in.apk out.apk\n'
                    'cp -f "$4" "$5"\n'
                )
                mock_zipalign.chmod(0o755)

                apksigner_log = tmp_path / "apksigner_calls.log"
                mock_apksigner = bin_dir / "apksigner"
                mock_apksigner.write_text(
                    "#!/usr/bin/env bash\n"
                    f'echo "$*" >> "{apksigner_log}"\n'
                    'if [[ "$1" == "sign" ]]; then\n'
                    '  if [[ -z "${BRAVING_KS_PASS:-}" || -z "${BRAVING_KEY_PASS:-}" ]]; then exit 1; fi\n'
                    '  in_apk=""\n'
                    '  out_apk=""\n'
                    '  while [[ $# -gt 0 ]]; do\n'
                    '    case "$1" in\n'
                    '      --in) in_apk="$2"; shift 2 ;;\n'
                    '      --out) out_apk="$2"; shift 2 ;;\n'
                    '      *) shift ;;\n'
                    '    esac\n'
                    '  done\n'
                    '  cp -f "$in_apk" "$out_apk"\n'
                    '  echo "SIGNED_BY_BRAVING" >> "$out_apk"\n'
                    '  touch "${out_apk}.idsig"\n'
                    'elif [[ "$1" == "verify" ]]; then\n'
                    '  target="${@: -1}"\n'
                    '  grep -q "SIGNED_BY_BRAVING" "$target" || exit 1\n'
                    '  echo "Verifies"\n'
                    'fi\n'
                )
                mock_apksigner.chmod(0o755)

                out_apks = tmp_path / "out" / "apks"
                release_apks = tmp_path / "build-workspace" / "src" / "out" / "Release" / "apks"
                out_apks.mkdir(parents=True)
                release_apks.mkdir(parents=True)

                apk_file = out_apks / "Braving-1.95.102-arm64.apk"
                create_minimal_apk(apk_file)

                secure_dir = tmp_path / ".secure_files"
                env = {
                    "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                    "KEY_PASSWORD_ANDROID": secret_pass,
                    "CI_API_V4_URL": f"http://127.0.0.1:{port}/api/v4",
                    "CI_PROJECT_ID": "42",
                    "CI_JOB_TOKEN": "glpat-job-token-123",
                    "SECURE_FILES_DIR": str(secure_dir),
                    "OUTPUT_APK_DIR": str(out_apks),
                    "OUT_DIR": str(release_apks.parent),
                    "ZIPALIGN_PATH": str(mock_zipalign),
                    "APKSIGNER_PATH": str(mock_apksigner),
                }

                res = subprocess.run(
                    ["bash", str(SIGN_SCRIPT)],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res.returncode, 0, f"sign-apk.sh failed:\n{res.stderr}\n{res.stdout}")
                self.assertNotIn(secret_pass, res.stdout)
                self.assertNotIn(secret_pass, res.stderr)

                # Verify keystore was downloaded with 0600 permissions
                downloaded_ks = secure_dir / "braving_android.jks"
                self.assertTrue(downloaded_ks.is_file())
                self.assertEqual(downloaded_ks.read_bytes(), fake_keystore_bytes)
                mode = stat.S_IMODE(downloaded_ks.stat().st_mode)
                self.assertEqual(mode, 0o600)

                # Verify both out/apks/ and build-workspace/src/out/Release/apks/ have the signed APK
                self.assertIn(b"SIGNED_BY_BRAVING", apk_file.read_bytes())
                synced_apk = release_apks / "Braving-1.95.102-arm64.apk"
                self.assertTrue(synced_apk.is_file())
                self.assertEqual(apk_file.read_bytes(), synced_apk.read_bytes())

                # Ensure no stray .idsig files remain
                self.assertEqual(list(out_apks.glob("*.idsig")), [])
                self.assertEqual(list(release_apks.glob("*.idsig")), [])

                # Check apksigner invocation arguments used alias 'braving' and env: passwords
                calls = apksigner_log.read_text()
                self.assertIn("--ks-key-alias braving", calls)
                self.assertIn("--ks-pass env:BRAVING_KS_PASS", calls)
                self.assertIn("--key-pass env:BRAVING_KEY_PASS", calls)
                self.assertNotIn(secret_pass, calls)
        finally:
            server.shutdown()
            server.server_close()

    def test_gitlab_secure_files_checksum_mismatch_rejected(self):
        """Verify tampered download from GitLab Secure Files API is rejected."""
        class TamperedHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if "secure_files?" in self.path:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    payload = [
                        {
                            "id": 1,
                            "name": "braving_android.jks",
                            "checksum": "0" * 64,
                            "checksum_algorithm": "sha256",
                        }
                    ]
                    self.wfile.write(json.dumps(payload).encode("utf-8"))
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"CORRUPTED_BYTES")

            def log_message(self, format, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), TamperedHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                env = {
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "KEY_PASSWORD_ANDROID": "validpass123",
                    "CI_API_V4_URL": f"http://127.0.0.1:{port}/api/v4",
                    "CI_PROJECT_ID": "42",
                    "CI_JOB_TOKEN": "token",
                    "SECURE_FILES_DIR": os.path.join(tmpdir, ".secure_files"),
                    "CI_PROJECT_DIR": tmpdir,
                }
                res = subprocess.run(
                    ["bash", str(SIGN_SCRIPT), "--preflight"],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(res.returncode, 0)
                self.assertIn("SHA256 mismatch", res.stderr)
                self.assertFalse(os.path.exists(os.path.join(tmpdir, ".secure_files", "braving_android.jks")))
        finally:
            server.shutdown()
            server.server_close()

    def test_cross_origin_redirect_strips_job_token_and_trailing_space_local_file(self):
        """
        Verify that:
        1. Cross-origin 302 redirects from GitLab API to external object storage strip JOB-TOKEN.
        2. Local `.secure_files/braving_android.jks ` (with trailing space) is discovered cleanly.
        """
        fake_keystore_bytes = b"REDIRECTED_JKS_BYTES"
        expected_sha256 = hashlib.sha256(fake_keystore_bytes).hexdigest()
        storage_headers = {}

        class StorageHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                storage_headers.update({k.lower(): v for k, v in self.headers.items()})
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                self.wfile.write(fake_keystore_bytes)

            def log_message(self, format, *args):
                pass

        storage_server = http.server.HTTPServer(("127.0.0.1", 0), StorageHandler)
        storage_port = storage_server.server_address[1]
        threading.Thread(target=storage_server.serve_forever, daemon=True).start()

        class ApiRedirectHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if "secure_files?" in self.path:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    payload = [
                        {
                            "id": 7,
                            "name": "braving_android.jks",
                            "checksum": expected_sha256,
                            "checksum_algorithm": "sha256",
                        }
                    ]
                    self.wfile.write(json.dumps(payload).encode("utf-8"))
                elif self.path.endswith("/download"):
                    self.send_response(302)
                    self.send_header("Location", f"http://localhost:{storage_port}/bucket/braving_android.jks")
                    self.end_headers()

            def log_message(self, format, *args):
                pass

        api_server = http.server.HTTPServer(("127.0.0.1", 0), ApiRedirectHandler)
        api_port = api_server.server_address[1]
        threading.Thread(target=api_server.serve_forever, daemon=True).start()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                bin_dir = tmp_path / "mock_bin"
                bin_dir.mkdir()
                mock_keytool = bin_dir / "keytool"
                mock_keytool.write_text("#!/usr/bin/env bash\nexit 0\n")
                mock_keytool.chmod(0o755)

                secure_dir = tmp_path / ".secure_files"
                env = {
                    "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                    "KEY_PASSWORD_ANDROID": "pass123",
                    "CI_API_V4_URL": f"http://127.0.0.1:{api_port}/api/v4",
                    "CI_PROJECT_ID": "42",
                    "CI_JOB_TOKEN": "secret-job-token",
                    "SECURE_FILES_DIR": str(secure_dir),
                }
                res = subprocess.run(
                    ["bash", str(SIGN_SCRIPT), "--preflight"],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res.returncode, 0, f"Preflight redirect failed: {res.stderr}")
                self.assertNotIn("job-token", storage_headers, "JOB-TOKEN must not leak across hosts on redirect!")

                # Rename local file to include a trailing space (`braving_android.jks `) and verify offline resolution
                spaced_ks = secure_dir / "braving_android.jks "
                (secure_dir / "braving_android.jks").rename(spaced_ks)
                offline_env = {
                    "PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                    "KEY_PASSWORD_ANDROID": "pass123",
                    "SECURE_FILES_DIR": str(secure_dir),
                }
                res_spaced = subprocess.run(
                    ["bash", str(SIGN_SCRIPT), "--preflight"],
                    env=offline_env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res_spaced.returncode, 0, f"Trailing-space local keystore failed: {res_spaced.stderr}")
        finally:
            api_server.shutdown()
            api_server.server_close()
            storage_server.shutdown()
            storage_server.server_close()


class TestRealCryptographicApkSigning(unittest.TestCase):
    """
    Deep verification using real keytool, zipalign, and apksigner when present on the host.
    """

    def _find_tool(self, name: str):
        in_path = shutil.which(name)
        if in_path:
            return in_path
        sdk_candidates = sorted(
            glob.glob(f"/home/pc/Android/Sdk/build-tools/*/{name}")
            + glob.glob(str(REPO_ROOT / f"build-workspace/src/third_party/android_sdk/public/build-tools/*/{name}"))
        )
        for c in reversed(sdk_candidates):
            if os.path.isfile(c) and os.access(c, os.X_OK):
                return c
        return None

    def test_real_jks_signing_and_verification(self):
        keytool_bin = self._find_tool("keytool")
        zipalign_bin = self._find_tool("zipalign")
        apksigner_bin = self._find_tool("apksigner")

        if not (keytool_bin and zipalign_bin and apksigner_bin):
            self.skipTest("keytool, zipalign, or apksigner not installed in current environment")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            secure_dir = tmp_path / ".secure_files"
            secure_dir.mkdir(parents=True)
            jks_path = secure_dir / "braving_android.jks"
            password = "Braving$ReleaseKey!2026"

            gen_env = dict(os.environ, KEY_PASSWORD_ANDROID=password)
            subprocess.run(
                [
                    keytool_bin,
                    "-genkeypair",
                    "-keystore",
                    str(jks_path),
                    "-alias",
                    "braving",
                    "-keyalg",
                    "RSA",
                    "-keysize",
                    "2048",
                    "-validity",
                    "365",
                    "-storepass:env",
                    "KEY_PASSWORD_ANDROID",
                    "-keypass:env",
                    "KEY_PASSWORD_ANDROID",
                    "-dname",
                    "CN=Braving Browser, O=Braving, C=US",
                ],
                env=gen_env,
                check=True,
                capture_output=True,
            )

            out_apks = tmp_path / "out" / "apks"
            release_apks = tmp_path / "build-workspace" / "src" / "out" / "Release" / "apks"
            out_apks.mkdir(parents=True)
            release_apks.mkdir(parents=True)

            apk_path = out_apks / "Braving-1.95.102-arm64.apk"
            create_minimal_apk(apk_path)
            # Also place ChromePublic.apk and TrichromeLibrary.apk in release_apks to verify out/apks is not polluted
            create_minimal_apk(release_apks / "ChromePublic.apk")
            create_minimal_apk(release_apks / "TrichromeLibrary.apk")

            run_env = dict(
                os.environ,
                KEY_PASSWORD_ANDROID=password,
                SECURE_FILES_DIR=str(secure_dir),
                OUTPUT_APK_DIR=str(out_apks),
                OUT_DIR=str(release_apks.parent),
                ZIPALIGN_PATH=zipalign_bin,
                APKSIGNER_PATH=apksigner_bin,
            )

            # 1. Verify preflight succeeds with correct password & alias
            res_pre = subprocess.run(
                ["bash", str(SIGN_SCRIPT), "--preflight"],
                env=run_env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_pre.returncode, 0, f"Preflight failed: {res_pre.stderr}")

            # 2. Verify preflight fails with wrong password
            bad_env = dict(run_env, KEY_PASSWORD_ANDROID="WrongPassword123")
            res_bad = subprocess.run(
                ["bash", str(SIGN_SCRIPT), "--preflight"],
                env=bad_env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_bad.returncode, 0, "Preflight must fail when password is wrong")

            # 3. Run full APK signing & verification
            res_sign = subprocess.run(
                ["bash", str(SIGN_SCRIPT)],
                env=run_env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_sign.returncode, 0, f"Real APK signing failed:\n{res_sign.stderr}\n{res_sign.stdout}")
            self.assertNotIn(password, res_sign.stdout)
            self.assertNotIn(password, res_sign.stderr)

            # Verify out/apks was NOT polluted with ChromePublic.apk or TrichromeLibrary.apk
            self.assertEqual([p.name for p in out_apks.iterdir()], ["Braving-1.95.102-arm64.apk"])

            # 4. Verify certificate subject and 0644 permissions in signed APK using apksigner verify --print-certs
            for verified_target in (apk_path, release_apks / "Braving-1.95.102-arm64.apk"):
                self.assertTrue(verified_target.is_file())
                self.assertEqual(stat.S_IMODE(verified_target.stat().st_mode), 0o644)
                verify_res = subprocess.run(
                    [apksigner_bin, "verify", "--verbose", "--print-certs", str(verified_target)],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertIn("Verifies", verify_res.stdout)
                self.assertIn("CN=Braving Browser", verify_res.stdout)

            # 5. Verify idempotency: running sign-apk.sh a second time skips redundant re-signing
            res_idem = subprocess.run(
                ["bash", str(SIGN_SCRIPT), f"--apk={apk_path}"],
                env=run_env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_idem.returncode, 0, f"Idempotent second run failed: {res_idem.stderr}")
            self.assertIn("already aligned, signed, and verified", res_idem.stdout)

    def test_jks_separate_keypass_and_trusted_cert_rejection(self):
        """
        Verify that `--preflight` catches:
        1. A JKS keystore where KEY_PASSWORD_ANDROID unlocks the store but NOT the private key.
        2. A keystore where alias `braving` is a `trustedCertEntry` (certificate without private key).
        """
        keytool_bin = self._find_tool("keytool")
        if not keytool_bin:
            self.skipTest("keytool not installed")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            jks_split = tmp_path / "split_pass.jks"
            subprocess.run(
                [
                    keytool_bin,
                    "-genkeypair",
                    "-storetype",
                    "JKS",
                    "-keystore",
                    str(jks_split),
                    "-alias",
                    "braving",
                    "-keyalg",
                    "RSA",
                    "-keysize",
                    "2048",
                    "-validity",
                    "365",
                    "-storepass",
                    "StorePass123",
                    "-keypass",
                    "PrivateKeyPass456",
                    "-dname",
                    "CN=Braving Split, O=Braving, C=US",
                ],
                check=True,
                capture_output=True,
            )

            # Wrong keypass must fail in preflight!
            env_wrong_keypass = dict(
                os.environ,
                KEY_PASSWORD_ANDROID="StorePass123",
                ANDROID_KEYSTORE_PATH=str(jks_split),
            )
            res_wrong = subprocess.run(
                ["bash", str(SIGN_SCRIPT), "--preflight"],
                env=env_wrong_keypass,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_wrong.returncode, 0, "Preflight must fail when private key password is wrong")
            self.assertIn("Failed to recover private key", res_wrong.stderr)

            # Correct ANDROID_KEY_PASSWORD must pass in preflight!
            env_right_keypass = dict(
                env_wrong_keypass,
                ANDROID_KEY_PASSWORD="PrivateKeyPass456",
            )
            res_right = subprocess.run(
                ["bash", str(SIGN_SCRIPT), "--preflight"],
                env=env_right_keypass,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_right.returncode, 0, f"Preflight with ANDROID_KEY_PASSWORD failed: {res_right.stderr}")

            # Export certificate and import as trustedCertEntry (no private key)
            cert_file = tmp_path / "cert.pem"
            jks_cert_only = tmp_path / "cert_only.jks"
            subprocess.run(
                [
                    keytool_bin,
                    "-exportcert",
                    "-keystore",
                    str(jks_split),
                    "-alias",
                    "braving",
                    "-storepass",
                    "StorePass123",
                    "-file",
                    str(cert_file),
                ],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [
                    keytool_bin,
                    "-importcert",
                    "-keystore",
                    str(jks_cert_only),
                    "-alias",
                    "braving",
                    "-storepass",
                    "StorePass123",
                    "-file",
                    str(cert_file),
                    "-noprompt",
                ],
                check=True,
                capture_output=True,
            )

            env_cert_only = dict(
                os.environ,
                KEY_PASSWORD_ANDROID="StorePass123",
                ANDROID_KEYSTORE_PATH=str(jks_cert_only),
            )
            res_cert = subprocess.run(
                ["bash", str(SIGN_SCRIPT), "--preflight"],
                env=env_cert_only,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res_cert.returncode, 0, "Preflight must reject trustedCertEntry without private key")
            self.assertIn("trustedCertEntry", res_cert.stderr)


if __name__ == "__main__":
    unittest.main()
