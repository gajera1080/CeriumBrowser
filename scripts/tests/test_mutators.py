#!/usr/bin/env python3
import os
import sys
import tempfile
import subprocess
import shutil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_apply_features():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test mock files
        rules_path = os.path.join(tmpdir, "build/webpack/rules.ts")
        wasm_path = os.path.join(tmpdir, "components/common/rust_to_wasm.gni")
        build_gn_path = os.path.join(tmpdir, "ui/webui/resources/BUILD.gn")
        sources_gni_path = os.path.join(tmpdir, "ui/webui/resources/sources.gni")

        os.makedirs(os.path.dirname(rules_path), exist_ok=True)
        os.makedirs(os.path.dirname(wasm_path), exist_ok=True)
        os.makedirs(os.path.dirname(build_gn_path), exist_ok=True)

        with open(rules_path, "w") as f:
            f.write("{ loader: 'sass-loader' },\n")

        with open(wasm_path, "w") as f:
            f.write('"--log-level",\n      "warn",\n')

        with open(build_gn_path, "w") as f:
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

        with open(sources_gni_path, "w") as f:
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

        # Verify mutated BUILD.gn
        with open(build_gn_path) as f:
            gn_content = f.read()
        assert ":external_js_bundles" in gn_content
        assert "//brave/components/brave_account/resources/opaque_ke" in gn_content
        assert ":external_js_bundles" not in gn_content.split('if (include_polymer)')[0]

        # Verify mutated sources.gni
        with open(sources_gni_path) as f:
            gni_content = f.read()
        assert "external_js.grdp" in gni_content
        assert "external_js.grdp" not in gni_content.split('if (!is_android && !is_ios)')[0]

        # Verify idempotence
        res_idem = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"apply-features idempotence failed: {res_idem.stderr}"
        assert "Skipped" in res_idem.stdout

        print("PASS: test_apply_features")

def test_enforce_policies():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test mock files
        origin_utils = os.path.join(tmpdir, "components/brave_origin/brave_origin_utils.cc")
        origin_service = os.path.join(tmpdir, "components/brave_origin/brave_origin_service.cc")
        policy_provider = os.path.join(tmpdir, "components/brave_policy/brave_browser_policy_provider.cc")
        ad_block = os.path.join(tmpdir, "components/brave_shields/content/browser/ad_block_service.cc")
        prefs_base = os.path.join(tmpdir, "android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java")

        # Java policy helper mocks
        wallet_policy = os.path.join(tmpdir, "android/java/org/chromium/chrome/browser/crypto_wallet/BraveWalletPolicy.java")
        news_policy = os.path.join(tmpdir, "android/java/org/chromium/chrome/browser/brave_news/BraveNewsPolicy.java")
        vpn_policy = os.path.join(tmpdir, "android/java/org/chromium/chrome/browser/vpn/BraveVpnPolicy.java")
        rewards_policy = os.path.join(tmpdir, "android/java/org/chromium/chrome/browser/BraveRewardsPolicy.java")
        leo_policy = os.path.join(tmpdir, "android/java/org/chromium/chrome/browser/brave_leo/BraveLeoPrefUtils.java")
        ntp_policy = os.path.join(tmpdir, "android/java/org/chromium/chrome/browser/ntp_background_images/util/NTPImageUtil.java")

        for p in [origin_utils, origin_service, policy_provider, ad_block, prefs_base,
                  wallet_policy, news_policy, vpn_policy, rewards_policy, leo_policy, ntp_policy]:
            os.makedirs(os.path.dirname(p), exist_ok=True)

        with open(origin_utils, "w") as f:
            f.write("""bool IsBraveOriginFeatureEnabled() {
  return base::FeatureList::IsEnabled(features::kBraveOrigin);
}

bool IsBraveOriginPurchased() {
  if (!IsBraveOriginFeatureEnabled()) {
    return false;
  }
  auto* manager = BraveOriginPolicyManager::GetInstance();
  return manager->IsInitialized() && manager->IsPurchased();
}
""")

        with open(origin_service, "w") as f:
            f.write("""void BraveOriginService::CheckPurchaseState(
    base::OnceCallback<void(bool)> callback) {
  if (!EnsureSkusConnected()) {
    std::move(callback).Run(IsPurchased());
    return;
  }

  skus_service_->CredentialSummary(
      origin_sku_domain_,
      base::BindOnce(&BraveOriginService::OnCredentialSummary,
                     weak_ptr_factory_.GetWeakPtr(), std::move(callback)));
}

bool BraveOriginService::IsPurchased() const {
  return BraveOriginPolicyManager::GetInstance()->IsPurchased();
}
""")

        with open(policy_provider, "w") as f:
            f.write("""policy::PolicyBundle BraveBrowserPolicyProvider::LoadPolicies() {
  policy::PolicyBundle bundle;

  if (brave_origin::IsBraveOriginPurchased()) {
    LoadBraveOriginPolicies(bundle);
  }

  return bundle;
}
""")

        with open(ad_block, "w") as f:
            f.write("""#include "brave/components/brave_shields/content/browser/ad_block_service.h"

void RegisterPrefsForAdBlockService(PrefRegistrySimple* registry) {
  registry->RegisterDictionaryPref(prefs::kAdBlockListSubscriptions);
}
""")

        with open(prefs_base, "w") as f:
            f.write("""if (ChromeFeatureList.isEnabled(BraveFeatureList.BRAVE_ORIGIN)) {\n""")

        with open(wallet_policy, "w") as f:
            f.write("public static boolean isDisabledByPolicy(@Nullable Profile profile) {\n        if (profile == null) return false;\n}")
        with open(news_policy, "w") as f:
            f.write("public static boolean isDisabledByPolicy(@Nullable Profile profile) {\n        return false;\n}")
        with open(vpn_policy, "w") as f:
            f.write("public static boolean isDisabledByPolicy(@Nullable Profile profile) {\n        return false;\n}")
        with open(rewards_policy, "w") as f:
            f.write("public static boolean isDisabledByPolicy(@Nullable Profile profile) {\n        return false;\n}")
        with open(leo_policy, "w") as f:
            f.write("public static boolean isLeoDisabledByPolicy(@Nullable Profile profile) {\n        return false;\n}")
        with open(ntp_policy, "w") as f:
            f.write("public static boolean shouldEnableNTPFeature() {\n        return true;\n}")

        script = os.path.join(REPO_ROOT, "scripts/android/enforce-policies.py")
        res = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res.returncode == 0, f"enforce-policies failed: {res.stderr}\n{res.stdout}"

        # 1. Check brave_origin_utils.cc
        with open(origin_utils) as f:
            u_content = f.read()
        assert "return manager->IsInitialized();" in u_content
        assert "bool IsBraveOriginFeatureEnabled() {\n  return true;\n}" in u_content

        # 2. Check brave_origin_service.cc
        with open(origin_service) as f:
            s_content = f.read()
        assert "std::move(callback).Run(true);" in s_content
        assert "bool BraveOriginService::IsPurchased() const {\n  return true;\n}" in s_content

        # 3. Check brave_browser_policy_provider.cc
        with open(policy_provider) as f:
            p_content = f.read()
        for pol in ["BraveWalletDisabled", "BraveVPNDisabled", "BraveAIChatEnabled", "BraveNewsDisabled",
                    "BraveRewardsDisabled", "BraveSearchResultAdsEnabled", "BraveTalkDisabled",
                    "BraveStatsPingEnabled", "BraveWebDiscoveryEnabled", "BraveP3AEnabled",
                    "BraveWaybackMachineEnabled", "BraveLocalAIEnabled"]:
            assert f'enforce("{pol}", ' in p_content, f"Missing policy: {pol}"
        assert "if (brave_origin::IsBraveOriginPurchased())" in p_content

        # 4. Check ad_block_service.cc
        with open(ad_block) as f:
            a_content = f.read()
        assert '#include "base/values.h"' in a_content
        assert 'prefs::kAdBlockListSubscriptions, std::move(default_subscriptions)' in a_content

        # 5. Check Java policies
        with open(wallet_policy) as f:
            assert "if (true) return true;" in f.read()
        with open(ntp_policy) as f:
            assert "if (true) return false;" in f.read()

        # Verify idempotence in strict mode
        res_idem = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"enforce-policies idempotence failed: {res_idem.stderr}"
        assert "Skipped C++" in res_idem.stdout

        print("PASS: test_enforce_policies")


if __name__ == "__main__":
    try:
        test_apply_features()
        test_enforce_policies()
        print("ALL MUTATOR TESTS PASSED.")
    except Exception as e:
        import sys
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
