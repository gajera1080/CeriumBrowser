import sys
import os
import re

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
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if old in content:
        # AGENTS.md rule 3: For UI strings, only mutate inner text of nodes.
        # Split by XML tags to protect all attributes (like name="IDS_Brave_Rewards")
        parts = re.split(r'(<[^>]+>)', content)
        for i in range(len(parts)):
            # Even indices are text nodes outside of < >
            if i % 2 == 0:
                parts[i] = parts[i].replace(old, new)
        
        new_content = "".join(parts)
            
        if new_content != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Branded: {filepath}")
        else:
            print(f"Skipped: {filepath} (already branded or no text nodes to brand)")

# Target Android GRD files and channel constants
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

