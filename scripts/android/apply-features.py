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


# 3. Consolidate desktop-only WebUI bundles and opaque_ke into include_polymer block
replace_in_file(
    "ui/webui/resources/BUILD.gn",
    """group("grdp") {
  public_deps = [
    ":external_js_bundles",
    ":fonts_grdp",
    ":icons_grdp",
    ":static_grdp",
    "//brave/components/brave_account/resources/opaque_ke",
  ]
  if (include_polymer) {
    public_deps += [ ":build_grdp" ]
  }
}""",
    """group("grdp") {
  public_deps = [
    ":fonts_grdp",
    ":icons_grdp",
    ":static_grdp",
  ]
  if (include_polymer) {
    public_deps += [
      ":build_grdp",
      ":external_js_bundles",
      "//brave/components/brave_account/resources/opaque_ke",
    ]
  }
}"""
)

# 4. Consolidate desktop-only GRDPs into !is_android && !is_ios conditional in sources.gni
replace_in_file(
    "ui/webui/resources/sources.gni",
    """brave_resources_extra_grdps = [
  "$brave_resources_extra_grdps_path/brave_fonts_resources.grdp",
  "$brave_resources_extra_grdps_path/brave_icons_resources.grdp",
  "$brave_resources_extra_grdps_path/brave_static_resources.grdp",
  "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
  "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
]

brave_resources_extra_grdps_deps = [ "//brave/ui/webui/resources:grdp" ]

# At the moment, all non-static resources are only required for polymer WebUI.
# This could change and, when it does, the `include_polymer` conditional can be
# removed here and the one in //brave/ui/webui/resources/BUILD.gn be relied on
# to only add polymer-related files when appropriate.
if (!is_android && !is_ios) {
  brave_resources_extra_grdps +=
      [ "$brave_resources_extra_grdps_path/resources.grdp" ]
}""",
    """brave_resources_extra_grdps = [
  "$brave_resources_extra_grdps_path/brave_fonts_resources.grdp",
  "$brave_resources_extra_grdps_path/brave_icons_resources.grdp",
  "$brave_resources_extra_grdps_path/brave_static_resources.grdp",
]

brave_resources_extra_grdps_deps = [ "//brave/ui/webui/resources:grdp" ]

# At the moment, all non-static resources are only required for polymer WebUI.
# This could change and, when it does, the `include_polymer` conditional can be
# removed here and the one in //brave/ui/webui/resources/BUILD.gn be relied on
# to only add polymer-related files when appropriate.
if (!is_android && !is_ios) {
  brave_resources_extra_grdps += [
    "$brave_resources_extra_grdps_path/resources.grdp",
    "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
    "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
  ]
}"""
)

# 5. Source Braving Shields icons from app/theme/brave/android/shields_drawables
#    instead of @brave/leo node_modules so Stage 1 (prepare-source.sh) handles all assets.
replace_in_file(
    "android/nala/BUILD.gn",
    """  copy(_name) {
    sources = [ "$nala_base_path/drawable/${override.source}" ]
    outputs = [ "$target_gen_dir/res/drawable/${override.dest}" ]
  }""",
    """  copy(_name) {
    if (override.source == "ic_social_brave_outline_favicon_fullheight.xml") {
      sources = [ "//brave/app/theme/brave/android/shields_drawables/${override.source}" ]
    } else {
      sources = [ "$nala_base_path/drawable/${override.source}" ]
    }
    outputs = [ "$target_gen_dir/res/drawable/${override.dest}" ]
  }"""
)

replace_in_file(
    "android/nala/BUILD.gn",
    """copy("nala_icons") {
  sources = []
  foreach(icon, nala_icons) {
    sources +=
        [ "//brave/node_modules/@brave/leo/tokens/android/drawable/$icon" ]
  }
  outputs = [ "$target_gen_dir/res/drawable/{{source_file_part}}" ]
}""",
    """copy("nala_icons") {
  sources = []
  foreach(icon, nala_icons) {
    if (icon == "ic_social_brave_carved_favicon_fullheight.xml" ||
        icon == "ic_social_brave_outline_favicon_fullheight.xml" ||
        icon == "ic_social_brave_release_favicon_fullheight_color.xml") {
      sources += [ "//brave/app/theme/brave/android/shields_drawables/$icon" ]
    } else {
      sources +=
          [ "//brave/node_modules/@brave/leo/tokens/android/drawable/$icon" ]
    }
  }
  outputs = [ "$target_gen_dir/res/drawable/{{source_file_part}}" ]
}"""
)

# 6. Register Braving mipmap-anydpi-v26 vector app icons in brave_base_module_resources
#    so //chrome/android:chrome_base_module_resources and
#    //chrome/android:chrome_public_apk_base_module_resources list all files in res_chromium_base.
replace_in_file(
    "android/brave_java_resources.gni",
    """brave_base_module_resources =
    [ "java/res_chromium_base/drawable-night/themed_app_icon.xml" ]""",
    """brave_base_module_resources = [
  "java/res_chromium_base/drawable-night/themed_app_icon.xml",
  "java/res_chromium_base/mipmap-anydpi-v26/app_icon.xml",
  "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon.xml",
  "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon_background.xml",
]"""
)

print("Successfully applied GN build fixes!")
