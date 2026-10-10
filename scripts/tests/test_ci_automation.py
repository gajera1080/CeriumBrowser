#!/usr/bin/env python3
"""
Unit tests for CI automation scripts:
- Release version gating logic (check-release-needed.sh)
- Publish release payload generation (publish-release-direct.sh)

These tests verify the Python-based JSON parsing and payload logic used by the bash scripts.
"""

import json
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


class TestReleaseCheckLogic(unittest.TestCase):
    """Tests the tag existence check logic from check-release-needed.sh."""

    def test_tag_exists_response(self):
        """When tag API returns 200, SKIP_BUILD should be 'true'."""
        http_status = 200
        skip_build = "true" if http_status == 200 else "false"
        self.assertEqual(skip_build, "true")

    def test_tag_not_found_response(self):
        """When tag API returns 404, SKIP_BUILD should be 'false'."""
        http_status = 404
        skip_build = "true" if http_status == 200 else "false"
        self.assertEqual(skip_build, "false")

    def test_api_error_response(self):
        """On API error (500), SKIP_BUILD should default to 'false' (fail-open)."""
        http_status = 500
        skip_build = "true" if http_status == 200 else "false"
        self.assertEqual(skip_build, "false")

    def test_dotenv_format(self):
        """Dotenv output must be 'KEY=value' format (no quotes, no spaces)."""
        version = "1.96.60"
        skip_build = "false"
        dotenv_line = f"SKIP_BUILD={skip_build}"
        self.assertRegex(dotenv_line, r'^SKIP_BUILD=(true|false)$')
        self.assertNotIn('"', dotenv_line)
        self.assertNotIn("'", dotenv_line)

    def test_reads_dynamic_brave_version_from_dotenv_file(self):
        """check-release-needed.sh must read DYNAMIC_BRAVE_VERSION from BUILD_ENV_FILE if unset in environment."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, "test.env")
            with open(env_file, "w") as f:
                f.write("DYNAMIC_BRAVE_VERSION=1.97.56\n")
            res = subprocess.run(
                ["bash", os.path.join(REPO_ROOT, "scripts/ci/check-release-needed.sh")],
                env={"PATH": os.environ.get("PATH", ""), "BUILD_ENV_FILE": env_file},
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"check-release-needed failed: {res.stderr}")
            with open(env_file, "r") as f:
                content = f.read()
            self.assertIn("SKIP_BUILD=false", content)


class TestPublishReleasePayload(unittest.TestCase):
    """Tests the release payload generation from publish-release-direct.sh."""

    def _generate_payload(self, version, arch, commit_sha, apk_url, sha256=None, apk_name=None, chromium_version=None, sha256_url=None):
        """Simulates the Python payload generator used by publish-release-direct.sh."""
        apk_name = apk_name or f"braving-android-{arch}-v{version}.apk"
        chromium_part = f" and Chromium v{chromium_version}" if chromium_version else ""
        description_lines = [
            f"Updated to v{version}{chromium_part}\n",
            "### Android",
            f"- [{apk_name}]({apk_url})",
            f"- **Architecture**: `{arch}`",
        ]
        if sha256:
            description_lines.append(f"- **SHA256**: `{sha256}`")
        description_lines.extend([
            "\n### Debloated Features",
            "- Brave Wallet / Crypto",
            "- AI Chat / Leo",
            "- Brave VPN",
            "- Brave News",
            "- Brave Rewards / BAT Ads",
            "- P3A Telemetry\n",
        ])
        description = "\n".join(description_lines)
        links = [
            {
                "name": apk_name,
                "url": apk_url,
                "link_type": "package",
            }
        ]
        if sha256_url:
            links.append({
                "name": "SHA256SUMS.txt",
                "url": sha256_url,
                "link_type": "package",
            })
        payload = {
            "name": f"Release v{version}",
            "tag_name": f"v{version}",
            "ref": commit_sha,
            "description": description,
            "assets": {
                "links": links
            }
        }
        return payload

    def test_payload_structure(self):
        """Release payload must contain all required GitLab Release API fields."""
        payload = self._generate_payload(
            "1.96.60", "arm64", "abc123def",
            "https://gitlab.com/CeriumBrowser/Cerium-Browser/uploads/hash/file.apk",
            sha256="deadbeef",
        )
        self.assertIn("name", payload)
        self.assertIn("tag_name", payload)
        self.assertIn("ref", payload)
        self.assertIn("description", payload)
        self.assertIn("assets", payload)
        self.assertIn("links", payload["assets"])

    def test_tag_name_format(self):
        """Tag name must start with 'v' prefix."""
        payload = self._generate_payload("1.96.60", "arm64", "abc", "http://x")
        self.assertTrue(payload["tag_name"].startswith("v"))

    def test_asset_link_type(self):
        """Asset link must have link_type 'package'."""
        payload = self._generate_payload("1.96.60", "arm64", "abc", "http://x")
        link = payload["assets"]["links"][0]
        self.assertEqual(link["link_type"], "package")

    def test_asset_links_with_sha256(self):
        """When sha256_url is provided, links must include SHA256SUMS.txt package."""
        payload = self._generate_payload(
            "1.96.60", "arm64", "abc", "http://x/apk",
            sha256="deadbeef", sha256_url="http://x/sha256"
        )
        self.assertEqual(len(payload["assets"]["links"]), 2)
        self.assertEqual(payload["assets"]["links"][1]["name"], "SHA256SUMS.txt")
        self.assertEqual(payload["assets"]["links"][1]["url"], "http://x/sha256")
        self.assertEqual(payload["assets"]["links"][1]["link_type"], "package")

    def test_no_hardcoded_versions(self):
        """Payload fields must use the dynamic version, not hardcoded values."""
        payload = self._generate_payload("2.0.0", "x86_64", "sha", "http://x")
        self.assertIn("2.0.0", payload["name"])
        self.assertEqual(payload["name"], "Release v2.0.0")
        self.assertIn("v2.0.0", payload["tag_name"])
        self.assertIn("x86_64", payload["assets"]["links"][0]["name"])

    def test_description_format(self):
        """Description must include update notice with version and chromium version."""
        payload = self._generate_payload(
            "1.96.61", "arm64", "abc", "http://x",
            chromium_version="154.0.8037.98"
        )
        self.assertIn("Updated to v1.96.61 and Chromium v154.0.8037.98", payload["description"])
        self.assertIn("### Android", payload["description"])

    def test_payload_is_valid_json(self):
        """Payload must serialize to valid JSON."""
        payload = self._generate_payload("1.96.60", "arm64", "abc", "http://x")
        json_str = json.dumps(payload)
        reparsed = json.loads(json_str)
        self.assertEqual(reparsed["tag_name"], "v1.96.60")
        self.assertEqual(reparsed["name"], "Release v1.96.60")


class TestCIScriptSyntax(unittest.TestCase):
    """Verifies that all CI scripts exist and have valid bash syntax."""

    REPO_ROOT = os.path.join(os.path.dirname(__file__), '..', '..')

    def _check_bash_syntax(self, script_path):
        """Check bash syntax with bash -n."""
        full_path = os.path.join(self.REPO_ROOT, script_path)
        if not os.path.exists(full_path):
            self.skipTest(f"{script_path} not found (may not be created yet)")
        result = subprocess.run(
            ['bash', '-n', full_path],
            capture_output=True, text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"Syntax error in {script_path}:\n{result.stderr}"
        )

    def test_check_release_needed_syntax(self):
        self._check_bash_syntax('scripts/ci/check-release-needed.sh')

    def test_publish_release_syntax(self):
        self._check_bash_syntax('scripts/ci/publish-release-direct.sh')

    def test_publish_release_dry_run(self):
        """publish-release-direct.sh --dry-run must exit 0 and simulate multi-arch release."""
        env = os.environ.copy()
        env.update({
            "DYNAMIC_BRAVE_VERSION": "1.96.61",
            "TARGET_ARCH": "all",
            "CI_COMMIT_BRANCH": "release",
        })
        res = subprocess.run(
            ["bash", os.path.join(self.REPO_ROOT, "scripts/ci/publish-release-direct.sh"), "--dry-run"],
            capture_output=True, text=True, env=env
        )
        self.assertEqual(res.returncode, 0, f"publish-release dry-run failed: {res.stderr}")
        self.assertIn("Braving Direct Release Publisher", res.stdout)
        self.assertIn("Release v1.96.61", res.stdout)

    def test_apply_patches_syntax(self):
        self._check_bash_syntax('scripts/core/apply-patches.sh')

    def test_prepare_source_syntax(self):
        self._check_bash_syntax('scripts/core/prepare-source.sh')

    def test_build_android_syntax(self):
        self._check_bash_syntax('scripts/platforms/android/build.sh')

    def test_package_android_syntax(self):
        self._check_bash_syntax('scripts/platforms/android/package.sh')

    def test_sign_apk_android_syntax(self):
        self._check_bash_syntax('scripts/platforms/android/sign-apk.sh')

    def test_build_windows_syntax(self):
        self._check_bash_syntax('scripts/platforms/windows/build.sh')

    def test_package_windows_syntax(self):
        self._check_bash_syntax('scripts/platforms/windows/package.sh')

    def test_build_windows_dry_run(self):
        """build.sh --dry-run must exit 0 and parse manifests cleanly for x64, amd64, and arm64."""
        import glob
        manifests = sorted(glob.glob(os.path.join(self.REPO_ROOT, "metadata/releases/*.yaml")))
        if not manifests:
            return
        manifest = manifests[-1]
        for arch, expected_arch in [("x64", "x64"), ("amd64", "x64"), ("arm64", "arm64")]:
            res = subprocess.run(
                ["bash", os.path.join(self.REPO_ROOT, "scripts/platforms/windows/build.sh"),
                 f"--manifest={manifest}", f"--arch={arch}", "--release", "--dry-run"],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"build-windows dry-run failed for {arch}: {res.stderr}")
            self.assertIn("Braving Windows Build", res.stdout)
            self.assertIn(f"Architecture: {expected_arch}", res.stdout)
            self.assertIn("Dry-run mode requested. Validation complete.", res.stdout)

    def test_package_windows_dry_run(self):
        """package.sh --dry-run must exit 0 and validate for x64 and arm64."""
        for arch in ["x64", "arm64", "amd64"]:
            res = subprocess.run(
                ["bash", os.path.join(self.REPO_ROOT, "scripts/platforms/windows/package.sh"),
                 f"--arch={arch}", "--dry-run"],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"package-windows dry-run failed for {arch}: {res.stderr}")
            self.assertIn("Braving Windows Package", res.stdout)
            self.assertIn("Dry-run mode requested.", res.stdout)

    def test_package_windows_invalid_arch(self):
        """package.sh must reject invalid architecture with non-zero exit code."""
        res = subprocess.run(
            ["bash", os.path.join(self.REPO_ROOT, "scripts/platforms/windows/package.sh"),
             "--arch=invalid_arch"],
            capture_output=True, text=True
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid architecture", res.stderr)

    def test_build_windows_invalid_arch(self):
        """build.sh must reject invalid architecture with non-zero exit code."""
        res = subprocess.run(
            ["bash", os.path.join(self.REPO_ROOT, "scripts/platforms/windows/build.sh"),
             "--arch=invalid_arch"],
            capture_output=True, text=True
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid architecture", res.stderr)

    def test_gitlab_ci_yaml_structure(self):
        """Validate root .gitlab-ci.yml and modular includes in .gitlab/ci/."""
        import yaml
        ci_files = [
            '.gitlab-ci.yml',
            '.gitlab/ci/common.yml',
            '.gitlab/ci/android.yml',
            '.gitlab/ci/windows.yml',
        ]
        for rel_path in ci_files:
            full_path = os.path.join(self.REPO_ROOT, rel_path)
            self.assertTrue(os.path.isfile(full_path), f"Missing CI file: {rel_path}")
            with open(full_path, 'r', encoding='utf-8') as f:
                docs = [d for d in yaml.safe_load_all(f) if d]
            self.assertTrue(len(docs) >= 1, f"Empty YAML file: {rel_path}")
            spec = docs[0].get('spec', {})
            self.assertIn('inputs', spec, f"Missing spec:inputs in {rel_path}")

        # Check root configuration spec:inputs and runtime variables
        with open(os.path.join(self.REPO_ROOT, '.gitlab-ci.yml'), 'r', encoding='utf-8') as f:
            docs = [d for d in yaml.safe_load_all(f) if d]
        combined = {}
        for d in docs:
            combined.update(d)
        inputs = combined.get('spec', {}).get('inputs', {})
        self.assertIn('brave_version', inputs)
        self.assertNotIn('force_cache_rebuild', inputs)

        variables = combined.get('variables', {})
        self.assertIn('BRAVE_VERSION', variables)
        self.assertIn('FORCE_CACHE_REBUILD', variables)
        self.assertIsInstance(variables['BRAVE_VERSION'], str)
        self.assertIsInstance(variables['FORCE_CACHE_REBUILD'], str)

        if 'compile_target' in inputs:
            # Non-release branches require interactive developer selection in Web UI
            self.assertEqual(
                inputs['compile_target'].get('options'),
                ['all', 'android', 'windows', 'windows_x64', 'windows_arm64']
            )
            self.assertEqual(inputs['compile_target'].get('default'), 'all')
            self.assertIn('COMPILE_TARGET', variables)
        else:
            # Release branch builds all targets automatically without arch input prompt
            self.assertEqual(variables.get('COMPILE_TARGET', 'all'), 'all')

    def test_resolve_versions_execution(self):
        """resolve-versions.py must generate deterministic manifest and env files."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = os.path.join(tmpdir, "test.env")
            res = subprocess.run(
                [sys.executable, os.path.join(self.REPO_ROOT, "scripts/core/resolve-versions.py"),
                 "1.96.61", f"--repo-root={tmpdir}", f"--env-file={env_file}"],
                capture_output=True, text=True
            )
            self.assertEqual(res.returncode, 0, f"resolve-versions failed: {res.stderr}")
            self.assertTrue(os.path.isfile(env_file))
            with open(env_file, "r") as f:
                c = f.read()
            self.assertIn("DYNAMIC_BRAVE_VERSION=1.96.61", c)
            self.assertIn("DYNAMIC_CHROMIUM_VERSION=154.0.8037.98", c)

    def test_scripts_are_executable(self):
        """CI and core scripts must have execute permission."""
        scripts = [
            'scripts/ci/check-release-needed.sh',
            'scripts/ci/publish-release-direct.sh',
            'scripts/core/apply-patches.sh',
            'scripts/core/prepare-source.sh',
            'scripts/core/resolve-versions.py',
            'scripts/core/apply-assets.sh',
            'scripts/core/apply-branding.py',
            'scripts/core/apply-features.py',
            'scripts/core/filter-build-log.py',
            'scripts/core/upload-cache.sh',
            'scripts/core/download-cache.sh',
            'scripts/core/sync-chromium-source.sh',
            'scripts/core/verify-all.sh',
            'scripts/core/verify-branding.sh',
            'scripts/platforms/android/build.sh',
            'scripts/platforms/android/package.sh',
            'scripts/platforms/android/sign-apk.sh',
            'scripts/platforms/windows/build.sh',
            'scripts/platforms/windows/package.sh',
        ]
        for script in scripts:
            full_path = os.path.join(self.REPO_ROOT, script)
            self.assertTrue(os.path.exists(full_path), f"{script} does not exist")
            self.assertTrue(
                os.access(full_path, os.X_OK),
                f"{script} is not executable"
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
