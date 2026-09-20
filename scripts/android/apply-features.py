#!/usr/bin/env python3
# Braving — GN Build Fix Mutators
# These handle conditional GN array modifications that standard git patches
# cannot do safely across upstream version bumps.
# C++ and XML modifications are handled by git patches in patches/android/.

import sys
import os
import re

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")

def replace_in_file(filepath, search, replacement):
    path = os.path.join(repo_root, filepath)
    if not os.path.exists(path):
        msg = f"MISSING: {filepath}"
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if replacement in content:
        print(f"Skipped {filepath} (already patched)")
        return

    if search in content:
        content = content.replace(search, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        msg = f"Search string not found in {filepath}: {search[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

def replace_regex_in_file(filepath, pattern, replacement):
    path = os.path.join(repo_root, filepath)
    if not os.path.exists(path):
        msg = f"MISSING: {filepath}"
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # If the pattern is not found, assume it was already patched/removed
    if not re.search(pattern, content):
        print(f"Skipped {filepath} (pattern not found, assuming already patched)")
        return

    new_content, count = re.subn(pattern, replacement, content, count=1)
    if count > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Patched {filepath}")
    else:
        msg = f"Regex pattern not found in {filepath}: {pattern[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

# 1. Silence Dart Sass legacy JS API deprecation warning in sass-loader
replace_in_file(
    "build/webpack/rules.ts",
    "{ loader: 'sass-loader' },",
    "{ loader: 'sass-loader', options: { sassOptions: { silenceDeprecations: ['legacy-js-api'] } } },"
)

# 2. Silence wasm-pack version update notice
replace_in_file(
    "components/common/rust_to_wasm.gni",
    '"--log-level",\n      "warn",',
    '"--log-level",\n      "error",'
)

# 3. Fix GN circular includes error for notifications when brave_ads is disabled
replace_regex_in_file(
    "browser/sources.gni",
    r'(\s*)"//brave/browser/notifications",\n(\s*)\]',
    r'\n\2]\n\2if (enable_brave_ads) {\n\2  brave_chrome_browser_allow_circular_includes_from += [\n\2    "//brave/browser/notifications",\n\2  ]\n\2}'
)

# 4. Fix GN list subtraction error for brave_news test when brave_news is disabled
replace_regex_in_file(
    "android/android_browser_tests.gni",
    r'(\s*)"//brave/browser/brave_news:browser_tests",\n',
    r''
)

# 5. Fix GN assertion failure for ai_chat when enable_ai_chat is disabled
replace_regex_in_file(
    "browser/android/BUILD.gn",
    r'(\s*)"//brave/browser/ai_chat",\n',
    r''
)

# 6. Fix GN Unresolved dependencies for brave_news in Android preferences
replace_regex_in_file(
    "browser/android/preferences/BUILD.gn",
    r'(\s*)"//brave/components/brave_news/common",\n',
    r''
)
replace_regex_in_file(
    "browser/android/preferences/BUILD.gn",
    r'(\s*)"//brave/components/brave_news/common/pref_names\.h",\n',
    r''
)
# 7. Fix GN missing ic_brave_logo.xml because it was replaced by pngs
replace_in_file(
    "android/BUILD.gn",
    '    "java/brave-res/drawable/ic_brave_logo.xml",\n',
    '    "java/brave-res/drawable-mdpi/ic_brave_logo.png",\n    "java/brave-res/drawable-hdpi/ic_brave_logo.png",\n    "java/brave-res/drawable-xhdpi/ic_brave_logo.png",\n    "java/brave-res/drawable-xxhdpi/ic_brave_logo.png",\n    "java/brave-res/drawable-xxxhdpi/ic_brave_logo.png",\n'
)

print("Successfully applied GN build fixes!")
