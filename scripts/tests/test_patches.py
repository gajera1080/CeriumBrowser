#!/usr/bin/env python3
"""
Test suite to validate Braving patch structure and syntax.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCH_DIR = os.path.join(REPO_ROOT, "patches")

def test_patches_structure():
    assert os.path.isdir(PATCH_DIR), f"Missing {PATCH_DIR}"

    total_patches = 0
    for root, _, files in os.walk(PATCH_DIR):
        for p in files:
            if p.endswith(".patch"):
                filepath = os.path.join(root, p)
                assert os.path.getsize(filepath) > 50, f"Patch {p} is suspiciously small"
                with open(filepath, "r") as f:
                    content = f.read()
                assert "diff --git" in content or "--- " in content, f"Invalid patch format in {p}"
                total_patches += 1

    assert total_patches > 0, f"No patch subdirectories with .patch files found in {PATCH_DIR}"
    print(f"PASS: test_patches_structure ({total_patches} patches verified)")

if __name__ == "__main__":
    try:
        test_patches_structure()
        print("ALL PATCH TESTS PASSED.")
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
