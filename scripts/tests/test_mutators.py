#!/usr/bin/env python3
"""
Braving Test Suite: Python Mutators and Git Patch Suite
Validates that:
1. Dynamic GN array mutators (apply-features.py) execute properly and idempotently.
2. Shields offline rules provisioning (apply-shields-fallback.py) creates all required files.
3. Debloat policy enforcement (enforce-policies.py) executes cleanly.
4. Git patch suite (0001, 0002, 0003) applies cleanly and complies with all compiler fixes.
"""

import os
import sys
import tempfile
import subprocess
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def test_apply_features():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Setup mock files for apply-features
        webpack_rules = os.path.join(tmpdir, "build/webpack/rules.ts")
        rust_wasm = os.path.join(tmpdir, "components/common/rust_to_wasm.gni")
        webui_build_gn = os.path.join(tmpdir, "ui/webui/resources/BUILD.gn")
        webui_sources_gni = os.path.join(tmpdir, "ui/webui/resources/sources.gni")
        nala_build_gn = os.path.join(tmpdir, "android/nala/BUILD.gn")
        brave_java_res_gni = os.path.join(tmpdir, "android/brave_java_resources.gni")
        branding_js = os.path.join(tmpdir, "build/commands/lib/branding.js")

        for p in [webpack_rules, rust_wasm, webui_build_gn, webui_sources_gni, nala_build_gn, brave_java_res_gni, branding_js]:
            os.makedirs(os.path.dirname(p), exist_ok=True)

        with open(webpack_rules, "w") as f:
            f.write("{ loader: 'sass-loader' },\n")

        with open(rust_wasm, "w") as f:
            f.write('"--log-level",\n      "warn",\n')

        with open(webui_build_gn, "w") as f:
            f.write("""group("grdp") {
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
}
""")

        with open(webui_sources_gni, "w") as f:
            f.write("""brave_resources_extra_grdps = [
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
}
""")

        with open(nala_build_gn, "w") as f:
            f.write("""_nala_override_deps = []
foreach(override, nala_icon_overrides) {
  _name = "nala_override_" + string_replace(override.dest, ".xml", "")
  copy(_name) {
    sources = [ "$nala_base_path/drawable/${override.source}" ]
    outputs = [ "$target_gen_dir/res/drawable/${override.dest}" ]
  }
  _nala_override_deps += [ ":$_name" ]
}

copy("nala_icons") {
  sources = []
  foreach(icon, nala_icons) {
    sources +=
        [ "//brave/node_modules/@brave/leo/tokens/android/drawable/$icon" ]
  }
  outputs = [ "$target_gen_dir/res/drawable/{{source_file_part}}" ]
}
""")

        with open(brave_java_res_gni, "w") as f:
            f.write("""brave_base_module_resources =
    [ "java/res_chromium_base/drawable-night/themed_app_icon.xml" ]
""")

        with open(branding_js, "w") as f:
            f.write("""  // Replace chrome dark logo with channel specific brave logo.
  fileMap.add([
    path.join(
      config.braveCoreDir,
      'node_modules',
      '@brave',
      'leo',
      'icons',
      config.getBraveLogoIconName(),
    ),
    path.join(
      config.srcDir,
      'ui',
      'webui',
      'resources',
      'images',
      'chrome_logo_dark.svg',
    ),
  ])
""")

        script = os.path.join(REPO_ROOT, "scripts/android/apply-features.py")
        res = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res.returncode == 0, f"apply-features failed: {res.stderr}\n{res.stdout}"

        # Check modifications
        with open(webpack_rules) as f:
            assert "silenceDeprecations" in f.read()

        with open(rust_wasm) as f:
            assert '"--log-level",\n      "error",' in f.read()

        with open(webui_build_gn) as f:
            c = f.read()
            assert ":external_js_bundles" not in c.split("if (include_polymer)")[0]
            assert ":external_js_bundles" in c.split("if (include_polymer)")[1]

        with open(webui_sources_gni) as f:
            c = f.read()
            assert "if (!is_android && !is_ios) {" in c

        with open(nala_build_gn) as f:
            c = f.read()
            assert "//brave/app/theme/brave/android/shields_drawables/" in c

        with open(brave_java_res_gni) as f:
            c = f.read()
            assert "java/res_chromium_base/mipmap-anydpi-v26/app_icon.xml" in c
            assert "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon.xml" in c
            assert "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon_background.xml" in c

        with open(branding_js) as f:
            c = f.read()
            assert "'product_logo.svg'" in c

        # Verify idempotence
        res_idem = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"apply-features idempotence failed: {res_idem.stderr}"
        assert "Skipped" in res_idem.stdout

        print("PASS: test_apply_features")


def test_patch_suite():
    patch_dir = os.path.join(REPO_ROOT, "patches")
    patches = []
    if os.path.exists(patch_dir):
        for root, _, files in os.walk(patch_dir):
            for f in sorted(files):
                if f.endswith(".patch"):
                    patches.append(os.path.join(root, f))
    assert len(patches) >= 7, f"Expected at least 7 modular patches, found {len(patches)}"
    for p in patches:
        assert os.path.getsize(p) > 50, f"Patch {p} is suspiciously small"

    # Ensure monolithic 0003 patch is retired in favor of patches/android/debloat/
    old_0003 = os.path.join(REPO_ROOT, "patches/android/0003-enforce-debloat-policies.patch")
    assert not os.path.exists(old_0003), f"Monolithic patch should be split into patches/android/debloat/: {old_0003}"

    # Verify 0001 branding patch (release-only)
    patch_0001 = os.path.join(REPO_ROOT, "patches/android/0001-braving-branding.patch")
    assert os.path.isfile(patch_0001), f"Missing patch file: {patch_0001}"
    with open(patch_0001, "r", encoding="utf-8") as f:
        c0001 = f.read()
    assert "app/theme/brave/BRANDING" in c0001
    assert "app/theme/brave/BRANDING." not in c0001, "Dev/Beta/Nightly BRANDING files should not be in 0001"
    assert "PRODUCT_FULLNAME=Braving Browser" in c0001
    assert "PRODUCT_SHORTNAME=Braving" in c0001
    assert 'Braving - Debug' not in c0001, "Found Debug suffix in 0001-braving-branding.patch"
    assert '<string name="app_name" translatable="false">Braving</string>' in c0001
    assert "ic_social_brave_release_favicon_fullheight_color" in c0001
    assert "ic_social_brave_outline_favicon_fullheight" in c0001
    assert "R.mipmap.layered_app_icon" in c0001
    assert "R.mipmap.layered_app_icon_background" in c0001
    assert "R.drawable.btn_brave" in c0001
    assert "R.drawable.btn_brave_off" in c0001

    # Verify 0002 custom updater endpoint patch (release-only)
    patch_0002 = os.path.join(REPO_ROOT, "patches/android/0002-custom-updater-endpoint.patch")
    assert os.path.isfile(patch_0002), f"Missing patch file: {patch_0002}"
    with open(patch_0002, "r", encoding="utf-8") as f:
        c0002 = f.read()
    assert 'https://updates.braving.org/components' in c0002
    assert '+  updater_prod_endpoint = "https://updates.braving.org/components"' in c0002
    assert '+  updater_dev_endpoint' not in c0002

    # Verify modular debloat patches in patches/android/debloat/
    debloat_dir = os.path.join(REPO_ROOT, "patches/android/debloat")
    assert os.path.isdir(debloat_dir), f"Missing debloat patch directory: {debloat_dir}"

    p_flag = os.path.join(debloat_dir, "0001-hide-brave-origin-flag.patch")
    with open(p_flag, "r", encoding="utf-8") as f:
        c_flag = f.read()
    assert "BASE_FEATURE(kBraveOrigin, base::FEATURE_DISABLED_BY_DEFAULT);" in c_flag

    p_backend = os.path.join(debloat_dir, "0002-unlock-brave-origin-backend.patch")
    with open(p_backend, "r", encoding="utf-8") as f:
        c_backend = f.read()
    assert "brave_origin_policy_manager.cc" in c_backend
    assert "brave_origin_service.cc" in c_backend
    assert "brave_origin_utils.cc" in c_backend
    assert "return manager->IsInitialized();" in c_backend

    p_android_origin = os.path.join(debloat_dir, "0003-unlock-brave-origin-android-prefs.patch")
    with open(p_android_origin, "r", encoding="utf-8") as f:
        c_android_origin = f.read()
    assert "BraveOriginSubscriptionPrefs.java" in c_android_origin
    assert "getIsCredentialSummaryActiveCached" in c_android_origin
    assert "getIsSubscriptionActive" in c_android_origin

    p_policies = os.path.join(debloat_dir, "0004-enforce-enterprise-policies.patch")
    with open(p_policies, "r", encoding="utf-8") as f:
        c_policies = f.read()
    assert "RefreshPolicies(policy::PolicyFetchReason::kBrowserStart);" in c_policies
    assert 'enforce("MetricsReportingEnabled", false);' in c_policies
    assert 'enforce("BraveP3AEnabled", false);' in c_policies
    assert 'enforce("BraveStatsPingEnabled", false);' in c_policies
    assert 'enforce("BraveWalletDisabled", true);' in c_policies
    assert 'enforce("BraveVPNDisabled", true);' in c_policies
    assert 'enforce("BraveAIChatEnabled", false);' in c_policies

    p_adblock = os.path.join(debloat_dir, "0005-default-adblock-subscriptions.patch")
    with open(p_adblock, "r", encoding="utf-8") as f:
        c_adblock = f.read()
    assert "base::Value::Dict" not in c_adblock, "Deprecated base::Value::Dict found; use base::DictValue"
    assert "base::DictValue" in c_adblock
    assert 'sub.Set("last_update_attempt", "0")' in c_adblock
    assert "SetFilterListCatalog({})" in c_adblock
    assert "!subscription_filters_providers_.contains(sub_url)" in c_adblock
    assert "info.last_successful_update_attempt.is_null()" in c_adblock

    # Dynamic brave-core detection: check BRAVE_CORE_DIR, build-workspace, or /run/media/pc/D/brave-core
    brave_core = os.environ.get("BRAVE_CORE_DIR", "")
    if not (brave_core and os.path.isdir(os.path.join(brave_core, ".git"))):
        workspace_brave = os.path.join(REPO_ROOT, "build-workspace/src/brave")
        if os.path.isdir(os.path.join(workspace_brave, ".git")):
            brave_core = workspace_brave
        elif os.path.isdir("/run/media/pc/D/brave-core/.git"):
            brave_core = "/run/media/pc/D/brave-core"

    if brave_core and os.path.isdir(os.path.join(brave_core, ".git")):
        for p in patches:
            cmd = ["git", "-C", brave_core, "apply", "--check", p]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                cmd_rev = ["git", "-C", brave_core, "apply", "--check", "--reverse", p]
                res_rev = subprocess.run(cmd_rev, capture_output=True, text=True)
                if res_rev.returncode != 0:
                    cmd_c1 = ["git", "-C", brave_core, "apply", "-C1", "--check", p]
                    res_c1 = subprocess.run(cmd_c1, capture_output=True, text=True)
                    if res_c1.returncode != 0:
                        cmd_c1_rev = ["git", "-C", brave_core, "apply", "-C1", "--check", "--reverse", p]
                        res_c1_rev = subprocess.run(cmd_c1_rev, capture_output=True, text=True)
                        assert res_c1_rev.returncode == 0, f"Patch {os.path.basename(p)} failed to apply: {res.stderr}"

    print("PASS: test_patch_suite")


def test_apply_branding():
    import importlib.util
    script_path = os.path.join(REPO_ROOT, "scripts/android/apply-branding.py")
    spec = importlib.util.spec_from_file_location("apply_branding", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory() as tmpdir:
        grd_dir = os.path.join(tmpdir, "browser/ui/android/strings")
        xtb_dir = os.path.join(grd_dir, "translations")
        pref_dir = os.path.join(tmpdir, "android/java/res/xml")
        os.makedirs(xtb_dir, exist_ok=True)
        os.makedirs(pref_dir, exist_ok=True)

        grd_path = os.path.join(grd_dir, "android_brave_strings.grd")
        part_path = os.path.join(grd_dir, "sub_strings.grdp")
        xtb_path = os.path.join(xtb_dir, "android_brave_strings_es.xtb")
        pref_path = os.path.join(pref_dir, "developer_preferences.xml")

        import xml.etree.ElementTree as ET
        old_fp_1 = mod.get_fingerprint_for_xtb(ET.fromstring("<message>Welcome to Brave</message>"))
        new_fp_1 = mod.get_fingerprint_for_xtb(ET.fromstring("<message>Welcome to Braving</message>"))

        old_fp_2 = mod.get_fingerprint_for_xtb(
            ET.fromstring('<message>Brave Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Brave 1.0</ex></ph></message>')
        )
        new_fp_2 = mod.get_fingerprint_for_xtb(
            ET.fromstring('<message>Braving Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Braving 1.0</ex></ph></message>')
        )

        with open(part_path, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<grit-part>
  <message name="IDS_SHIELDS_PRIVACY" desc="Shields label">
    Brave Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Brave 1.0</ex></ph>
  </message>
</grit-part>
""")

        with open(grd_path, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<grit latest_public_release="0" current_release="1">
  <outputs>
    <output filename="values/android_brave_strings.xml" lang="en" type="android" />
  </outputs>
  <translations>
    <file path="translations/android_brave_strings_es.xtb" lang="es" />
  </translations>
  <release seq="1">
    <messages fallback_to_english="true">
      <part file="sub_strings.grdp" />
      <message name="IDS_WELCOME_BRAVE" desc="Welcome">Welcome to Brave</message>
      <message name="IDS_CHROME_HISTORY" desc="History menu item">Brave history</message>
      <message name="IDS_JAVASCRIPT_OPT" desc="Protects against malicious actors">Brave runs faster</message>
      <message name="IDS_BRAVE_SEARCH_DESC" desc="Search">Try Brave Search at https://search.brave.com or brave://settings in Brave</message>
      <message name="IDS_BRAVE_WALLET_TITLE" desc="Wallet bloat">Brave Wallet</message>
      <message name="IDS_AI_CHAT_INTRO" desc="Leo bloat">Ask Brave Leo AI</message>
      <message name="IDS_TOR_STATUS" desc="Tor bloat">Brave Tor</message>
    </messages>
  </release>
</grit>
""")

        with open(xtb_path, "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" ?>
<!DOCTYPE translationbundle>
<translationbundle lang="es">
<translation id="{old_fp_1}">Bienvenido a Brave</translation>
<translation id="{old_fp_2}">Escudos de Brave en <ph name="BRAVE_VERSION"/></translation>
</translationbundle>
""")

        with open(pref_path, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<!-- Copyright (c) 2020 The Brave Authors. All rights reserved. -->
<PreferenceScreen xmlns:android="http://schemas.android.com/apk/res/android">
    <Preference
        android:key="qa_hint"
        android:title="Tap Brave version in About Brave"
        android:summary="Visit https://brave.com for Brave Search" />
</PreferenceScreen>
""")

        env = dict(os.environ)
        env.pop("CI", None)
        res = subprocess.run([sys.executable, script_path, tmpdir], env=env, capture_output=True, text=True)
        assert res.returncode == 0, f"apply-branding failed: {res.stderr}\n{res.stdout}"

        with open(grd_path, "r", encoding="utf-8") as f:
            grd_out = f.read()
        assert ">Welcome to Braving</message>" in grd_out
        assert ">Braving history</message>" in grd_out
        assert ">Braving runs faster</message>" in grd_out
        assert ">Try Brave Search at https://search.brave.com or brave://settings in Braving</message>" in grd_out
        assert ">Brave Wallet</message>" in grd_out, "Bloat wallet string should not be branded"
        assert ">Ask Brave Leo AI</message>" in grd_out, "Bloat AI chat string should not be branded"
        assert ">Brave Tor</message>" in grd_out, "Bloat Tor string should not be branded"

        with open(part_path, "r", encoding="utf-8") as f:
            part_out = f.read()
        assert 'Braving Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Brave 1.0</ex></ph>' in part_out

        with open(xtb_path, "r", encoding="utf-8") as f:
            xtb_out = f.read()
        assert f'id="{new_fp_1}">Bienvenido a Braving</translation>' in xtb_out
        assert f'id="{new_fp_2}">Escudos de Braving en <ph name="BRAVE_VERSION"/></translation>' in xtb_out

        with open(pref_path, "r", encoding="utf-8") as f:
            pref_out = f.read()
        assert "The Brave Authors" in pref_out, "Copyright comment should not be modified"
        assert 'android:title="Tap Braving version in About Braving"' in pref_out
        assert 'android:summary="Visit https://brave.com for Brave Search"' in pref_out

        # Idempotence check
        res_idem = subprocess.run([sys.executable, script_path, tmpdir], env=env, capture_output=True, text=True)
        assert res_idem.returncode == 0, f"apply-branding idempotence failed: {res_idem.stderr}"
        assert "0 messages updated across 0 GRD/GRDP files and 0 XTB translation files" in res_idem.stdout

        print("PASS: test_apply_branding")


def test_python311_syntax_compatibility():
    """Ensure all Python scripts and embedded heredocs are compatible with Python 3.11 (Debian Bookworm)."""
    import ast
    import glob
    import re

    def verify_source(code: str, label: str):
        tree = ast.parse(code, filename=label)
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                seg = ast.get_source_segment(code, node)
                if not seg:
                    continue
                m = re.match(r"^[fFrR]+(\"\"\"|'''|\"|')", seg)
                outer_q = m.group(1) if m else '"'
                for val in node.values:
                    if isinstance(val, ast.FormattedValue):
                        vseg = ast.get_source_segment(code, val) or ""
                        assert "\\" not in vseg, (
                            f"Python 3.11 SyntaxError: backslash in f-string expression at {label}:{node.lineno}: {vseg}"
                        )
                        if outer_q in ('"', "'"):
                            assert outer_q not in vseg, (
                                f"Python 3.11 SyntaxError: nested {outer_q} in f-string expression at {label}:{node.lineno}: {vseg}"
                            )
                        assert "#" not in vseg, (
                            f"Python 3.11 SyntaxError: comment in f-string expression at {label}:{node.lineno}: {vseg}"
                        )

    py_files = sorted(glob.glob(os.path.join(REPO_ROOT, "scripts/**/*.py"), recursive=True))
    for p in py_files:
        with open(p, "r", encoding="utf-8") as f:
            verify_source(f.read(), os.path.relpath(p, REPO_ROOT))

    sh_files = sorted(glob.glob(os.path.join(REPO_ROOT, "scripts/**/*.sh"), recursive=True))
    for p in sh_files:
        with open(p, "r", encoding="utf-8") as f:
            sh = f.read()
        for i, m in enumerate(re.finditer(r"python3 - [^\n]*<<'?PYEOF'?\n(.*?)\nPYEOF", sh, re.DOTALL)):
            verify_source(m.group(1), f"{os.path.relpath(p, REPO_ROOT)}[PYEOF#{i}]")

    print("PASS: test_python311_syntax_compatibility")


if __name__ == "__main__":
    try:
        test_python311_syntax_compatibility()
        test_apply_features()
        test_apply_branding()
        test_patch_suite()
        print("ALL MUTATOR & PATCH TESTS PASSED.")
    except Exception as e:
        import sys
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
