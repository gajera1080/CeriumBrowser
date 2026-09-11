import sys
import os
import re

repo_root = sys.argv[1]

def comment_out_imports_and_usages(file_path, keywords):
    with open(file_path, "r") as f:
        lines = f.readlines()
    
    new_lines = []
    in_block = False
    for line in lines:
        if any(kw in line for kw in keywords):
            new_lines.append("// " + line)
        else:
            new_lines.append(line)
            
    with open(file_path, "w") as f:
        f.writelines(new_lines)

# Exclude wallet files from GN
gni_path = os.path.join(repo_root, "android/brave_java_sources.gni")
with open(gni_path, "r") as f:
    gni_lines = f.readlines()
new_gni = [l for l in gni_lines if "crypto_wallet" not in l and "Wallet" not in l and "NetworkPreferenceAdapter" not in l]
with open(gni_path, "w") as f:
    f.writelines(new_gni)

print("Java sources pruned.")
