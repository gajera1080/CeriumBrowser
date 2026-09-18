import sys
import os

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")

def patch_cpp(filepath, search, inject_before, inject_after=""):
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

    is_patched = (inject_before and inject_before in content) or (inject_after and inject_after in content)
    if search in content and not is_patched:
        content = content.replace(search, inject_before + search + inject_after, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched C++ {filepath}")
    elif is_patched:
        print(f"Skipped {filepath} (already patched)")
    else:
        msg = f"Search string not found in {filepath}: {search[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

def remove_xml_block(filepath, search_start, search_end):
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
    
    start_idx = content.find(search_start)
    if start_idx != -1:
        end_idx = content.find(search_end, start_idx)
        if end_idx != -1:
            content = content[:start_idx] + content[end_idx + len(search_end):]
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Removed block from {filepath}")
            return
    print(f"Block not found or already removed in {filepath}")

def replace_in_file(filepath, search, replacement):
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

    if replacement in content:
        print(f"Skipped {filepath} (already patched)")
        return

    if search in content:
        content = content.replace(search, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        msg = f"Search string not found in {filepath}: {search[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

# 1. Enable Brave Origin Service (CheckPurchaseState)
origin_service_fallback = """void BraveOriginService::CheckPurchaseState(
  base::OnceCallback<void(bool)> callback) {
  BraveOriginPolicyManager::GetInstance()->SetPurchased(true);
  if (local_state_) { local_state_->SetBoolean(kOriginPoliciesWereEnforced, true); }
  std::move(callback).Run(true);
  return;
}

void BraveOriginService::CheckPurchaseState_UNUSED(
"""
patch_cpp("components/brave_origin/brave_origin_service.cc",
          "void BraveOriginService::CheckPurchaseState(",
          "", origin_service_fallback.replace("void BraveOriginService::CheckPurchaseState(\n", ""))

# 2. Origin Utils
patch_cpp("components/brave_origin/brave_origin_utils.cc",
          "  if (!IsBraveOriginFeatureEnabled()) {\n    return false;\n  }",
          "", "\n  return true;")

# 3. Remove purchase UI section
remove_xml_block("android/java/brave-res/xml/brave_origin_preferences.xml",
                 "<PreferenceCategory\n        android:key=\"origin_purchase_section\"",
                 "</PreferenceCategory>")

# 4. Silence Dart Sass legacy JS API deprecation warning in sass-loader
replace_in_file(
    "build/webpack/rules.ts",
    "{ loader: 'sass-loader' },",
    "{ loader: 'sass-loader', options: { sassOptions: { silenceDeprecations: ['legacy-js-api'] } } },"
)

# 5. Silence wasm-pack version update notice
replace_in_file(
    "components/common/rust_to_wasm.gni",
    '"--log-level",\n      "warn",',
    '"--log-level",\n      "error",'
)

print("Successfully injected Brave Origin feature modifications!")

