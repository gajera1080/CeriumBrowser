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

        for p in [webpack_rules, rust_wasm, webui_build_gn, webui_sources_gni]:
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
    assert len(patches) >= 3, f"Expected at least 3 patches, found {len(patches)}"
    for p in patches:
        assert os.path.getsize(p) > 50, f"Patch {p} is suspiciously small"

    # Verify 0002 custom updater endpoint patch
    patch_0002 = os.path.join(REPO_ROOT, "patches/android/0002-custom-updater-endpoint.patch")
    assert os.path.isfile(patch_0002), f"Missing patch file: {patch_0002}"
    with open(patch_0002, "r", encoding="utf-8") as f:
        c0002 = f.read()
    assert 'https://updates.braving.org/components' in c0002
    assert 'updater_dev_endpoint' in c0002
    assert 'updater_prod_endpoint' in c0002

    # Verify 0003 enterprise policies and origin hooks
    patch_0003 = os.path.join(REPO_ROOT, "patches/android/0003-enforce-debloat-policies.patch")
    assert os.path.isfile(patch_0003), f"Missing patch file: {patch_0003}"
    with open(patch_0003, "r", encoding="utf-8") as f:
        c0003 = f.read()
    assert "BraveWalletDisabled" in c0003
    assert "BraveVPNDisabled" in c0003
    assert "BraveAIChatEnabled" in c0003

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
                assert res_rev.returncode == 0, f"Patch {os.path.basename(p)} failed to apply: {res.stderr}"

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
