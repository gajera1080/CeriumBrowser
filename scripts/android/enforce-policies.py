#!/usr/bin/env python3
"""
Braving — Debloat Enterprise Policies & Brave Origin Backend
All C++ debloat policies, Brave Origin backend enablement, and uBlock subscriptions
are maintained via standard git patch:
patches/android/0003-enforce-debloat-policies.patch

Per project policy, git patches are the priority for C++ and UI modifications.
Python mutator logic is reserved strictly for dynamic tasks.
"""
import sys
import os
import subprocess

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")


def apply_policy_patch():
    patch_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../patches/android/0003-enforce-debloat-policies.patch"))
    if not os.path.isfile(patch_path):
        print(f"Note: Policy patch not found at {patch_path}")
        return

    git_dir = os.path.join(repo_root, ".git")
    if os.path.isdir(git_dir):
        res_rev = subprocess.run(["git", "-C", repo_root, "apply", "--check", "--reverse", patch_path], capture_output=True)
        if res_rev.returncode == 0:
            print("Debloat policies patch already applied (Skipped)")
            return
        res_fwd = subprocess.run(["git", "-C", repo_root, "apply", "--check", patch_path], capture_output=True)
        if res_fwd.returncode == 0:
            subprocess.run(["git", "-C", repo_root, "apply", patch_path], check=True)
            print("Applied 0003-enforce-debloat-policies.patch")
            return
        if STRICT:
            print("ERROR: 0003-enforce-debloat-policies.patch failed to apply", file=sys.stderr)
            sys.exit(1)
    else:
        print("Note: Target is not a git repository; policy patch verification skipped.")


if __name__ == "__main__":
    apply_policy_patch()
