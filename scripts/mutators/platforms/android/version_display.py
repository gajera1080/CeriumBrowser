"""
Android Version Display Mutator (scripts/mutators/android/version_display.py)
Removes Chromium major version milestone from APK name and Settings product version string.
"""

import os
import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    if ctx.has_chromium_src():
        ctx.replace_in_src(
            "chrome/version.gni",
            re.compile(r"^[ \t]*chrome_version_name\s*=\s*chrome_version_full\b", re.MULTILINE),
            """  declare_args() {
    chrome_version_name =
        "$chrome_version_minor.$chrome_version_build.$chrome_version_patch"
  }""",
        )

        ctx.replace_in_src(
            "chrome/android/java/version_strings.xml.template",
            re.compile(r'<string\s+name="product_version"[^>]*>@MAJOR@\.@MINOR@\.@BUILD@\.@PATCH@</string>'),
            '  <string name="product_version" translatable="false" tools:ignore="UnusedResources">@MINOR@.@BUILD@.@PATCH@</string>',
        )
