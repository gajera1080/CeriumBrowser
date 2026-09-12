import sys
import os

repo_root = sys.argv[1]

def patch_method(filepath, method_name, inject_code):
    path = os.path.join(repo_root, filepath)
    if not os.path.exists(path):
        print(f"File not found: {filepath}")
        return
        
    with open(path, "r") as f:
        content = f.read()
    
    search = f"public static boolean {method_name}("
    if search in content and inject_code not in content:
        idx = content.find("{", content.find(search))
        if idx != -1:
            content = content[:idx+1] + inject_code + content[idx+1:]
            with open(path, "w") as f:
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
        print(f"File not found: {filepath}")
        return
    with open(path, "r") as f:
        content = f.read()
    if search in content:
        content = content.replace(search, replace)
        with open(path, "w") as f:
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
