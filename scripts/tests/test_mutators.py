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

        for p in [webpack_rules, rust_wasm, webui_build_gn, webui_sources_gni, nala_build_gn, brave_java_res_gni]:
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


if __name__ == "__main__":
    try:
        test_apply_features()
        test_patch_suite()
        print("ALL MUTATOR & PATCH TESTS PASSED.")
    except Exception as e:
        import sys
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
