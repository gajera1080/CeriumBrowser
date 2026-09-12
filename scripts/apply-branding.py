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

xml_files = [
    "android/java/brave-res/values/android_brave_strings.xml",
    "android/java/brave-res/values/brave_strings.xml",
    "android/java/brave-res/values/brave_sync_strings.xml",
    "android/java/brave-res/values/strings.xml"
]

for f in xml_files:
    replace_in_file(f, "Brave", "Braving")
    replace_in_file(f, "brave", "braving")

