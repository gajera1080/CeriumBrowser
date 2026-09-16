import sys
import os

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")
java_file = os.path.join(repo_root, "android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java")

if not os.path.exists(java_file):
    msg = f"MISSING: {java_file}"
    if STRICT:
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)
    print(f"WARNING: {msg}")
    sys.exit(0)

with open(java_file, "r") as f:
    content = f.read()

injection = """
        // --- BRAVING UI PRUNING ---
        removePreferenceIfPresent(PREF_BRAVE_WALLET);
        removePreferenceIfPresent(PREF_BRAVE_NEWS_V2);
        removePreferenceIfPresent(PREF_BRAVE_VPN);
        removePreferenceIfPresent(PREF_BRAVE_LEO);
        removePreferenceIfPresent(PREF_BRAVE_ORIGIN);
        removePreferenceIfPresent(PREF_BRAVE_VPN_CALLOUT);
        // --------------------------
"""

if "BRAVING UI PRUNING" not in content:
    if "resortPreferenceScreenChildren();" in content:
        content = content.replace("resortPreferenceScreenChildren();", injection + "\n        resortPreferenceScreenChildren();")
        with open(java_file, "w") as f:
            f.write(content)
        print("Successfully pruned bloatware from BraveMainPreferencesBase UI!")
    else:
        print("ERROR: resortPreferenceScreenChildren() not found in BraveMainPreferencesBase.java")
        sys.exit(1)
else:
    print("UI already pruned.")
