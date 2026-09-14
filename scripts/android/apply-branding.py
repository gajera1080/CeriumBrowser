import sys
import os

repo_root = sys.argv[1]

def replace_in_file(filepath, old, new):
    path = os.path.join(repo_root, filepath)
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(path, "w") as f:
            f.write(content)
        print(f"Branded: {filepath}")

# We need to target the Android GRD files
grd_files = [
    "browser/ui/android/strings/android_brave_strings.grd",
    "browser/ui/android/strings/android_chrome_strings_override.grd",
    "components/browser_ui/strings/android/browser_ui_strings_override.grd",
    "components/browser_ui/strings/android/browser_ui_strings.grd",
    "app/brave_strings.grd",
    "app/brave_strings_override.grd",
    "components/components_brave_strings.grd"
]

for f in grd_files:
    replace_in_file(f, "Brave", "Braving")
    replace_in_file(f, "brave", "braving")
