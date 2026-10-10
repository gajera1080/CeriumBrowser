"""
Android Toolchain Timestamp Mutator (scripts/mutators/android/toolchain.py)
Allows secondary toolchains (such as webview) to import build/timestamp.gni
without assertion failure when enable_android_secondary_abi is false.
"""

import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    ctx.replace_in_src(
        "build/timestamp.gni",
        re.compile(
            r"[ \t]*if\s*\(\s*!enable_android_secondary_abi\s*\)\s*\{[^}]*"
            r"assert\s*\(\s*current_toolchain\s*==\s*default_toolchain[^)]*\)[^}]*\}"
        ),
        """  # In Braving, enable_android_secondary_abi is disabled for single-arch builds,
  # but secondary toolchains (such as webview) may still evaluate targets
  # that import timestamp.gni. Allow execution across all toolchains.
  not_needed([ "enable_android_secondary_abi" ])""",
    )
