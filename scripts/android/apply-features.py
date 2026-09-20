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


print("Successfully applied GN build fixes!")

# 8. Fix external_js_bundles crash on Android by removing it from unconditional GN block
replace_regex_in_file(
    "ui/webui/resources/BUILD.gn",
    r'\s*":external_js_bundles",\n',
    r'\n'
)

# 8c. Remove external_js.grdp from unconditional sources
replace_regex_in_file(
    "ui/webui/resources/sources.gni",
    r'\s*"\$root_gen_dir/brave/web-ui-external_js/external_js\.grdp",\n',
    r'\n'
)
# 8d. Add it to the !is_android block
replace_in_file(
    "ui/webui/resources/sources.gni",
    '      [ "$brave_resources_extra_grdps_path/resources.grdp" ]',
    '      [\n        "$brave_resources_extra_grdps_path/resources.grdp",\n        "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",\n      ]'
)

# 9. Also remove opaque_ke to prevent similar Android errors
replace_regex_in_file(
    "ui/webui/resources/BUILD.gn",
    r'\s*"//brave/components/brave_account/resources/opaque_ke",\n',
    r'\n'
)

# 9b. Add both to include_polymer block in BUILD.gn
replace_in_file(
    "ui/webui/resources/BUILD.gn",
    '    public_deps += [ ":build_grdp" ]',
    '    public_deps += [\n      ":build_grdp",\n      ":external_js_bundles",\n      "//brave/components/brave_account/resources/opaque_ke",\n    ]'
)

# 9c. Remove opaque_ke.grdp from unconditional sources
replace_regex_in_file(
    "ui/webui/resources/sources.gni",
    r'\s*"\$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke\.grdp",\n',
    r'\n'
)
# 9d. Add it to the !is_android block
replace_in_file(
    "ui/webui/resources/sources.gni",
    '        "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",\n      ]',
    '        "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",\n        "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",\n      ]'
)
