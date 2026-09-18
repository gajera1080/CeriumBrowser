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
        # Avoid replacing attribute names like name="Brave..." or id="Brave..."
        if old == "Brave":
            new_content = re.sub(r'(?<!name=")(?<!id=")Brave', new, content)
        else:
            new_content = content.replace(old, new)
            
        if new_content != content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Branded: {filepath}")
        else:
            print(f"Skipped: {filepath} (already branded)")

# Safe Package ID and Application Name Branding ONLY
# Note: Global regex replacement of "Brave" to "Braving" in .grd files was removed 
# because it broke C++ translation dependencies (e.g., IDS_Brave_Rewards). 
# Any specific user-facing string debranding should be done via semantic patching.

replace_in_file("build/commands/lib/buildArgs.ts", "com.brave.browser", "org.braving.browser")
