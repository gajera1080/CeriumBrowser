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

    with open(path, "r") as f:
        content = f.read()

    if search in content and inject_before not in content:
        content = content.replace(search, inject_before + search + inject_after)
        with open(path, "w") as f:
            f.write(content)
        print(f"Patched C++ {filepath}")
    elif inject_before in content:
        print(f"Skipped {filepath} (already patched)")
    else:
        msg = f"Search string not found in {filepath}: {search[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")

# 1. BUILD.gn deps
patch_cpp("components/brave_shields/core/browser/BUILD.gn",
          "\"//base\",",
          "    \"//brave/components/resources\",\n    \"//ui/base\",\n    ")

# 2. AdBlockComponentFiltersProvider
cpp_filters_incl = """#include "brave/components/resources/grit/brave_components_resources.h"
#include "ui/base/resource/resource_bundle.h"
"""
cpp_filters_fallback = """  if (ui::ResourceBundle::HasSharedInstance()) {
    nint resource_id = GetFallbackResourceIdForComponent(uuid);
    if (resource_id != 0) {
      base::ThreadPool::PostTaskAndReplyWithResult(
          FROM_HERE, {base::MayBlock()},
          base::BindOnce([](int id) -> DATFileDataBuffer {
            std::string data = ui::ResourceBundle::GetSharedInstance().LoadDataResourceString(id);
            return DATFileDataBuffer(data.begin(), data.end());
          }, resource_id),
          base::BindOnce(&OnReadDATFileData, std::move(cb), permission_mask_, flow));
      return;
    }
  }
"""
cpp_filters_helper = """
nint GetFallbackResourceIdForComponent(const std::string& component_id) {
  if (component_id == "iodkpdagapdfkphljnddpjlldadblomo") return IDR_BRAVE_SHIELDS_DEFAULT_RULES;
  if (component_id == "kihnoaefogbkmblfimmibknnmkllbhlf") return IDR_BRAVE_SHIELDS_TRACKER_RULES;
  if (component_id == "adcocjohghhfpidemphmcmlmhnfgikei") return IDR_BRAVE_SHIELDS_FIRST_PARTY_RULES;
  if (component_id == "cdbbhgbmjhfnhnmgeddbliobbofkgdhe") return IDR_BRAVE_SHIELDS_COOKIE_RULES;
  if (component_id == "bfpgedeaaibpoidldhjcknekahbikncb") return IDR_BRAVE_SHIELDS_MOBILE_RULES;
  return 0;
}
"""
patch_cpp("components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
          "#include \"brave/components/brave_shields/core/browser/ad_block_filters_provider.h\"",
          cpp_filters_incl)
patch_cpp("components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
          "std::move(cb).Run(base::BindOnce(AddNothingToFilterSet));",
          cpp_filters_fallback)
patch_cpp("components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
          "}  // namespace brave_shields",
          cpp_filters_helper)

# 3. AdBlockDefaultResourceProvider
cpp_res_incl = """#include "brave/components/resources/grit/brave_components_resources.h"
#include "ui/base/resource/resource_bundle.h"
"""
cpp_res_fallback = """    if (ui::ResourceBundle::HasSharedInstance()) {
      std::string resources_json = ui::ResourceBundle::GetSharedInstance().LoadDataResourceString(IDR_BRAVE_SHIELDS_RESOURCES_JSON);
      if (!resources_json.empty()) {
        base::ThreadPool::PostTaskAndReplyWithResult(
            FROM_HERE, {base::MayBlock()},
            base::BindOnce([](std::string json) { return adblock::new_resource_storage(json); }, std::move(resources_json)),
            std::move(cb));
        return;
      }
    }
"""
patch_cpp("components/brave_shields/core/browser/ad_block_default_resource_provider.cc",
          "#include \"base/task/thread_pool.h\"",
          cpp_res_incl)
patch_cpp("components/brave_shields/core/browser/ad_block_default_resource_provider.cc",
          "// This should not happen, but if it does, we should not proceed.",
          cpp_res_fallback)
patch_cpp("components/brave_shields/core/browser/ad_block_default_resource_provider.cc",
          "// If the path is not ready yet, run the callback with empty resources to",
          cpp_res_fallback)

# 4. AdBlockFilterListCatalogProvider
cpp_cat_incl = """#include "brave/components/resources/grit/brave_components_resources.h"
#include "ui/base/resource/resource_bundle.h"
"""
cpp_cat_fallback = """    if (ui::ResourceBundle::HasSharedInstance()) {
      std::string catalog_json = ui::ResourceBundle::GetSharedInstance().LoadDataResourceString(IDR_BRAVE_SHIELDS_LIST_CATALOG);
      if (!catalog_json.empty()) {
        base::ThreadPool::PostTaskAndReplyWithResult(
            FROM_HERE, {base::MayBlock()},
            base::BindOnce([](std::string json) { return json; }, std::move(catalog_json)),
            std::move(cb));
        return;
      }
    }
"""
patch_cpp("components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.cc",
          "#include \"base/task/thread_pool.h\"",
          cpp_cat_incl)
patch_cpp("components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.cc",
          "// If the path is not ready yet, don't run the callback. An update should be",
          cpp_cat_fallback)

def replace_exact(filepath, old, new):
    path = os.path.join(repo_root, filepath)
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new)
        with open(path, "w") as f:
            f.write(content)
        print(f"Patched GRD: {filepath}")

replace_exact("components/resources/brave_components_resources.grd",
              """      <if expr="not is_android">
        <part file="brave_shields_resources.grdp" />""",
              """      <part file="brave_shields_resources.grdp" />
      <if expr="not is_android">""")
patch_cpp("components/resources/brave_shields_resources.grdp",
          "</grit-part>",
          """  <include name="IDR_BRAVE_SHIELDS_LIST_CATALOG" file="../brave_shields/resources/list_catalog.json" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_RESOURCES_JSON" file="../brave_shields/resources/resources.json" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_DEFAULT_RULES" file="../brave_shields/resources/default_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_TRACKER_RULES" file="../brave_shields/resources/tracker_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_FIRST_PARTY_RULES" file="../brave_shields/resources/first_party_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_COOKIE_RULES" file="../brave_shields/resources/cookie_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_MOBILE_RULES" file="../brave_shields/resources/mobile_rules.txt" type="BINDATA" />
""")

patch_cpp("resources/resource_ids.spec",
          "\"includes\": [53020],",
          "", "\"includes\": [54200],  # Braving patched\n")

print("Successfully injected Shields offline fallback logic!")
