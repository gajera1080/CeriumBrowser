#!/usr/bin/env python3
"""
Braving — Upstream Release & Dependency Version Resolver
Resolves strict, deterministic upstream release commits:
  BRAVE_VERSION -> exact brave-core release tag -> exact pinned Chromium revision
Generates upstream metadata (metadata/upstream-<version>.yaml), release manifest
(metadata/releases/<version>.yaml), and dotenv exports (build.env).
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import urllib.request
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def is_commit_sha(value) -> bool:
    return isinstance(value, str) and COMMIT_SHA_RE.fullmatch(value) is not None


def fetch_json(url: str, headers: dict = None, timeout: int = 15):
    hdrs = {"User-Agent": "Braving-CI", "Accept": "application/vnd.github+json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_latest_brave_release(repo_root: str):
    """Fetches latest stable release tag and Chromium version from GitHub."""
    # 1. Official latest release
    try:
        data = fetch_json("https://api.github.com/repos/brave/brave-browser/releases/latest")
        tag = data.get("tag_name", "").lstrip("v")
        name = (data.get("name") or "").strip()
        cr = ""
        if "(Chromium " in name:
            cr = name.split("(Chromium ")[1].rstrip(") ")
        if tag:
            return tag, cr
    except Exception as e:
        print(f"Note: releases/latest lookup failed: {e}", file=sys.stderr)

    # 2. Fallback: first 10 releases
    try:
        data = fetch_json("https://api.github.com/repos/brave/brave-browser/releases?per_page=10")
        if isinstance(data, list):
            for r in data:
                name = (r.get("name") or "").strip()
                if name.startswith("Release "):
                    tag = r["tag_name"].lstrip("v")
                    cr = ""
                    if "(Chromium " in name:
                        cr = name.split("(Chromium ")[1].rstrip(") ")
                    return tag, cr
    except Exception as e:
        print(f"Note: releases list lookup failed: {e}", file=sys.stderr)

    # 3. Fallback: local metadata
    meta_dirs = [os.path.join(repo_root, "metadata/releases"), os.path.join(repo_root, "metadata")]
    local_versions = []
    for mdir in meta_dirs:
        if os.path.isdir(mdir):
            for f in os.listdir(mdir):
                m = re.match(r"^(?:upstream-)?([0-9]+\.[0-9]+\.[0-9]+)\.yaml$", f)
                if m:
                    local_versions.append(m.group(1))
    if local_versions:
        return max(local_versions, key=lambda value: tuple(map(int, value.split(".")))), ""
    return "", ""


def resolve_brave_core_commit(version: str, local_brave: str) -> str:
    """Resolves commit hash for brave-core tag v<version>."""
    # Local git check
    if local_brave and os.path.isdir(os.path.join(local_brave, ".git")):
        try:
            return subprocess.check_output(
                ["git", "-C", local_brave, "rev-parse", f"refs/tags/v{version}^{{commit}}"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
        except Exception:
            pass

    # GitHub REST tag lookup
    try:
        data = fetch_json(f"https://api.github.com/repos/brave/brave-core/git/ref/tags/v{version}", timeout=10)
        obj = data.get("object", {})
        if obj.get("type") == "tag" and obj.get("url"):
            tag_data = fetch_json(obj["url"], timeout=10)
            sha = tag_data.get("object", {}).get("sha")
            if sha:
                return sha
        if obj.get("sha"):
            return obj["sha"]
    except Exception:
        pass

    # git ls-remote fallback
    try:
        out = subprocess.check_output(
            ["git", "ls-remote", "https://github.com/brave/brave-core.git", f"refs/tags/v{version}"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out:
            for line in out.splitlines():
                if line.endswith("^{}"):
                    return line.split()[0]
            return out.splitlines()[0].split()[0]
    except Exception:
        pass

    return ""


def resolve_chromium_version(version: str, local_brave: str) -> str:
    """Resolves pinned Chromium version string from brave-core package.json."""
    if local_brave:
        pkg_file = os.path.join(local_brave, "package.json")
        if os.path.isfile(pkg_file):
            try:
                with open(pkg_file, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
                if pkg_data.get("version") == version:
                    cr = pkg_data.get("config", {}).get("projects", {}).get("chrome", {}).get("tag")
                    if cr:
                        return cr
            except Exception:
                pass

    try:
        pkg_url = f"https://raw.githubusercontent.com/brave/brave-core/v{version}/package.json"
        req = urllib.request.Request(pkg_url, headers={"User-Agent": "Braving-Source-Prep"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pkg_data = json.loads(resp.read().decode("utf-8"))
            cr = pkg_data.get("config", {}).get("projects", {}).get("chrome", {}).get("tag")
            if cr:
                return cr
    except Exception as e:
        print(f"Note: package.json fetch failed: {e}", file=sys.stderr)

    return ""


def resolve_chromium_commit(chromium_version: str) -> str:
    """Resolves Chromium commit hash via Gitiles REST API or git ls-remote."""
    try:
        req = urllib.request.Request(
            f"https://chromium.googlesource.com/chromium/src/+/refs/tags/{chromium_version}?format=JSON",
            headers={"User-Agent": "Braving-CI"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            if raw.startswith(")]}'"):
                raw = raw[4:].strip()
            data = json.loads(raw)
            sha = data.get("commit")
            if sha:
                return sha
    except Exception:
        pass

    try:
        out = subprocess.check_output(
            ["git", "ls-remote", "https://chromium.googlesource.com/chromium/src.git", f"refs/tags/{chromium_version}"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
        if out:
            for line in out.splitlines():
                if line.endswith("^{}"):
                    return line.split()[0]
            return out.splitlines()[0].split()[0]
    except Exception:
        pass

    return ""


def write_manifests(repo_root: str, brave_version: str, brave_core_commit: str,
                    chromium_version: str, chromium_commit: str):
    """Writes upstream metadata and release manifest YAML files."""
    build_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    metadata_dir = os.path.join(repo_root, "metadata")
    releases_dir = os.path.join(metadata_dir, "releases")
    os.makedirs(releases_dir, exist_ok=True)

    upstream_data = {
        "release": {
            "brave_version": brave_version,
            "release_date": build_date,
        },
        "repositories": {
            "brave_core": {
                "url": "https://github.com/brave/brave-core.git",
                "tag": f"refs/tags/v{brave_version}",
                "commit": brave_core_commit,
                "mount_path": "src/brave",
            },
            "chromium": {
                "url": "https://chromium.googlesource.com/chromium/src.git",
                "tag": f"refs/tags/{chromium_version}",
                "version": chromium_version,
                "commit": chromium_commit,
                "mount_path": "src",
            },
            "depot_tools": {
                "url": "https://chromium.googlesource.com/chromium/tools/depot_tools.git",
                "mount_path": "src/brave/vendor/depot_tools",
                "behavior": {"disable_auto_update": True},
            },
        },
        "gn_arguments": {
            "base": {
                "target_os": "android",
                "target_cpu": "arm64",
                "is_debug": False,
                "is_official_build": True,
                "is_component_build": False,
                "symbol_level": 0,
                "disable_fieldtrial_testing_config": True,
            },
            "braving_overrides": {
                "chrome_public_manifest_package": "org.cerium.browser",
                "disable_android_lint": True,
                "target_android_output_format": "aab",
                "enable_resource_allowlist_generation": True,
            },
        },
    }

    release_data = {
        "braving_version": brave_version,
        "cerium_version": brave_version,
        "brave_version": brave_version,
        "brave_core_commit": brave_core_commit,
        "chromium_version": chromium_version,
        "chromium_commit": chromium_commit,
        "build_date": build_date,
        "package_id": "org.cerium.browser",
        "target_architecture": "arm64",
        "build_arguments": {
            "target_os": "android",
            "target_cpu": "arm64",
            "is_debug": False,
            "is_official_build": True,
            "is_component_build": False,
            "chrome_public_manifest_package": "org.cerium.browser",
            "disable_android_lint": True,
            "target_android_output_format": "aab",
            "enable_resource_allowlist_generation": True,
        },
    }

    upstream_file = os.path.join(metadata_dir, f"upstream-{brave_version}.yaml")
    with open(upstream_file, "w", encoding="utf-8") as f:
        yaml.dump(upstream_data, f, default_flow_style=False, sort_keys=False)

    release_file = os.path.join(releases_dir, f"{brave_version}.yaml")
    with open(release_file, "w", encoding="utf-8") as f:
        yaml.dump(release_data, f, default_flow_style=False, sort_keys=False)


def write_env_file(env_path: str, brave_version: str, brave_core_commit: str,
                   chromium_version: str, chromium_commit: str):
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(f"DYNAMIC_BRAVE_VERSION={brave_version}\n")
        f.write(f"DYNAMIC_BRAVE_CORE_COMMIT={brave_core_commit}\n")
        f.write(f"DYNAMIC_CHROMIUM_VERSION={chromium_version}\n")
        f.write(f"DYNAMIC_CHROMIUM_COMMIT={chromium_commit}\n")


def main():
    parser = argparse.ArgumentParser(description="Resolve upstream Brave and Chromium versions")
    parser.add_argument("version", nargs="?", default="", help="Brave version (e.g. 1.96.61)")
    parser.add_argument("--repo-root", default=DEFAULT_REPO_ROOT, help="Braving repository root")
    parser.add_argument("--local-brave", default=os.environ.get("BRAVE_CORE_DIR", "/run/media/pc/D/brave-core"))
    parser.add_argument("--env-file", default=None, help="Output dotenv file path")
    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    env_file = args.env_file or os.path.join(repo_root, "build.env")
    version = args.version.lstrip("v").strip()
    chromium_hint = os.environ.get("GITHUB_CHROMIUM_VERSION", "")

    if not version:
        version, chromium_hint = resolve_latest_brave_release(repo_root)
        if not version:
            print("ERROR: Could not resolve latest stable Brave version.", file=sys.stderr)
            sys.exit(1)
        print(f"Resolved latest stable: Brave v{version} (Chromium {chromium_hint})")

    # Check existing upstream metadata
    upstream_meta = os.path.join(repo_root, f"metadata/upstream-{version}.yaml")
    brave_core_commit = ""
    chromium_version = chromium_hint or ""
    chromium_commit = ""

    if os.path.isfile(upstream_meta):
        try:
            with open(upstream_meta, "r", encoding="utf-8") as f:
                cached = yaml.safe_load(f) or {}
            repositories = cached.get("repositories", {})
            brave_core_commit = repositories.get("brave_core", {}).get("commit", "")
            cached_chromium = repositories.get("chromium", {})
            cached_chromium_version = cached_chromium.get("version", "")
            chromium_version = chromium_version or cached_chromium_version
            if cached_chromium_version == chromium_version:
                chromium_commit = cached_chromium.get("commit", "")
        except Exception:
            pass

    if not brave_core_commit:
        brave_core_commit = resolve_brave_core_commit(version, args.local_brave)
        if not brave_core_commit:
            print(f"ERROR: Exact brave-core release tag v{version} commit could not be resolved.", file=sys.stderr)
            sys.exit(1)

    if not chromium_version:
        chromium_version = resolve_chromium_version(version, args.local_brave)
        if not chromium_version:
            print(f"ERROR: Could not resolve Chromium version for Brave {version}.", file=sys.stderr)
            sys.exit(1)

    if not is_commit_sha(chromium_commit):
        chromium_commit = resolve_chromium_commit(chromium_version)
    if not is_commit_sha(chromium_commit):
        print(f"ERROR: Exact Chromium tag {chromium_version} commit could not be resolved.", file=sys.stderr)
        sys.exit(1)

    write_manifests(repo_root, version, brave_core_commit, chromium_version, chromium_commit)
    write_env_file(env_file, version, brave_core_commit, chromium_version, chromium_commit)

    print("\nExact Pinned Specification:")
    print(f" - brave-core release tag : v{version}")
    print(f" - brave-core commit      : {brave_core_commit}")
    print(f" - Pinned Chromium tag    : {chromium_version}")
    print(f" - Pinned Chromium commit : {chromium_commit}")


if __name__ == "__main__":
    main()
