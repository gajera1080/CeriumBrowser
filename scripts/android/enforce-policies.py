import sys
import os
import re

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")

def patch_method(filepath, method_name, inject_code):
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
    
    search = f"public static boolean {method_name}("
    if search in content and inject_code not in content:
        m = re.search(re.escape(search) + r'[^\{]*\{', content)
        if m:
            idx = m.end()
            content = content[:idx] + inject_code + content[idx:]
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Patched {filepath} -> {method_name}")
    else:
        print(f"Skipped {filepath} (already patched or method not found)")

# Hide UI in Settings and App Menu (also hides NTP News feed)
patch_method("android/java/org/chromium/chrome/browser/crypto_wallet/BraveWalletPolicy.java", "isDisabledByPolicy", "\n        if (true) return true;")
patch_method("android/java/org/chromium/chrome/browser/brave_news/BraveNewsPolicy.java", "isDisabledByPolicy", "\n        if (true) return true;")
patch_method("android/java/org/chromium/chrome/browser/vpn/BraveVpnPolicy.java", "isDisabledByPolicy", "\n        if (true) return true;")
patch_method("android/java/org/chromium/chrome/browser/BraveRewardsPolicy.java", "isDisabledByPolicy", "\n        if (true) return true;")
patch_method("android/java/org/chromium/chrome/browser/brave_leo/BraveLeoPrefUtils.java", "isLeoDisabledByPolicy", "\n        if (true) return true;")

# Hide Sponsored Images from NTP
patch_method("android/java/org/chromium/chrome/browser/ntp_background_images/util/NTPImageUtil.java", "shouldEnableNTPFeature", "\n        if (true) return false;")

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

# Force Disable P3A (Privacy Preserving Product Analytics)
patch_cpp("components/p3a/p3a_service.cc", 
          "registry->RegisterBooleanPref(kP3AEnabled,\n                                !BUILDFLAG(IS_BRAVE_ORIGIN_BRANDED));", 
          "registry->RegisterBooleanPref(kP3AEnabled,\n                                false);")

# Force Disable Statistics Ping Reporting
patch_cpp("browser/brave_local_state_prefs.cc", 
          "registry->RegisterBooleanPref(kStatsReportingEnabled, true);", 
          "registry->RegisterBooleanPref(kStatsReportingEnabled, false);")


# Hide Web Discovery Project in Settings
patch_cpp("android/java/org/chromium/chrome/browser/settings/BraveOriginPreferences.java",
          "PREF_WEB_DISCOVERY_PROJECT_SWITCH.equals(preferenceKey)",
          "false")

# Remove Brave Origin from Settings Menu
patch_cpp("android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java",
          "if (ChromeFeatureList.isEnabled(BraveFeatureList.BRAVE_ORIGIN)) {",
          "if (false) {")

# Unlock Brave Origin for Backend Changes
patch_cpp("components/brave_origin/brave_origin_utils.cc",
          "bool IsBraveOriginFeatureEnabled() {\n  return base::FeatureList::IsEnabled(features::kBraveOrigin);\n}",
          "bool IsBraveOriginFeatureEnabled() {\n  return true;\n}")

# Force Enforce Braving Debloat Enterprise Policies in C++
patch_cpp("components/brave_policy/brave_browser_policy_provider.cc",
          "  return bundle;\n}",
          """
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

  return bundle;
}""")

# Pre-seed direct uBlock Origin & EasyList subscriptions in Shields
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

