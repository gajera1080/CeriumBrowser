#!/usr/bin/env python3
"""
Test suite to validate Braving release manifests and upstream metadata files.
"""

import os
import sys
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_upstream_metadata():
    metadata_dir = os.path.join(REPO_ROOT, "metadata")
    upstream_file = os.path.join(metadata_dir, "upstream-1.94.120.yaml")
    assert os.path.isfile(upstream_file), f"Missing {upstream_file}"

    with open(upstream_file, "r") as f:
        data = yaml.safe_load(f)

    assert data["release"]["brave_version"] == "1.94.120"
    assert data["repositories"]["brave_core"]["commit"] == "449b91b1c032bd6c94aacd054757a97e128635b5"
    assert data["repositories"]["chromium"]["version"] == "152.0.7977.76"
    assert data["repositories"]["chromium"]["commit"] == "0d89dfa2dd7c1ec4b8a14b9f303f887bb63b6174"
    assert data["gn_arguments"]["braving_overrides"]["chrome_public_manifest_package"] == "org.braving.browser"
    print("PASS: test_upstream_metadata")


def test_release_manifest_if_present():
    releases_dir = os.path.join(REPO_ROOT, "metadata", "releases")
    if not os.path.isdir(releases_dir):
        return

    for fname in os.listdir(releases_dir):
        if fname.endswith(".yaml"):
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
