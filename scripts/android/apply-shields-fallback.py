#!/usr/bin/env python3
import sys
import os
import re
import shutil

repo_root = sys.argv[1]
STRICT = "--strict" in sys.argv or os.environ.get("CI")


def patch_file(filepath, search, replace):
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
    if replace in content:
        print(f"Skipped {filepath} (already patched)")
        return
    if search in content:
        content = content.replace(search, replace, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        msg = f"Search string not found in {filepath}: {search[:50]}..."
        if STRICT:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"WARNING: {msg}")


# 0. Provision default offline rules and catalog stubs
res_dir = os.path.join(repo_root, "components/brave_shields/resources")
os.makedirs(res_dir, exist_ok=True)

# Sourced from local repo if available
resources_src = os.path.join(repo_root, "ios/brave-ios/Tests/ClientTests/Resources/ad-block-resources/resources.json")
target_resources = os.path.join(res_dir, "resources.json")
if not os.path.exists(target_resources):
    if os.path.exists(resources_src):
        shutil.copyfile(resources_src, target_resources)
        print(f"Copied {resources_src} to {target_resources}")
    else:
        with open(target_resources, "w", encoding="utf-8") as f:
            f.write("[]\n")
        print(f"Initialized stub {target_resources}")

catalog_file = os.path.join(res_dir, "list_catalog.json")
if not os.path.exists(catalog_file):
    with open(catalog_file, "w", encoding="utf-8") as f:
        f.write("""{
  "version": 1,
  "lists": [
    {
      "uuid": "default-offline-list",
      "name": "Braving Default Rules (uBlock Defaults)",
      "type": "ad-blocking",
      "desc": "Bundled offline rules based on uBlock Origin defaults",
      "filename": "default_rules.txt",
      "enabled_by_default": true
    }
  ]
}
""")
    print(f"Created {catalog_file}")

rule_files = {
    "default_rules.txt": "! Braving default offline ad-blocking rules\n! Sourced from uBlock Origin & EasyList\n||googleads.g.doubleclick.net^\n||pagead2.googlesyndication.com^\n",
    "tracker_rules.txt": "! Braving default offline tracker rules\n! Sourced from EasyPrivacy\n||google-analytics.com^\n",
    "first_party_rules.txt": "! Braving offline first-party rules\n",
    "cookie_rules.txt": "! Braving offline cookie rules\n",
    "mobile_rules.txt": "! Braving offline mobile rules\n"
}

for fname, default_content in rule_files.items():
    fpath = os.path.join(res_dir, fname)
    if not os.path.exists(fpath):
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(default_content)
        print(f"Created rule file: {fpath}")


# 1. BUILD.gn deps
patch_file("components/brave_shields/core/browser/BUILD.gn",
           '    "//base",',
           '    "//base",\n    "//brave/components/resources",\n    "//ui/base",')


# 2. AdBlockComponentFiltersProvider
patch_file("components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
           '#include "brave/components/brave_shields/core/browser/ad_block_component_filters_provider.h"',
           '#include "brave/components/brave_shields/core/browser/ad_block_component_filters_provider.h"\n\n#include "brave/components/resources/grit/brave_components_resources.h"\n#include "ui/base/resource/resource_bundle.h"')

helper_fn = """namespace {

int GetFallbackResourceIdForComponent(const std::string& component_id) {
  if (component_id == "iodkpdagapdfkphljnddpjlldadblomo") return IDR_BRAVE_SHIELDS_DEFAULT_RULES;
  if (component_id == "kihnoaefogbkmblfimmibknnmkllbhlf") return IDR_BRAVE_SHIELDS_TRACKER_RULES;
  if (component_id == "adcocjohghhfpidemphmcmlmhnfgikei") return IDR_BRAVE_SHIELDS_FIRST_PARTY_RULES;
  if (component_id == "cdbbhgbmjhfnhnmgeddbliobbofkgdhe") return IDR_BRAVE_SHIELDS_COOKIE_RULES;
  if (component_id == "bfpgedeaaibpoidldhjcknekahbikncb") return IDR_BRAVE_SHIELDS_MOBILE_RULES;
  return 0;
}
"""
patch_file("components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
           "namespace {\n",
           helper_fn)

patch_file("components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
           "bool AdBlockComponentFiltersProvider::IsInitialized() const {\n  return !component_path_.empty();\n}",
           "bool AdBlockComponentFiltersProvider::IsInitialized() const {\n  if (!component_path_.empty()) return true;\n  return GetFallbackResourceIdForComponent(component_id_) != 0;\n}")

fallback_filter_load = """  if (list_file_path.empty()) {
    int resource_id = GetFallbackResourceIdForComponent(component_id_);
    if (resource_id != 0 && ui::ResourceBundle::HasSharedInstance()) {
      base::ThreadPool::PostTaskAndReplyWithResult(
          FROM_HERE, {base::MayBlock()},
          base::BindOnce([](int id) -> DATFileDataBuffer {
            std::string data = ui::ResourceBundle::GetSharedInstance().LoadDataResourceString(id);
            return DATFileDataBuffer(data.begin(), data.end());
          }, resource_id),
          base::BindOnce(&OnReadDATFileData, std::move(cb), permission_mask_, flow));
      return;
    }
    // If the path is not ready yet, provide a no-op callback immediately. An
    // update will be pushed later to notify about the newly available list.
    std::move(cb).Run(base::BindOnce(AddNothingToFilterSet));
    return;
  }"""

patch_file("components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
           """  if (list_file_path.empty()) {
    // If the path is not ready yet, provide a no-op callback immediately. An
    // update will be pushed later to notify about the newly available list.
    std::move(cb).Run(base::BindOnce(AddNothingToFilterSet));
    return;
  }""",
           fallback_filter_load)


# 3. AdBlockDefaultResourceProvider
patch_file("components/brave_shields/core/browser/ad_block_default_resource_provider.cc",
           '#include "brave/components/brave_shields/core/browser/ad_block_default_resource_provider.h"',
           '#include "brave/components/brave_shields/core/browser/ad_block_default_resource_provider.h"\n\n#include "brave/components/resources/grit/brave_components_resources.h"\n#include "ui/base/resource/resource_bundle.h"')

fallback_res_load = """  base::FilePath resources_path = GetResourcesPath();
  if (resources_path.empty()) {
    if (ui::ResourceBundle::HasSharedInstance()) {
      std::string resources_json = ui::ResourceBundle::GetSharedInstance().LoadDataResourceString(IDR_BRAVE_SHIELDS_RESOURCES_JSON);
      if (!resources_json.empty()) {
        base::ThreadPool::PostTaskAndReplyWithResult(
            FROM_HERE, {base::MayBlock()},
            base::BindOnce([](std::string json) { return adblock::new_resource_storage(json); }, std::move(resources_json)),
            std::move(cb));
        return;
      }
    }
    // If the path is not ready yet, run the callback with empty resources to
    // avoid blocking filter data loads.
    auto empty_storage = adblock::new_empty_resource_storage();
    std::move(cb).Run(std::move(empty_storage));
    return;
  }"""

patch_file("components/brave_shields/core/browser/ad_block_default_resource_provider.cc",
           """  base::FilePath resources_path = GetResourcesPath();
  if (resources_path.empty()) {
    // If the path is not ready yet, run the callback with empty resources to
    // avoid blocking filter data loads.
    auto empty_storage = adblock::new_empty_resource_storage();
    std::move(cb).Run(std::move(empty_storage));
    return;
  }""",
           fallback_res_load)


# 4. AdBlockFilterListCatalogProvider
patch_file("components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.cc",
           '#include "brave/components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.h"',
           '#include "brave/components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.h"\n\n#include "brave/components/resources/grit/brave_components_resources.h"\n#include "ui/base/resource/resource_bundle.h"')

fallback_cat_load = """void AdBlockFilterListCatalogProvider::LoadFilterListCatalog(
    base::OnceCallback<void(const std::string& catalog_json)> cb) {
  if (component_path_.empty()) {
    if (ui::ResourceBundle::HasSharedInstance()) {
      std::string catalog_json = ui::ResourceBundle::GetSharedInstance().LoadDataResourceString(IDR_BRAVE_SHIELDS_LIST_CATALOG);
      if (!catalog_json.empty()) {
        base::ThreadPool::PostTaskAndReplyWithResult(
            FROM_HERE, {base::MayBlock()},
            base::BindOnce([](std::string json) { return json; }, std::move(catalog_json)),
            std::move(cb));
        return;
      }
    }
    // If the path is not ready yet, don't run the callback. An update should be
    // pushed soon.
    return;
  }"""

patch_file("components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.cc",
           """void AdBlockFilterListCatalogProvider::LoadFilterListCatalog(
    base::OnceCallback<void(const std::string& catalog_json)> cb) {
  if (component_path_.empty()) {
    // If the path is not ready yet, don't run the callback. An update should be
    // pushed soon.
    return;
  }""",
           fallback_cat_load)


# 5. components/resources/brave_components_resources.grd
patch_file("components/resources/brave_components_resources.grd",
           """      <if expr="not is_android">
        <part file="brave_shields_resources.grdp" />
        <part file="brave_private_new_tab_resources.grdp" />
      </if>""",
           """      <part file="brave_shields_resources.grdp" />
      <if expr="not is_android">
        <part file="brave_private_new_tab_resources.grdp" />
      </if>""")


# 6. components/resources/brave_shields_resources.grdp
grdp_includes = """  <include name="IDR_BRAVE_SHIELDS_LIST_CATALOG" file="../brave_shields/resources/list_catalog.json" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_RESOURCES_JSON" file="../brave_shields/resources/resources.json" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_DEFAULT_RULES" file="../brave_shields/resources/default_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_TRACKER_RULES" file="../brave_shields/resources/tracker_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_FIRST_PARTY_RULES" file="../brave_shields/resources/first_party_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_COOKIE_RULES" file="../brave_shields/resources/cookie_rules.txt" type="BINDATA" />
  <include name="IDR_BRAVE_SHIELDS_MOBILE_RULES" file="../brave_shields/resources/mobile_rules.txt" type="BINDATA" />
</grit-part>"""

patch_file("components/resources/brave_shields_resources.grdp",
           "</grit-part>",
           grdp_includes)


# 7. Update component updater endpoints
patch_file("components/update_client/BUILD.gn",
           '"https://go-updater.brave.com/extensions"',
           '"https://updates.braving.org/components"')

patch_file("components/update_client/BUILD.gn",
           '"https://go-updater-dev.bravesoftware.com/extensions"',
           '"https://updates.braving.org/components"')

patch_file("browser/net/brave_network_audit_allowed_lists.h",
           '"https://go-updater.brave.com/",',
           '"https://updates.braving.org/components/",')

print("Successfully applied Shields offline fallback, resource bundling, and updater endpoints!")
