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

        for p in [origin_utils, origin_service, policy_provider, ad_block, prefs_base]:
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


        # Verify idempotence in strict mode
        res_idem = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"enforce-policies idempotence failed: {res_idem.stderr}"
        assert "Skipped C++" in res_idem.stdout

        print("PASS: test_enforce_policies")

def test_apply_shields_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock files
        build_gn = os.path.join(tmpdir, "components/brave_shields/core/browser/BUILD.gn")
        filters_prov = os.path.join(tmpdir, "components/brave_shields/core/browser/ad_block_component_filters_provider.cc")
        res_prov = os.path.join(tmpdir, "components/brave_shields/core/browser/ad_block_default_resource_provider.cc")
        cat_prov = os.path.join(tmpdir, "components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.cc")
        grd = os.path.join(tmpdir, "components/resources/brave_components_resources.grd")
        grdp = os.path.join(tmpdir, "components/resources/brave_shields_resources.grdp")
        ios_res = os.path.join(tmpdir, "ios/brave-ios/Tests/ClientTests/Resources/ad-block-resources/resources.json")
        updater_build_gn = os.path.join(tmpdir, "components/update_client/BUILD.gn")
        allowed_lists_h = os.path.join(tmpdir, "browser/net/brave_network_audit_allowed_lists.h")

        for p in [build_gn, filters_prov, res_prov, cat_prov, grd, grdp, ios_res, updater_build_gn, allowed_lists_h]:
            os.makedirs(os.path.dirname(p), exist_ok=True)

        with open(build_gn, "w") as f:
            f.write("""  deps = [
    "//base",
    "//components/prefs",
  ]
""")

        with open(filters_prov, "w") as f:
            f.write("""#include "brave/components/brave_shields/core/browser/ad_block_component_filters_provider.h"

namespace {

void AddNothingToFilterSet(rust::Box<adblock::FilterSet>*) {}

}  // namespace

bool AdBlockComponentFiltersProvider::IsInitialized() const {
  return !component_path_.empty();
}

void AdBlockComponentFiltersProvider::LoadFilterSet(cb) {
  if (list_file_path.empty()) {
    // If the path is not ready yet, provide a no-op callback immediately. An
    // update will be pushed later to notify about the newly available list.
    std::move(cb).Run(base::BindOnce(AddNothingToFilterSet));
    return;
  }
}
""")

        with open(res_prov, "w") as f:
            f.write("""#include "brave/components/brave_shields/core/browser/ad_block_default_resource_provider.h"

void AdBlockDefaultResourceProvider::LoadResources(cb) {
  base::FilePath resources_path = GetResourcesPath();
  if (resources_path.empty()) {
    // If the path is not ready yet, run the callback with empty resources to
    // avoid blocking filter data loads.
    auto empty_storage = adblock::new_empty_resource_storage();
    std::move(cb).Run(std::move(empty_storage));
    return;
  }
}
""")

        with open(cat_prov, "w") as f:
            f.write("""#include "brave/components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.h"

void AdBlockFilterListCatalogProvider::LoadFilterListCatalog(
    base::OnceCallback<void(const std::string& catalog_json)> cb) {
  if (component_path_.empty()) {
    // If the path is not ready yet, don't run the callback. An update should be
    // pushed soon.
    return;
  }
}
""")

        with open(grd, "w") as f:
            f.write("""      <if expr="not is_android">
        <part file="brave_shields_resources.grdp" />
        <part file="brave_private_new_tab_resources.grdp" />
      </if>
""")

        with open(grdp, "w") as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<grit-part>
  <include name="IDR_BRAVE_SHIELDS_ICON_64" file="../brave_shields/resources/icon.png" type="BINDATA" />
</grit-part>
""")

        with open(ios_res, "w") as f:
            f.write('[{"name": "test"}]\n')

        with open(updater_build_gn, "w") as f:
            f.write("""  updater_dev_endpoint = "https://go-updater-dev.bravesoftware.com/extensions"
  updater_prod_endpoint = "https://go-updater.brave.com/extensions"
""")

        with open(allowed_lists_h, "w") as f:
            f.write("""    "https://go-updater.brave.com/",
""")

        script = os.path.join(REPO_ROOT, "scripts/android/apply-shields-fallback.py")
        res = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res.returncode == 0, f"apply-shields-fallback failed: {res.stderr}\n{res.stdout}"

        # 1. Check BUILD.gn
        with open(build_gn) as f:
            gn_content = f.read()
            assert '"//brave/components/resources",' in gn_content
            assert '"//ui/base",' in gn_content

        # 2. Check filters provider
        with open(filters_prov) as f:
            fp_content = f.read()
            assert "GetFallbackResourceIdForComponent" in fp_content
            assert "ui::ResourceBundle::HasSharedInstance()" in fp_content
            assert "int resource_id = GetFallbackResourceIdForComponent(component_id_);" in fp_content

        # 3. Check resource provider
        with open(res_prov) as f:
            rp_content = f.read()
            assert "IDR_BRAVE_SHIELDS_RESOURCES_JSON" in rp_content

        # 4. Check catalog provider
        with open(cat_prov) as f:
            cp_content = f.read()
            assert "IDR_BRAVE_SHIELDS_LIST_CATALOG" in cp_content

        # 5. Check GRD and GRDP
        with open(grd) as f:
            grd_content = f.read()
            assert '<part file="brave_shields_resources.grdp" />\n      <if expr="not is_android">' in grd_content

        with open(grdp) as f:
            grdp_content = f.read()
            assert 'IDR_BRAVE_SHIELDS_DEFAULT_RULES' in grdp_content
            assert 'IDR_BRAVE_SHIELDS_RESOURCES_JSON' in grdp_content

        # 6. Check provisioned fallback resources
        res_dir = os.path.join(tmpdir, "components/brave_shields/resources")
        assert os.path.exists(os.path.join(res_dir, "default_rules.txt"))
        assert os.path.exists(os.path.join(res_dir, "tracker_rules.txt"))
        assert os.path.exists(os.path.join(res_dir, "list_catalog.json"))
        assert os.path.exists(os.path.join(res_dir, "resources.json"))
        
        # 7. Check updater endpoints
        with open(updater_build_gn) as f:
            updater_content = f.read()
            assert 'updater_dev_endpoint = "https://updates.braving.org/components"' in updater_content
            assert 'updater_prod_endpoint = "https://updates.braving.org/components"' in updater_content
            assert "go-updater-dev.bravesoftware.com" not in updater_content
            assert "go-updater.brave.com" not in updater_content
            
        with open(allowed_lists_h) as f:
            allowed_lists_content = f.read()
            assert '"https://updates.braving.org/components/",' in allowed_lists_content

        # Verify idempotence
        res_idem = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"apply-shields-fallback idempotence failed: {res_idem.stderr}"
        assert "Skipped" in res_idem.stdout

        print("PASS: test_apply_shields_fallback")


if __name__ == "__main__":
    try:
        test_apply_features()
        test_enforce_policies()
        test_apply_shields_fallback()
        print("ALL MUTATOR TESTS PASSED.")
    except Exception as e:
        import sys
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
