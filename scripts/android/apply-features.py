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

# Determine brave_dir and src_dir
src_dir = None
for arg in sys.argv[2:]:
    if arg.startswith("--src-dir="):
        src_dir = arg.split("=", 1)[1]
        break

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

def replace_in_file(filepath, search, replacement, check_token=None):
    path = os.path.join(brave_dir, filepath)
    if not os.path.exists(path):
        msg = f"MISSING: {filepath}"
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if (check_token and check_token in content) or (isinstance(replacement, str) and replacement in content):
        print(f"Skipped {filepath} (already patched)")
        return

    if isinstance(search, str) and search in content:
        content = content.replace(search, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    elif hasattr(search, "search") and search.search(content):
        content = search.sub(lambda _: replacement, content, count=1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        pattern_str = search.pattern if hasattr(search, "pattern") else search
        msg = f"Search string not found in {filepath}: {pattern_str[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

def replace_in_src(filepath, search, replacement, check_token=None):
    if not src_dir:
        return
    path = os.path.join(src_dir, filepath)
    if not os.path.exists(path):
        msg = f"MISSING SRC: {filepath}"
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if (check_token and check_token in content) or (isinstance(replacement, str) and replacement in content):
        print(f"Skipped {filepath} (already patched)")
        return

    if isinstance(search, str) and search in content:
        content = content.replace(search, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    elif hasattr(search, "search") and search.search(content):
        content = search.sub(lambda _: replacement, content, count=1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        pattern_str = search.pattern if hasattr(search, "pattern") else search
        msg = f"Search string not found in {filepath}: {pattern_str[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

def _find_matching_gn_char(text, start_idx, open_char, close_char):
    depth = 0
    in_str = False
    escaped = False
    in_comment = False
    i = start_idx
    while i < len(text):
        ch = text[i]
        if in_comment:
            if ch == "\n":
                in_comment = False
        elif in_str:
            if ch == "\\" and not escaped:
                escaped = True
            elif ch == '"' and not escaped:
                in_str = False
            else:
                escaped = False
        else:
            if ch == "#":
                in_comment = True
            elif ch == '"':
                in_str = True
            elif ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1

def mutate_file(filepath, mutator_fn, in_src=False):
    base = src_dir if in_src else brave_dir
    if in_src and not src_dir:
        return
    path = os.path.join(base, filepath)
    if not os.path.exists(path):
        msg = f"{'MISSING SRC: ' if in_src else 'MISSING: '}{filepath}"
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    new_content, modified, found = mutator_fn(content)
    if modified:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"Patched {filepath}")
    elif found:
        print(f"Skipped {filepath} (already patched)")
    else:
        msg = f"Search string not found in {filepath}"
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

# 1. Silence Dart Sass legacy JS API deprecation warning in sass-loader
replace_in_file(
    "build/webpack/rules.ts",
    re.compile(r"\{\s*loader:\s*['\"]sass-loader['\"]\s*\},?"),
    "{ loader: 'sass-loader', options: { sassOptions: { silenceDeprecations: ['legacy-js-api'] } } },",
    check_token="silenceDeprecations: ['legacy-js-api']"
)

# 2. Silence wasm-pack version update notice
replace_in_file(
    "components/common/rust_to_wasm.gni",
    re.compile(r'"--log-level",\s*"warn",'),
    '"--log-level",\n      "error",',
    check_token='"--log-level",\n      "error",'
)

# 3. Consolidate desktop-only WebUI bundles and opaque_ke into include_polymer block
def _patch_webui_resources_build_gn(content):
    original_content = content
    m = re.search(r'\bgroup\s*\(\s*"grdp"\s*\)\s*\{', content)
    if not m:
        return content, False, False

    start = m.start()
    open_idx = m.end() - 1
    close_idx = _find_matching_gn_char(content, open_idx, "{", "}")
    if close_idx == -1:
        return content, False, False

    body = content[start : close_idx + 1]

    # Find unconditional public_deps inside group("grdp")
    m_deps = re.search(r'\bpublic_deps\s*=\s*\[', body)
    if not m_deps:
        return content, False, False
    d_open = m_deps.end() - 1
    d_close = _find_matching_gn_char(body, d_open, "[", "]")
    if d_close == -1:
        return content, False, False

    unconditional_deps = body[d_open + 1 : d_close]
    to_isolate = [":external_js_bundles", "resources/opaque_ke"]
    present_unconditional = [item for item in to_isolate if item in unconditional_deps]
    if not present_unconditional:
        if ":external_js_bundles" in body:
            return content, False, True

    deps_lines = unconditional_deps.splitlines()
    filtered_lines = [l for l in deps_lines if not any(item in l for item in to_isolate)]
    body = body[: d_open + 1] + "\n".join(filtered_lines) + "\n" + body[d_close:]

    m_poly = re.search(r'if\s*\(\s*include_polymer\s*\)\s*\{', body)
    if m_poly:
        p_open = m_poly.end() - 1
        p_close = _find_matching_gn_char(body, p_open, "{", "}")
        if p_close == -1:
            return original_content, False, False
        poly_body = body[p_open + 1 : p_close]
        m_pld = re.search(r'public_deps\s*\+=\s*\[', poly_body)
        if m_pld:
            pd_open = m_pld.end() - 1
            pd_close = _find_matching_gn_char(poly_body, pd_open, "[", "]")
            if pd_close == -1:
                return original_content, False, False
            before = poly_body[:pd_close].rstrip()
            last_char = before[-1:] if before else ""
            comma = "," if last_char not in (",", "[") else ""
            addition = comma + '\n      ":external_js_bundles",\n      "//brave/components/brave_account/resources/opaque_ke",'
            poly_body = before + addition + "\n    " + poly_body[pd_close:]
        else:
            return original_content, False, False
        body = body[: p_open + 1] + poly_body + body[p_close:]
    else:
        addition = """
  if (include_polymer) {
    public_deps += [
      ":build_grdp",
      ":external_js_bundles",
      "//brave/components/brave_account/resources/opaque_ke",
    ]
  }
"""
        body = body[:-1].rstrip() + "\n" + addition + "}"

    m_result_poly = re.search(r'if\s*\(\s*include_polymer\s*\)\s*\{', body)
    if not m_result_poly:
        return original_content, False, False
    result_poly_close = _find_matching_gn_char(body, m_result_poly.end() - 1, "{", "}")
    if result_poly_close == -1:
        return original_content, False, False
    result_poly_body = body[m_result_poly.end() : result_poly_close]
    if ":external_js_bundles" not in result_poly_body or "//brave/components/brave_account/resources/opaque_ke" not in result_poly_body:
        return original_content, False, False

    res = content[:start] + body + content[close_idx + 1 :]
    return res, True, True

mutate_file("ui/webui/resources/BUILD.gn", _patch_webui_resources_build_gn)

# 4. Consolidate desktop-only GRDPs into !is_android && !is_ios conditional in sources.gni
def _patch_webui_sources_gni(content):
    original_content = content
    m_arr = re.search(r'\bbrave_resources_extra_grdps\s*=\s*\[', content)
    if not m_arr:
        return content, False, False

    arr_open = m_arr.end() - 1
    arr_close = _find_matching_gn_char(content, arr_open, "[", "]")
    if arr_close == -1:
        return content, False, False

    unconditional_items = content[arr_open + 1 : arr_close]
    to_move = ["external_js.grdp", "opaque_ke.grdp"]

    if not any(item in unconditional_items for item in to_move):
        if "external_js.grdp" in content:
            return content, False, True

    arr_lines = unconditional_items.splitlines()
    filtered_lines = [l for l in arr_lines if not any(item in l for item in to_move)]
    content = content[: arr_open + 1] + "\n".join(filtered_lines) + "\n" + content[arr_close:]

    m_cond = re.search(r'if\s*\(\s*!is_android\s*&&\s*!is_ios\s*\)\s*\{', content)
    if m_cond:
        c_open = m_cond.end() - 1
        c_close = _find_matching_gn_char(content, c_open, "{", "}")
        if c_close == -1:
            return original_content, False, False
        cond_body = content[c_open + 1 : c_close]
        m_plus = re.search(r'brave_resources_extra_grdps\s*\+=\s*\[', cond_body)
        if m_plus:
            p_open = m_plus.end() - 1
            p_close = _find_matching_gn_char(cond_body, p_open, "[", "]")
            if p_close == -1:
                return original_content, False, False
            before = cond_body[:p_close].rstrip()
            last_char = before[-1:] if before else ""
            comma = "," if last_char not in (",", "[") else ""
            addition = comma + '\n    "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",\n    "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",'
            cond_body = before + addition + "\n  " + cond_body[p_close:]
        else:
            return original_content, False, False
        content = content[: c_open + 1] + cond_body + content[c_close:]
    else:
        addition = """

if (!is_android && !is_ios) {
  brave_resources_extra_grdps += [
    "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
    "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
  ]
}
"""
        m_arr2 = re.search(r'\bbrave_resources_extra_grdps\s*=\s*\[', content)
        if m_arr2:
            close2 = _find_matching_gn_char(content, m_arr2.end() - 1, "[", "]")
            if close2 != -1:
                content = content[: close2 + 1] + addition + content[close2 + 1 :]
            else:
                content += addition
        else:
            content += addition

    m_result_cond = re.search(r'if\s*\(\s*!is_android\s*&&\s*!is_ios\s*\)\s*\{', content)
    if not m_result_cond:
        return original_content, False, False
    result_cond_close = _find_matching_gn_char(content, m_result_cond.end() - 1, "{", "}")
    if result_cond_close == -1:
        return original_content, False, False
    result_cond_body = content[m_result_cond.end() : result_cond_close]
    if "external_js.grdp" not in result_cond_body or "opaque_ke.grdp" not in result_cond_body:
        return original_content, False, False

    return content, True, True

mutate_file("ui/webui/resources/sources.gni", _patch_webui_sources_gni)

# 5. Source Braving Shields icons from app/theme/brave/android/shields_drawables
#    instead of @brave/leo node_modules so Stage 1 (prepare-source.sh) handles all assets.
def _patch_nala_build_gn(content):
    has_outline = "ic_social_brave_outline_favicon_fullheight.xml" in content and "//brave/app/theme/brave/android/shields_drawables/" in content
    has_carved = "ic_social_brave_carved_favicon_fullheight.xml" in content and "//brave/app/theme/brave/android/shields_drawables/" in content
    has_monochrome = "ic_social_brave_monochrome_favicon_fullheight_color.xml" in content and "//brave/app/theme/brave/android/shields_drawables/" in content
    if has_outline and has_carved and has_monochrome:
        return content, False, True

    modified = False

    # 5a. Template syntax
    m_templ = re.search(r'template\s*\(\s*"nala_icon_override"\s*\)\s*\{', content)
    if m_templ:
        if "shields_drawables" not in content[m_templ.start() : m_templ.start() + 400]:
            pattern = re.compile(
                r'(_source\s*=\s*"\$nala_base_path/drawable/\$\{invoker\.source\}")',
                re.DOTALL
            )
            repl = """if (invoker.source == "ic_social_brave_outline_favicon_fullheight.xml") {
    _source = "//brave/app/theme/brave/android/shields_drawables/${invoker.source}"
  } else {
    _source = "$nala_base_path/drawable/${invoker.source}"
  }"""
            content, count = pattern.subn(repl, content, count=1)
            if count > 0:
                modified = True
    else:
        # 5b. Legacy copy(_name) syntax
        if "ic_social_brave_outline_favicon_fullheight.xml" not in content:
            pattern = re.compile(
                r'(\s*sources\s*=\s*\[\s*"\$nala_base_path/drawable/\$\{override\.source\}"\s*\])',
                re.DOTALL
            )
            repl = """
    if (override.source == "ic_social_brave_outline_favicon_fullheight.xml") {
      sources = [ "//brave/app/theme/brave/android/shields_drawables/${override.source}" ]
    } else {
      sources = [ "$nala_base_path/drawable/${override.source}" ]
    }"""
            content, count = pattern.subn(repl, content, count=1)
            if count > 0:
                modified = True

    # 5c. copy("nala_icons")
    if "ic_social_brave_carved_favicon_fullheight.xml" not in content:
        pattern = re.compile(
            r'(\s*sources\s*\+=\s*\[\s*["\']//brave/node_modules/@brave/leo/tokens/android/drawable/\$icon["\']\s*\])',
            re.DOTALL
        )
        repl = """
    if (icon == "ic_social_brave_carved_favicon_fullheight.xml" ||
        icon == "ic_social_brave_outline_favicon_fullheight.xml" ||
        icon == "ic_social_brave_release_favicon_fullheight_color.xml" ||
        icon == "ic_social_brave_monochrome_favicon_fullheight_color.xml") {
      sources += [ "//brave/app/theme/brave/android/shields_drawables/$icon" ]
    } else {
      sources +=
          [ "//brave/node_modules/@brave/leo/tokens/android/drawable/$icon" ]
    }"""
        content, count = pattern.subn(repl, content, count=1)
        if count > 0:
            modified = True
    elif "ic_social_brave_monochrome_favicon_fullheight_color.xml" not in content:
        if 'icon == "ic_social_brave_release_favicon_fullheight_color.xml"' in content:
            content = content.replace(
                'icon == "ic_social_brave_release_favicon_fullheight_color.xml"',
                'icon == "ic_social_brave_release_favicon_fullheight_color.xml" ||\n        icon == "ic_social_brave_monochrome_favicon_fullheight_color.xml"',
                1
            )
            modified = True

    if modified:
        return content, True, True
    return content, False, False

mutate_file("android/nala/BUILD.gn", _patch_nala_build_gn)

# 6. Register Braving mipmap-anydpi-v26 vector app icons in brave_base_module_resources
#    so //chrome/android:chrome_base_module_resources and
#    //chrome/android:chrome_public_apk_base_module_resources list all files in res_chromium_base.
def _patch_brave_java_resources_gni(content):
    if "mipmap-anydpi-v26/app_icon.xml" in content:
        return content, False, True
    m = re.search(r'\bbrave_base_module_resources\s*=\s*\[', content)
    if not m:
        return content, False, False
    bracket_open = m.end() - 1
    bracket_close = _find_matching_gn_char(content, bracket_open, "[", "]")
    if bracket_close == -1:
        return content, False, False
    items = content[bracket_open + 1 : bracket_close]
    extra_items = """
  "java/res_chromium_base/mipmap-anydpi-v26/app_icon.xml",
  "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon.xml",
  "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon_background.xml",
"""
    trimmed = items.rstrip()
    comma = "" if trimmed.endswith(",") else ","
    new_items = trimmed + comma + extra_items
    new_content = content[: bracket_open + 1] + new_items + content[bracket_close :]
    return new_content, True, True

mutate_file("android/brave_java_resources.gni", _patch_brave_java_resources_gni)

# 7. Point WebUI chrome_logo_dark.svg override in branding.js to app/theme/brave/product_logo.svg
#    instead of @brave/leo node_modules so WebUI pages use the colored Braving logo.
replace_in_file(
    "build/commands/lib/branding.js",
    re.compile(
        r"path\.join\(\s*config\.braveCoreDir,\s*['\"]node_modules['\"],\s*['\"]@brave['\"],\s*['\"]leo['\"],\s*['\"]icons['\"],\s*config\.getBraveLogoIconName\(\),?\s*\)",
        re.DOTALL
    ),
    """path.join(
      braveAppDir,
      'theme',
      'brave',
      'product_logo.svg',
    )""",
    check_token="'product_logo.svg'"
)

# 8. Rebrand home screen search widget logo to Brave search lion
replace_in_file(
    "android/java/brave-res/layout/quick_action_search_and_bookmark_widget_layout.xml",
    'android:src="@mipmap/app_icon"',
    'android:src="@drawable/brave_icon_search"'
)

# 9. Decouple omnibox quick search engines Brave Search logo from rebranded shields icon
# In upstream Brave, QuickSearchEnginesViewAdapter and QuickSearchEnginesAdapter use
# R.drawable.ic_social_brave_release_favicon_fullheight_color (which Braving rebrands to the
# shields icon). Re-point both adapters to Nala's native search icon (R.drawable.ic_brave_icon_search)
# provided via //brave/android/nala:java_resources.
# Note: Never bundle brave_icon_search.xml directly in quick_search_engines resources as that
# causes a fatal duplicate resource collision with //brave/android:java_resources in AAPT2 link.
replace_in_file(
    "browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/views/QuickSearchEnginesViewAdapter.java",
    re.compile(
        r'quickSearchViewHolder\.mSearchEngineLogo\.setImageResource\s*\(\s*'
        r'R\.drawable\.(?:ic_social_brave_release_favicon_fullheight_color|brave_icon_search)\s*\);'
    ),
    "quickSearchViewHolder.mSearchEngineLogo.setImageResource(\n                    R.drawable.ic_brave_icon_search);",
    check_token="R.drawable.ic_brave_icon_search"
)

replace_in_file(
    "browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/settings/QuickSearchEnginesAdapter.java",
    re.compile(
        r'quickSearchEnginesSettingsViewHolder\.mSearchEngineLogo\.setImageResource\s*\(\s*'
        r'R\.drawable\.(?:ic_social_brave_release_favicon_fullheight_color|brave_icon_search)\s*\);'
    ),
    "quickSearchEnginesSettingsViewHolder.mSearchEngineLogo.setImageResource(\n                    R.drawable.ic_brave_icon_search);",
    check_token="R.drawable.ic_brave_icon_search"
)

# Clean up any stale brave_icon_search.xml in quick_search_engines to prevent AAPT2 collision
qse_drawable_dir = os.path.join(brave_dir, "browser/quick_search_engines/android/java/res/drawable")
qse_icon = os.path.join(qse_drawable_dir, "brave_icon_search.xml")
if os.path.exists(qse_icon):
    os.remove(qse_icon)

# Revert any previously injected brave_icon_search.xml entry in quick_search_engines BUILD.gn
qse_build_gn = os.path.join(brave_dir, "browser/quick_search_engines/android/BUILD.gn")
if os.path.exists(qse_build_gn):
    with open(qse_build_gn, "r", encoding="utf-8") as f:
        gn_content = f.read()
    if '"java/res/drawable/brave_icon_search.xml"' in gn_content:
        gn_content = re.sub(r'[ \t]*"java/res/drawable/brave_icon_search\.xml",?\r?\n?', '', gn_content)
        with open(qse_build_gn, "w", encoding="utf-8") as f:
            f.write(gn_content)

# 10. Fix brave://flags blank screen by neutralizing broken legacy DOM mutations in brave_flags_overrides.js
# In Chromium 120+, flags-app was rewritten to Lit 3.0 (CrLitElement). Upstream Brave's legacy
# brave_flags_overrides.js from 2020 hooks into DOMContentLoaded and performs synchronous querySelector
# and .after() calls on shadow DOM elements ('div.blurb-container'), which throws an unhandled
# TypeError: Cannot read properties of null (reading 'after') and corrupts Lit's child parts,
# preventing <flags-app> from rendering and leaving brave://flags completely blank.
# Neutralize brave_flags_overrides.js to restore 100% native Lit rendering and remove Brave promo links.
replace_in_file(
    "components/flags_ui/resources/brave_flags_overrides.js",
    re.compile(r"document\.addEventListener\('DOMContentLoaded'[\s\S]*\}\);\s*"),
    "// Braving: Overrides disabled for clean Lit WebUI compatibility and complete de-branding.\n",
    check_token="// Braving: Overrides disabled for clean Lit WebUI compatibility"
)

# Neutralize IDR_FLAGS_UI_APP_JS concatenation in BraveContentClient::GetDataResourceBytes
# so native Lit 3.0 flags-app WebUI loads cleanly without Brave promo script injection.
replace_in_file(
    "common/brave_content_client.cc",
    re.compile(
        r"scoped_refptr<base::RefCountedMemory>\s+BraveContentClient::GetDataResourceBytes\(\s*"
        r"int resource_id\)\s*\{\s*"
        r"if\s*\(resource_id\s*==\s*IDR_FLAGS_UI_APP_JS\)\s*\{[\s\S]*?\}\s*"
        r"return ChromeContentClient::GetDataResourceBytes\(resource_id\);\s*\}"
    ),
    """scoped_refptr<base::RefCountedMemory> BraveContentClient::GetDataResourceBytes(
    int resource_id) {
  // Braving: Direct delegate to pure Chromium Lit WebUI resources without Brave promo injection
  return ChromeContentClient::GetDataResourceBytes(resource_id);
}""",
    check_token="// Braving: Direct delegate to pure Chromium Lit WebUI resources"
)

# 11. Ensure Client Hints and User-Agent always identify as standard modern Chrome
# across all websites, removing Brave brand leakage and version freezing.
replace_in_file(
    "chromium_src/components/embedder_support/user_agent_utils.cc",
    re.compile(r"constexpr\s+char\s+kBraveBrandNameForCHUA\[\]\s*=\s*\"Brave\";"),
    '[[maybe_unused]] constexpr char kBraveBrandNameForCHUA[] = "Brave";',
    check_token='[[maybe_unused]] constexpr char kBraveBrandNameForCHUA'
)
replace_in_file(
    "chromium_src/components/embedder_support/user_agent_utils.cc",
    re.compile(
        r"#define\s+BRAVE_GET_USER_AGENT_BRAND_LIST\s+brand\s*=\s*(?:kBraveBrandNameForCHUA|\"Google Chrome\");(?:\s*\(void\)kBraveBrandNameForCHUA;)?"
    ),
    '#define BRAVE_GET_USER_AGENT_BRAND_LIST brand = "Google Chrome"; (void)kBraveBrandNameForCHUA;',
    check_token='brand = "Google Chrome"; (void)kBraveBrandNameForCHUA;'
)
replace_in_file(
    "chromium_src/components/embedder_support/user_agent_utils.cc",
    re.compile(
        r"#define\s+BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE\s*\\\s*\n\s*"
        r"base::StrCat\(\s*\{\s*major_version\s*,\s*\"\.0\.0\.0\"\s*\}\s*\)"
    ),
    "#define BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE full_version",
    check_token="#define BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE full_version"
)

# Preserve full version fidelity in UserAgentMetadata instead of zeroing out last 3 version components
replace_in_file(
    "browser/brave_content_browser_client.cc",
    re.compile(
        r"blink::UserAgentMetadata\s+BraveContentBrowserClient::GetUserAgentMetadata\(\)\s*\{[\s\S]*?"
        r"metadata\.full_version\s*=\s*base::StrCat\([\s\S]*?\);\s*"
        r"return\s+metadata;\s*\}"
    ),
    """blink::UserAgentMetadata BraveContentBrowserClient::GetUserAgentMetadata() {
  // Braving: Return standard Chromium / Chrome UserAgentMetadata with full version fidelity
  return ChromeContentBrowserClient::GetUserAgentMetadata();
}""",
    check_token="// Braving: Return standard Chromium / Chrome UserAgentMetadata with full version fidelity"
)

# Always hide Brave brand across all domains so Braving consistently identifies as Chrome
replace_in_file(
    "components/brave_user_agent/browser/brave_user_agent_exceptions.cc",
    re.compile(
        r"bool\s+BraveUserAgentExceptions::CanShowBrave\s*\(\s*const\s+GURL&\s*url\s*\)\s*\{[\s\S]*?"
        r"return\s+!excepted_domains_\.contains\(domain\);\s*\}"
    ),
    """bool BraveUserAgentExceptions::CanShowBrave(const GURL& url) {
  // Braving: Never show Brave brand; always identify as standard Chrome
  (void)url;
  return false;
}""",
    check_token="// Braving: Never show Brave brand; always identify as standard Chrome"
)
replace_in_file(
    "components/brave_user_agent/browser/brave_user_agent_exceptions.cc",
    re.compile(
        r"bool\s+ShouldHideBraveBrand\s*\(\s*const\s+GURL&\s*url\s*\)\s*\{[\s\S]*?"
        r"return\s+exceptions\s*&&\s*!exceptions->CanShowBrave\(url\);\s*\}"
    ),
    """bool ShouldHideBraveBrand(const GURL& url) {
  // Braving: Always hide Brave brand across all domains
  (void)url;
  return true;
}""",
    check_token="// Braving: Always hide Brave brand across all domains"
)

# 12. Enable kBraveAdblockDefault1pBlocking by default so first-party ad blocking works cleanly in Standard Mode
replace_in_file(
    "components/brave_shields/core/common/features.cc",
    re.compile(
        r'BASE_FEATURE\(\s*kBraveAdblockDefault1pBlocking\s*,\s*base::FEATURE_DISABLED_BY_DEFAULT\s*\);'
    ),
    "BASE_FEATURE(kBraveAdblockDefault1pBlocking, base::FEATURE_ENABLED_BY_DEFAULT);",
    check_token="BASE_FEATURE(kBraveAdblockDefault1pBlocking, base::FEATURE_ENABLED_BY_DEFAULT);"
)

# 13. Clean APK and Settings version display (remove Chromium major version milestone from APK name)
explicit_src_dir = any(arg.startswith("--src-dir=") for arg in sys.argv[2:])
if explicit_src_dir or (src_dir and os.path.exists(os.path.join(src_dir, "chrome", "version.gni"))):
    replace_in_src(
        "chrome/version.gni",
        re.compile(r"^[ \t]*chrome_version_name\s*=\s*chrome_version_full\b", re.MULTILINE),
        """  declare_args() {
    chrome_version_name =
        "$chrome_version_minor.$chrome_version_build.$chrome_version_patch"
  }""",
        check_token="$chrome_version_minor.$chrome_version_build.$chrome_version_patch"
    )

    # Note: base/version_info/version_info_values.h.version and VersionConstants.java.version
    # define internal C++ and Java engine PRODUCT_VERSION, which Chromium strictly requires
    # to have 4 components (@MAJOR@.@MINOR@.@BUILD@.@PATCH@). Truncating @MAJOR@ breaks
    # version_info::GetVersion().components()[3] causing fatal SIGTRAP / brk #0x1 crashes
    # in paint_preview when backgrounding or closing tabs. If previously truncated, restore them.
    if src_dir:
        v_values = os.path.join(src_dir, "base/version_info/version_info_values.h.version")
        if os.path.exists(v_values):
            with open(v_values, "r", encoding="utf-8") as f:
                content = f.read()
            if '#define PRODUCT_VERSION "@MINOR@.@BUILD@.@PATCH@"' in content:
                content = content.replace(
                    '#define PRODUCT_VERSION "@MINOR@.@BUILD@.@PATCH@"',
                    '#define PRODUCT_VERSION "@MAJOR@.@MINOR@.@BUILD@.@PATCH@"'
                )
                with open(v_values, "w", encoding="utf-8") as f:
                    f.write(content)
                print("Restored 4-component PRODUCT_VERSION in base/version_info/version_info_values.h.version")

        v_consts = os.path.join(src_dir, "base/version_info/android/java/VersionConstants.java.version")
        if os.path.exists(v_consts):
            with open(v_consts, "r", encoding="utf-8") as f:
                content = f.read()
            if 'PRODUCT_VERSION = "@MINOR@.@BUILD@.@PATCH@"' in content:
                content = content.replace(
                    'PRODUCT_VERSION = "@MINOR@.@BUILD@.@PATCH@"',
                    'PRODUCT_VERSION = "@MAJOR@.@MINOR@.@BUILD@.@PATCH@"'
                )
                with open(v_consts, "w", encoding="utf-8") as f:
                    f.write(content)
                print("Restored 4-component PRODUCT_VERSION in base/version_info/android/java/VersionConstants.java.version")

    replace_in_src(
        "chrome/android/java/version_strings.xml.template",
        re.compile(r'<string\s+name="product_version"[^>]*>@MAJOR@\.@MINOR@\.@BUILD@\.@PATCH@</string>'),
        '  <string name="product_version" translatable="false" tools:ignore="UnusedResources">@MINOR@.@BUILD@.@PATCH@</string>',
        check_token='>@MINOR@.@BUILD@.@PATCH@</string>'
    )

    # Defensive bounds checking in Paint Preview version comparisons to prevent any future SIGTRAP / out-of-bounds crashes
    replace_in_src(
        "components/paint_preview/browser/paint_preview_client.cc",
        re.compile(
            r'const auto& current_chrome_version = version_info::GetVersion\(\);\s*'
            r'chromeVersion->set_major\(current_chrome_version\.components\(\)\[0\]\);\s*'
            r'chromeVersion->set_minor\(current_chrome_version\.components\(\)\[1\]\);\s*'
            r'chromeVersion->set_build\(current_chrome_version\.components\(\)\[2\]\);\s*'
            r'chromeVersion->set_patch\(current_chrome_version\.components\(\)\[3\]\);'
        ),
        """const auto& current_chrome_version = version_info::GetVersion();
  const auto& version_components = current_chrome_version.components();
  chromeVersion->set_major(version_components.size() > 0 ? version_components[0] : 0);
  chromeVersion->set_minor(version_components.size() > 1 ? version_components[1] : 0);
  chromeVersion->set_build(version_components.size() > 2 ? version_components[2] : 0);
  chromeVersion->set_patch(version_components.size() > 3 ? version_components[3] : 0);""",
        check_token="version_components.size() > 3"
    )

    replace_in_src(
        "components/paint_preview/player/player_compositor_delegate.cc",
        re.compile(
            r'const auto& current_chrome_version = version_info::GetVersion\(\);\s*'
            r'if \(capture_result_->proto\.metadata\(\)\.has_chrome_version\(\) &&\s*'
            r'chrome_version\.major\(\) == current_chrome_version\.components\(\)\[0\] &&\s*'
            r'chrome_version\.minor\(\) == current_chrome_version\.components\(\)\[1\] &&\s*'
            r'chrome_version\.build\(\) == current_chrome_version\.components\(\)\[2\] &&\s*'
            r'chrome_version\.patch\(\) == current_chrome_version\.components\(\)\[3\]\) \{'
        ),
        """const auto& current_chrome_version = version_info::GetVersion();
  const auto& version_components = current_chrome_version.components();
  if (capture_result_->proto.metadata().has_chrome_version() &&
      version_components.size() >= 4 &&
      chrome_version.major() == version_components[0] &&
      chrome_version.minor() == version_components[1] &&
      chrome_version.build() == version_components[2] &&
      chrome_version.patch() == version_components[3]) {""",
        check_token="version_components.size() >= 4"
    )


# 12. Silence GN unused variable errors in third_party/devtools-frontend files
# In Chromium / Brave <version>, public_inputs is assigned in ts_library_split.gni,
# front_end/models/ai_assistance/skills/BUILD.gn, and other DevTools frontend targets
# for remote execution environments, but unused in inspector_overlay and standard local/CI
# builds, triggering GN's strict "Assignment had no effect" error.
def _strip_gn_comments_and_strings(line):
    res = []
    in_str = False
    escaped = False
    for ch in line:
        if in_str:
            if ch == "\\" and not escaped:
                escaped = True
            elif ch == '"' and not escaped:
                in_str = False
            else:
                escaped = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '#':
                break
            else:
                res.append(ch)
    return "".join(res)

def silence_public_inputs_in_gn(content):
    lines = content.splitlines(keepends=True)
    new_lines = []
    i = 0
    modified = False
    found_any = False

    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([ \t]*)public_inputs\s*(\+?=)", line)
        if m:
            found_any = True
            indent = m.group(1)
            stmt_lines = [line]
            clean = _strip_gn_comments_and_strings(line)
            open_parens = clean.count("(") - clean.count(")")
            open_brackets = clean.count("[") - clean.count("]")
            open_braces = clean.count("{") - clean.count("}")
            stripped = clean.strip()
            ends_with_op = stripped.endswith("+") or stripped.endswith("=")

            while i + 1 < len(lines) and (open_parens > 0 or open_brackets > 0 or open_braces > 0 or ends_with_op):
                i += 1
                next_line = lines[i]
                stmt_lines.append(next_line)
                clean_next = _strip_gn_comments_and_strings(next_line)
                open_parens += clean_next.count("(") - clean_next.count(")")
                open_brackets += clean_next.count("[") - clean_next.count("]")
                open_braces += clean_next.count("{") - clean_next.count("}")
                stripped_next = clean_next.strip()
                ends_with_op = stripped_next.endswith("+") or stripped_next.endswith("=")

            new_lines.extend(stmt_lines)

            # Check if next statement already has not_needed([ "public_inputs" ])
            has_not_needed = False
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or lines[j].strip().startswith("#")):
                j += 1
            if j < len(lines) and "not_needed" in lines[j] and "public_inputs" in lines[j]:
                has_not_needed = True

            if not has_not_needed:
                newline = "\r\n" if line.endswith("\r\n") else "\n"
                new_lines.append(f"{indent}not_needed([ \"public_inputs\" ]){newline}")
                modified = True
        else:
            new_lines.append(line)
        i += 1

    return "".join(new_lines), modified, found_any

target_gn_files = [
    "third_party/devtools-frontend/src/scripts/build/typescript/ts_library_split.gni",
    "third_party/devtools-frontend/src/scripts/build/typescript/typescript.gni",
    "third_party/devtools-frontend/src/scripts/build/ninja/copy.gni",
    "third_party/devtools-frontend/src/scripts/build/ninja/devtools_pre_built.gni",
    "third_party/devtools-frontend/src/scripts/build/ninja/devtools_entrypoint.gni",
    "third_party/devtools-frontend/src/front_end/models/ai_assistance/skills/BUILD.gn",
]

if src_dir:
    for devtools_sub in ["third_party/devtools-frontend/src", "third_party/devtools-frontend"]:
        full_dir = os.path.join(src_dir, devtools_sub)
        if os.path.isdir(full_dir):
            for root, dirs, files in os.walk(full_dir):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "out", "target")]
                for file in files:
                    if file.endswith(".gni") or file == "BUILD.gn":
                        rel = os.path.relpath(os.path.join(root, file), src_dir)
                        if rel not in target_gn_files:
                            target_gn_files.append(rel)
            break

    for gn_rel in target_gn_files:
        gn_path = os.path.join(src_dir, gn_rel)
        if not os.path.exists(gn_path):
            continue
        with open(gn_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if "public_inputs" not in content:
            continue
        new_content, modified, found_any = silence_public_inputs_in_gn(content)
        if modified:
            with open(gn_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched {gn_rel} (silenced public_inputs)")
        elif found_any:
            print(f"Skipped {gn_rel} (already patched)")

# 13. Allow secondary toolchains (such as webview) to import build/timestamp.gni
# In Chromium / Brave <version>, timestamp.gni asserts current_toolchain == default_toolchain
# when enable_android_secondary_abi is false. In Braving, single-arch builds explicitly
# disable enable_android_secondary_abi, but secondary toolchains (such as
# android_clang_arm64_webview) pull in //components/policy:generated which imports
# timestamp.gni, triggering an assertion failure during gn gen.
if explicit_src_dir or (src_dir and os.path.exists(os.path.join(src_dir, "build", "timestamp.gni"))):
    replace_in_src(
        "build/timestamp.gni",
        re.compile(
            r"[ \t]*if\s*\(\s*!enable_android_secondary_abi\s*\)\s*\{[^}]*"
            r"assert\s*\(\s*current_toolchain\s*==\s*default_toolchain[^)]*\)[^}]*\}"
        ),
        """  # In Braving, enable_android_secondary_abi is disabled for single-arch builds,
  # but secondary toolchains (such as webview) may still evaluate targets
  # that import timestamp.gni. Allow execution across all toolchains.
  not_needed([ "enable_android_secondary_abi" ])""",
        check_token='not_needed([ "enable_android_secondary_abi" ])'
    )

# 14. Fix validate_expectations unresolved dependencies when secondary ABI is disabled
# In Chromium / Brave <version>, chrome/android/BUILD.gn declares group("validate_expectations")
# which unconditionally references 32-bit and dual-ABI (32_64, 64_32) trichrome and system_webview
# validation targets whenever enable_libs_and_assets_verification or enable_manifest_verification
# is true (e.g. in 64-bit official builds with stable channel). However, single-arch builds
# (such as Braving on ARM64) set enable_android_secondary_abi = false, which causes Chromium and
# android_webview BUILD.gn to skip generating those 32-bit / dual-ABI targets, resulting in
# "ERROR Unresolved dependencies: //chrome/android:validate_expectations needs ...".
# Semantically guard 32-bit and dual-ABI expectations with `if (defined(android_app_secondary_abi))`.
def patch_validate_expectations_in_gn(content):
    m = re.search(r'([ \t]*)group\s*\(\s*"validate_expectations"\s*\)\s*\{', content)
    if not m:
        return content, False, False

    start_idx = m.start()
    brace_open_idx = m.end() - 1
    group_indent = m.group(1)

    end_idx = _find_matching_gn_char(content, brace_open_idx, "{", "}")
    if end_idx == -1:
        return content, False, True

    group_text = content[start_idx : end_idx + 1]
    if "defined(android_app_secondary_abi)" in group_text:
        return content, False, True

    deps_matches = list(re.finditer(r"([ \t]*)deps\s*\+=\s*\[", group_text))
    if not deps_matches:
        return content, False, True

    new_group_text = group_text
    any_transformed = False

    for match in reversed(deps_matches):
        m_start = match.start()
        indent = match.group(1)
        bracket_open_idx = match.end() - 1
        bracket_close_idx = _find_matching_gn_char(new_group_text, bracket_open_idx, "[", "]")
        if bracket_close_idx == -1:
            continue

        items_block = new_group_text[bracket_open_idx + 1 : bracket_close_idx]
        lines = items_block.splitlines()
        primary_lines = []
        secondary_lines = []
        pending_comments = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                pending_comments.append(line)
                continue

            if "32" in stripped:
                secondary_lines.extend(pending_comments)
                pending_comments = []
                secondary_lines.append("  " + line if line.startswith(indent) else f"{indent}  {stripped}")
            else:
                primary_lines.extend(pending_comments)
                pending_comments = []
                primary_lines.append(line if line.startswith(indent) else f"{indent}{stripped}")

        primary_lines.extend(pending_comments)

        if not secondary_lines:
            continue

        replacement_parts = []
        if primary_lines:
            replacement_parts.append(f"{indent}deps += [\n")
            for pl in primary_lines:
                replacement_parts.append(f"{pl}\n")
            replacement_parts.append(f"{indent}]\n")

        replacement_parts.append(f"{indent}if (defined(android_app_secondary_abi)) {{\n")
        replacement_parts.append(f"{indent}  deps += [\n")
        for sl in secondary_lines:
            replacement_parts.append(f"{sl}\n")
        replacement_parts.append(f"{indent}  ]\n")
        replacement_parts.append(f"{indent}}}")

        rep_str = "".join(replacement_parts)
        new_group_text = new_group_text[:m_start] + rep_str + new_group_text[bracket_close_idx + 1 :]
        any_transformed = True

    if any_transformed:
        header = f"{group_indent}# In Braving, enable_android_secondary_abi is disabled for single-arch builds.\n{group_indent}# Only validate 32-bit and dual-ABI targets when secondary ABI is enabled.\n"
        new_group_text = header + new_group_text
        new_content = content[:start_idx] + new_group_text + content[end_idx + 1 :]
        return new_content, True, True

    return content, False, True


if explicit_src_dir or (src_dir and os.path.exists(os.path.join(src_dir, "chrome", "android", "BUILD.gn"))):
    if src_dir:
        ca_path = os.path.join(src_dir, "chrome", "android", "BUILD.gn")
        if not os.path.exists(ca_path):
            msg = "MISSING SRC: chrome/android/BUILD.gn"
            if STRICT:
                print(f"ERROR: {msg}", file=sys.stderr)
                sys.exit(1)
            print(f"WARNING: {msg}")
        else:
            with open(ca_path, "r", encoding="utf-8") as f:
                content = f.read()
            new_content, modified, found = patch_validate_expectations_in_gn(content)
            if modified:
                with open(ca_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print("Patched chrome/android/BUILD.gn")
            elif found:
                print("Skipped chrome/android/BUILD.gn (already patched)")
            else:
                msg = 'Search string not found in chrome/android/BUILD.gn: group("validate_expectations")...'
                if STRICT:
                    print(f"ERROR: {msg}", file=sys.stderr)
                    sys.exit(1)
                print(f"WARNING: {msg}")

print("Successfully applied GN build fixes!")
