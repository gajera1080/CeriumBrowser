import sys
import os

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")

def replace_in_file(filepath, old, new):
    path = os.path.join(repo_root, filepath)
    if not os.path.exists(path):
        msg = f"MISSING: {filepath}"
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")
        return
    with open(path, "r") as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(path, "w") as f:
            f.write(content)
        print(f"Branded: {filepath}")

# Target Android GRD files
grd_files = [
    "browser/ui/android/strings/android_brave_strings.grd",
    "browser/ui/android/strings/android_chrome_strings_override.grd",
    "components/browser_ui/strings/android/browser_ui_strings_override.grd",
    "components/browser_ui/strings/android/browser_ui_strings.grd",
    "app/brave_strings.grd",
    "app/brave_strings_override.grd",
    "components/components_brave_strings.grd",
    "app/theme/brave/android/res_brave_base/values/channel_constants.xml",
    "app/theme/brave/android/res_brave_default_base/values/channel_constants.xml",
    "app/theme/brave/android/values/channel_constants.xml"
]

for f in grd_files:
    replace_in_file(f, "Brave", "Braving")
    replace_in_file(f, "brave", "braving")

replace_in_file("build/commands/lib/buildArgs.ts", "com.brave.browser", "org.braving.browser")
