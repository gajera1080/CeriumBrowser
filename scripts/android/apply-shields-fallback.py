#!/usr/bin/env python3
"""
Braving — Shields Offline Rules Provisioning
Provisions bundled offline ad-blocking filter lists and catalog stubs
in components/brave_shields/resources/.

C++ fallback hooks, Grit definitions, and updater endpoints are maintained
declaratively via git patches (patches/android/0002-brave-shields-offline-fallback.patch).
Python scripting is used strictly for rule file provisioning per project guidelines.
"""
import sys
import os
import shutil
import subprocess

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")


# 0. Provision default offline rules and catalog stubs
res_dir = os.path.join(repo_root, "components/brave_shields/resources")
os.makedirs(res_dir, exist_ok=True)

# Sourced from local repo if available
resources_src = os.path.join(repo_root, "ios/brave-ios/Tests/ClientTests/Resources/ad-block-resources/resources.json")
target_resources = os.path.join(res_dir, "resources.json")
if not os.path.exists(target_resources):
    if os.path.exists(resources_src):
        shutil.copyfile(resources_src, target_resources)
        print(f"Copied {resources_src} to {target_resources}")
    else:
        with open(target_resources, "w", encoding="utf-8") as f:
            f.write("[]\n")
        print(f"Initialized stub {target_resources}")

catalog_file = os.path.join(res_dir, "list_catalog.json")
if not os.path.exists(catalog_file):
    with open(catalog_file, "w", encoding="utf-8") as f:
        f.write("""{
  "version": 1,
  "lists": [
    {
      "uuid": "default-offline-list",
      "name": "Braving Default Rules (uBlock Defaults)",
      "type": "ad-blocking",
      "desc": "Bundled offline rules based on uBlock Origin defaults",
      "filename": "default_rules.txt",
      "enabled_by_default": true
    }
  ]
}
""")
    print(f"Created {catalog_file}")

rule_files = {
    "default_rules.txt": "! Braving default offline ad-blocking rules\n! Sourced from uBlock Origin & EasyList\n||googleads.g.doubleclick.net^\n||pagead2.googlesyndication.com^\n",
    "tracker_rules.txt": "! Braving default offline tracker rules\n! Sourced from EasyPrivacy\n||google-analytics.com^\n",
    "first_party_rules.txt": "! Braving offline first-party rules\n",
    "cookie_rules.txt": "! Braving offline cookie rules\n",
    "mobile_rules.txt": "! Braving offline mobile rules\n"
}

for fname, default_content in rule_files.items():
    fpath = os.path.join(res_dir, fname)
    if not os.path.exists(fpath):
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(default_content)
        print(f"Created rule file: {fpath}")


# 1. Verify / ensure Shields offline fallback patch is in place
def ensure_shields_patch_applied():
    git_dir = os.path.join(repo_root, ".git")
    if os.path.isdir(git_dir):
        patch_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../patches/android/0002-brave-shields-offline-fallback.patch"))
        if not os.path.isfile(patch_path):
            print(f"Note: Shields patch not found at {patch_path}")
            return

        res_rev = subprocess.run(["git", "-C", repo_root, "apply", "--check", "--reverse", patch_path], capture_output=True)
        if res_rev.returncode == 0:
            print("Shields offline fallback patch already applied (Skipped)")
            return
        res_fwd = subprocess.run(["git", "-C", repo_root, "apply", "--check", patch_path], capture_output=True)
        if res_fwd.returncode == 0:
            subprocess.run(["git", "-C", repo_root, "apply", patch_path], check=True)
            print("Applied 0002-brave-shields-offline-fallback.patch")
            return
        if STRICT:
            print("ERROR: 0002-brave-shields-offline-fallback.patch failed to apply", file=sys.stderr)
            sys.exit(1)
    else:
        print("Note: Target is not a git repository; shields patch verification skipped.")


if __name__ == "__main__":
    ensure_shields_patch_applied()
