import sys
import os
import re

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")


def patch_cpp(filepath, search, replace):
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
    if replace in content:
        print(f"Skipped C++ {filepath} (already patched)")
        return
    if search in content:
        content = content.replace(search, replace, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched C++ {filepath}")
    else:
        msg = f"Search string not found in {filepath}: {search[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

# Remove Brave Origin from Settings Menu
patch_cpp("android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java",
          "if (ChromeFeatureList.isEnabled(BraveFeatureList.BRAVE_ORIGIN)) {",
          "if (false) {")

# Safe Brave Origin Backend Enablement
# 1. Feature flag enabled and IsBraveOriginPurchased safely returns manager->IsInitialized()
patch_cpp("components/brave_origin/brave_origin_utils.cc",
          "bool IsBraveOriginFeatureEnabled() {\n  return base::FeatureList::IsEnabled(features::kBraveOrigin);\n}",
          "bool IsBraveOriginFeatureEnabled() {\n  return true;\n}")

patch_cpp("components/brave_origin/brave_origin_utils.cc",
          "  auto* manager = BraveOriginPolicyManager::GetInstance();\n  return manager->IsInitialized() && manager->IsPurchased();",
          "  auto* manager = BraveOriginPolicyManager::GetInstance();\n  return manager->IsInitialized();")

# 2. Stub CheckPurchaseState and IsPurchased in BraveOriginService
patch_cpp("components/brave_origin/brave_origin_service.cc",
          """void BraveOriginService::CheckPurchaseState(
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
}""",
          """void BraveOriginService::CheckPurchaseState(
    base::OnceCallback<void(bool)> callback) {
  std::move(callback).Run(true);
}

bool BraveOriginService::IsPurchased() const {
  return true;
}""")

# Force Enforce Braving Debloat Enterprise Policies in C++
# Anchored inside LoadPolicies() after policy::PolicyBundle bundle;
patch_cpp("components/brave_policy/brave_browser_policy_provider.cc",
          "policy::PolicyBundle BraveBrowserPolicyProvider::LoadPolicies() {\n  policy::PolicyBundle bundle;",
          """policy::PolicyBundle BraveBrowserPolicyProvider::LoadPolicies() {
  policy::PolicyBundle bundle;

  // Braving: Enforce debloat policies via Enterprise Policy
  policy::PolicyMap& pm = bundle.Get(policy::PolicyNamespace(policy::POLICY_DOMAIN_CHROME, std::string()));
  auto enforce = [&](const char* name, bool val) {
    pm.Set(name, policy::POLICY_LEVEL_MANDATORY, policy::POLICY_SCOPE_USER, policy::POLICY_SOURCE_PLATFORM, base::Value(val), nullptr);
  };
  enforce("BraveWalletDisabled", true);
  enforce("BraveVPNDisabled", true);
  enforce("BraveAIChatEnabled", false);
  enforce("BraveNewsDisabled", true);
  enforce("BraveRewardsDisabled", true);
  enforce("BraveSearchResultAdsEnabled", false);
  enforce("BraveTalkDisabled", true);
  enforce("BraveStatsPingEnabled", false);
  enforce("BraveWebDiscoveryEnabled", false);
  enforce("BraveP3AEnabled", false);
  enforce("BraveWaybackMachineEnabled", false);
  enforce("BraveLocalAIEnabled", false);""")

# Pre-seed direct uBlock Origin & EasyList subscriptions in Shields
patch_cpp("components/brave_shields/content/browser/ad_block_service.cc",
          '#include "brave/components/brave_shields/content/browser/ad_block_service.h"',
          '#include "brave/components/brave_shields/content/browser/ad_block_service.h"\n#include "base/values.h"')

patch_cpp("components/brave_shields/content/browser/ad_block_service.cc",
          "  registry->RegisterDictionaryPref(prefs::kAdBlockListSubscriptions);",
          """  // Braving: Pre-seed direct uBlock Origin & EasyList subscription sources
  base::Value::Dict default_subscriptions;
  auto add_sub = [&](const char* url, const char* title) {
    base::Value::Dict sub;
    sub.Set("enabled", true);
    sub.Set("last_update_attempt", 0);
    sub.Set("last_successful_update_attempt", 0);
    sub.Set("expires", 72);
    sub.Set("title", title);
    default_subscriptions.Set(url, std::move(sub));
  };
  add_sub("https://easylist.to/easylist/easylist.txt", "EasyList");
  add_sub("https://easylist.to/easylist/easyprivacy.txt", "EasyPrivacy");
  add_sub("https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/filters.txt", "uBlock filters");
  add_sub("https://raw.githubusercontent.com/uBlockOrigin/uAssets/master/filters/badware.txt", "uBlock filters - Badware risks");
  add_sub("https://pgl.yoyo.org/adservers/serverlist.php?hostformat=adblockplus&showintro=1&mimetype=plaintext", "Peter Lowe's list");

  registry->RegisterDictionaryPref(prefs::kAdBlockListSubscriptions, std::move(default_subscriptions));""")

