"""
Braving Mutator Runner (scripts/mutators/runner.py)
Orchestrates component-based mutators across common and platform-specific targets.
"""

import os
import sys
from scripts.mutators.context import MutatorContext
from scripts.mutators.common import ALL_COMMON_MUTATORS
from scripts.mutators.android import ALL_ANDROID_MUTATORS


def run_mutators(args: list) -> int:
    if not args:
        print("Usage: runner.py <path-to-brave-core> [--strict] [--src-dir=...] [--target-os=...]", file=sys.stderr)
        return 1

    repo_root = args[0]
    strict = "--strict" in args or bool(os.environ.get("CI"))

    src_dir = None
    target_os = "android"
    explicit_src_dir = False

    for arg in args[1:]:
        if arg.startswith("--src-dir="):
            src_dir = arg.split("=", 1)[1]
            explicit_src_dir = True
        elif arg.startswith("--target-os="):
            target_os = arg.split("=", 1)[1]

    # Auto-resolve brave_dir and src_dir if not explicitly set
    brave_dir = repo_root
    if os.path.basename(os.path.abspath(repo_root)) == "brave":
        brave_dir = repo_root
        if not src_dir and os.path.isdir(os.path.join(repo_root, "..", "chrome")):
            src_dir = os.path.abspath(os.path.join(repo_root, ".."))
    elif os.path.isdir(os.path.join(repo_root, "brave")):
        brave_dir = os.path.join(repo_root, "brave")
        if not src_dir and os.path.isdir(os.path.join(repo_root, "chrome")):
            src_dir = os.path.abspath(repo_root)
    elif not src_dir and os.path.isdir(os.path.join(repo_root, "..", "chrome")):
        src_dir = os.path.abspath(os.path.join(repo_root, ".."))

    ctx = MutatorContext(
        brave_dir=brave_dir,
        src_dir=src_dir,
        strict=strict,
        target_os=target_os,
        explicit_src_dir=explicit_src_dir,
    )

    # 1. Run cross-platform mutators
    for mutator in ALL_COMMON_MUTATORS:
        mutator.apply(ctx)

    # 2. Run target-specific mutators
    if target_os == "android":
        for mutator in ALL_ANDROID_MUTATORS:
            mutator.apply(ctx)

    print("Successfully applied GN build fixes!")
    return 0
