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
