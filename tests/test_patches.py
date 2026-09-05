#!/usr/bin/env python3
"""
Test suite to validate Braving patch structure and syntax.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH_DIR = os.path.join(REPO_ROOT, "patches")


def test_patches_structure():
    assert os.path.isdir(PATCH_DIR), f"Missing {PATCH_DIR}"

    # Dynamically discover patch subdirectories (skip empty dirs with only .gitkeep)
    subdirs = [
        d for d in sorted(os.listdir(PATCH_DIR))
        if os.path.isdir(os.path.join(PATCH_DIR, d)) and not d.startswith('.')
        and any(f.endswith('.patch') for f in os.listdir(os.path.join(PATCH_DIR, d)))
    ]
    assert len(subdirs) > 0, f"No patch subdirectories with .patch files found in {PATCH_DIR}"
    total_patches = 0

    for sub in subdirs:
        dirpath = os.path.join(PATCH_DIR, sub)
        assert os.path.isdir(dirpath), f"Missing patch subdir {dirpath}"

        patches = [f for f in os.listdir(dirpath) if f.endswith(".patch")]
        assert len(patches) > 0, f"No patches found in {dirpath}"

        for p in patches:
            filepath = os.path.join(dirpath, p)
            assert os.path.getsize(filepath) > 50, f"Patch {p} is suspiciously small"
            with open(filepath, "r") as f:
                content = f.read()
            assert "diff --git" in content or "--- " in content, f"Invalid patch format in {p}"
            total_patches += 1

    print(f"PASS: test_patches_structure ({total_patches} patches verified)")


if __name__ == "__main__":
    try:
        test_patches_structure()
        print("ALL PATCH TESTS PASSED.")
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
