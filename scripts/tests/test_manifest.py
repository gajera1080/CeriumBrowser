#!/usr/bin/env python3
import os
import sys
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_upstream_metadata():
    metadata_dir = os.path.join(REPO_ROOT, "metadata")
    if not os.path.isdir(metadata_dir):
        print("SKIP: metadata dir not found (not generated yet)")
        return
    upstream_files = [f for f in os.listdir(metadata_dir) if f.startswith("upstream-") and f.endswith(".yaml")]
    if not upstream_files:
        print("SKIP: No upstream metadata files found")
        return
    for fname in upstream_files:
        upstream_file = os.path.join(metadata_dir, fname)
        with open(upstream_file, "r") as f:
            data = yaml.safe_load(f)
        assert "release" in data, f"Missing release section in {fname}"
        assert "brave_version" in data["release"], f"Missing brave_version in {fname}"
        print(f"PASS: test_upstream_metadata ({fname})")

def test_release_manifest():
    releases_dir = os.path.join(REPO_ROOT, "metadata", "releases")
    if not os.path.isdir(releases_dir):
        print("SKIP: metadata/releases dir not found (not generated yet)")
        return
    release_files = [f for f in os.listdir(releases_dir) if f.endswith(".yaml")]
    for fname in release_files:
        fpath = os.path.join(releases_dir, fname)
        with open(fpath, "r") as f:
            data = yaml.safe_load(f)
        assert data["package_id"] in ("org.cerium.browser", "org.braving.browser")
        print(f"PASS: test_release_manifest ({fname})")

if __name__ == "__main__":
    try:
        test_upstream_metadata()
        test_release_manifest()
        print("ALL MANIFEST TESTS PASSED.")
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
