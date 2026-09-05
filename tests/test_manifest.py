#!/usr/bin/env python3
"""
Test suite to validate Braving release manifests and upstream metadata files dynamically.
"""

import os
import sys
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_upstream_metadata():
    metadata_dir = os.path.join(REPO_ROOT, "metadata")
    assert os.path.isdir(metadata_dir), f"Missing metadata dir {metadata_dir}"

    upstream_files = [f for f in os.listdir(metadata_dir) if f.startswith("upstream-") and f.endswith(".yaml")]
    assert len(upstream_files) > 0, "No upstream metadata files found in metadata/"

    for fname in upstream_files:
        upstream_file = os.path.join(metadata_dir, fname)
        with open(upstream_file, "r") as f:
            data = yaml.safe_load(f)

        assert "release" in data, f"Missing release section in {fname}"
        assert "brave_version" in data["release"], f"Missing brave_version in {fname}"
        assert "repositories" in data, f"Missing repositories in {fname}"
        assert "brave_core" in data["repositories"], f"Missing brave_core in {fname}"
        assert "commit" in data["repositories"]["brave_core"], f"Missing brave_core commit in {fname}"
        assert "chromium" in data["repositories"], f"Missing chromium in {fname}"
        assert "version" in data["repositories"]["chromium"], f"Missing chromium version in {fname}"
        assert data["gn_arguments"]["braving_overrides"]["chrome_public_manifest_package"] == "org.braving.browser"
        print(f"PASS: test_upstream_metadata ({fname})")


def test_release_manifest_if_present():
    releases_dir = os.path.join(REPO_ROOT, "metadata", "releases")
    if not os.path.isdir(releases_dir):
        return

    release_files = [f for f in os.listdir(releases_dir) if f.endswith(".yaml")]
    for fname in release_files:
        fpath = os.path.join(releases_dir, fname)
        with open(fpath, "r") as f:
            data = yaml.safe_load(f)
        assert data["package_id"] == "org.braving.browser"
        assert "brave_core_commit" in data
        assert "chromium_commit" in data
        assert len(data.get("applied_patches", [])) > 0
        print(f"PASS: test_release_manifest ({fname})")


if __name__ == "__main__":
    try:
        test_upstream_metadata()
        test_release_manifest_if_present()
        print("ALL MANIFEST TESTS PASSED.")
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
