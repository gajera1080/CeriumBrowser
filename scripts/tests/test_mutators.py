#!/usr/bin/env python3
"""
Cerium Test Suite: Python Mutators and Git Patch Suite
Validates that:
1. Python 3.11 syntax compatibility is maintained across all scripts and embedded heredocs.
2. Dynamic GN array mutators (apply-features.py) execute properly and idempotently.
3. Cerium UI string branding and XTB localization mutators (apply-branding.py) execute properly and idempotently.
4. Git patch suite (branding, custom updater endpoint, debloat policies) applies cleanly.
"""

import os
import re
import sys
import tempfile
import subprocess
import shutil

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def setup_mock_brave(brave_dir):
    webui_build_gn = os.path.join(brave_dir, "ui/webui/resources/BUILD.gn")
    webui_sources_gni = os.path.join(brave_dir, "ui/webui/resources/sources.gni")
    nala_build_gn = os.path.join(brave_dir, "android/nala/BUILD.gn")
    brave_java_res_gni = os.path.join(brave_dir, "android/brave_java_resources.gni")
    branding_js = os.path.join(brave_dir, "build/commands/lib/branding.js")
    search_widget_layout = os.path.join(brave_dir, "android/java/brave-res/layout/quick_action_search_and_bookmark_widget_layout.xml")
    quick_search_view_adapter = os.path.join(brave_dir, "browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/views/QuickSearchEnginesViewAdapter.java")
    quick_search_adapter = os.path.join(brave_dir, "browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/settings/QuickSearchEnginesAdapter.java")
    qse_build_gn = os.path.join(brave_dir, "browser/quick_search_engines/android/BUILD.gn")
    brave_flags_overrides = os.path.join(brave_dir, "components/flags_ui/resources/brave_flags_overrides.js")
    brave_content_client = os.path.join(brave_dir, "common/brave_content_client.cc")
    user_agent_utils = os.path.join(brave_dir, "chromium_src/components/embedder_support/user_agent_utils.cc")
    brave_content_browser_client = os.path.join(brave_dir, "browser/brave_content_browser_client.cc")
    brave_user_agent_exceptions = os.path.join(brave_dir, "components/brave_user_agent/browser/brave_user_agent_exceptions.cc")
    brave_shields_features = os.path.join(brave_dir, "components/brave_shields/core/common/features.cc")
    brave_shields_settings_values_h = os.path.join(brave_dir, "components/brave_shields/core/common/brave_shields_settings_values.h")
    ntp_view_counter_pref_registry_cc = os.path.join(brave_dir, "components/ntp_background_images/common/view_counter_pref_registry.cc")
    brave_profile_prefs_cc = os.path.join(brave_dir, "browser/brave_profile_prefs.cc")
    bottom_toolbar_config_java = os.path.join(brave_dir, "android/java/org/chromium/chrome/browser/toolbar/bottom/BottomToolbarConfiguration.java")
    brave_toolbar_manager_java = os.path.join(brave_dir, "android/java/org/chromium/chrome/browser/toolbar/BraveToolbarManager.java")
    ntp_util_java = os.path.join(brave_dir, "android/java/org/chromium/chrome/browser/ntp/NtpUtil.java")
    origin_branding = os.path.join(brave_dir, "app/theme/brave_origin/BRANDING")
    origin_branding_beta = os.path.join(brave_dir, "app/theme/brave_origin/BRANDING.beta")
    origin_branding_dev = os.path.join(brave_dir, "app/theme/brave_origin/BRANDING.development")
    origin_branding_nightly = os.path.join(brave_dir, "app/theme/brave_origin/BRANDING.nightly")

    for p in [webui_build_gn, webui_sources_gni, nala_build_gn, brave_java_res_gni, branding_js, search_widget_layout, quick_search_view_adapter, quick_search_adapter, qse_build_gn, brave_flags_overrides, brave_content_client, user_agent_utils, brave_content_browser_client, brave_user_agent_exceptions, brave_shields_features, brave_shields_settings_values_h, ntp_view_counter_pref_registry_cc, brave_profile_prefs_cc, bottom_toolbar_config_java, brave_toolbar_manager_java, ntp_util_java, origin_branding, origin_branding_beta, origin_branding_dev, origin_branding_nightly]:
        os.makedirs(os.path.dirname(p), exist_ok=True)

    with open(webui_build_gn, "w") as f:
        f.write("""group("grdp") {
  public_deps = [
    ":external_js_bundles",
    ":fonts_grdp",
    ":icons_grdp",
    ":static_grdp",
    "//brave/components/brave_account/resources/opaque_ke",
  ]
  if (include_polymer) {
    public_deps += [ ":build_grdp" ]
  }
}
""")

    with open(webui_sources_gni, "w") as f:
        f.write("""brave_resources_extra_grdps = [
  "$brave_resources_extra_grdps_path/brave_fonts_resources.grdp",
  "$brave_resources_extra_grdps_path/brave_icons_resources.grdp",
  "$brave_resources_extra_grdps_path/brave_static_resources.grdp",
  "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
  "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
]

brave_resources_extra_grdps_deps = [ "//brave/ui/webui/resources:grdp" ]

# At the moment, all non-static resources are only required for polymer WebUI.
# This could change and, when it does, the `include_polymer` conditional can be
# removed here and the one in //brave/ui/webui/resources/BUILD.gn be relied on
# to only add polymer-related files when appropriate.
if (!is_android && !is_ios) {
  brave_resources_extra_grdps +=
      [ "$brave_resources_extra_grdps_path/resources.grdp" ]
}
""")

    with open(nala_build_gn, "w") as f:
        f.write("""_nala_override_deps = []
foreach(override, nala_icon_overrides) {
  _name = "nala_override_" + string_replace(override.dest, ".xml", "")
  copy(_name) {
    sources = [ "$nala_base_path/drawable/${override.source}" ]
    outputs = [ "$target_gen_dir/res/drawable/${override.dest}" ]
  }
  _nala_override_deps += [ ":$_name" ]
}

copy("nala_icons") {
  sources = []
  foreach(icon, nala_icons) {
    sources +=
        [ "//brave/node_modules/@brave/leo/tokens/android/drawable/$icon" ]
  }
  outputs = [ "$target_gen_dir/res/drawable/{{source_file_part}}" ]
}
""")

    with open(brave_java_res_gni, "w") as f:
        f.write("""brave_base_module_resources =
    [ "java/res_chromium_base/drawable-night/themed_app_icon.xml" ]
""")

    with open(branding_js, "w") as f:
        f.write("""  // Replace chrome dark logo with channel specific brave logo.
  fileMap.add([
    path.join(
      config.braveCoreDir,
      'node_modules',
      '@brave',
      'leo',
      'icons',
      config.getBraveLogoIconName(),
    ),
    path.join(
      config.srcDir,
      'ui',
      'webui',
      'resources',
      'images',
      'chrome_logo_dark.svg',
    ),
  ])
""")

    with open(search_widget_layout, "w") as f:
        f.write('<ImageView android:src="@mipmap/app_icon" />\n')

    with open(quick_search_view_adapter, "w") as f:
        f.write("""quickSearchViewHolder.mSearchEngineLogo.setImageResource(
                    R.drawable.ic_social_brave_release_favicon_fullheight_color);\n""")

    with open(quick_search_adapter, "w") as f:
        f.write("""quickSearchEnginesSettingsViewHolder.mSearchEngineLogo.setImageResource(
                    R.drawable.ic_social_brave_release_favicon_fullheight_color);\n""")

    with open(qse_build_gn, "w") as f:
        f.write('''android_resources("java_resources") {
  sources = [
    "java/res/drawable/ic_leo_icon.xml",
    "java/res/drawable/ic_microsoft_color.xml",
    "java/res/drawable/ic_social_youtube.xml",
    "java/res/drawable/ic_startpage_color.xml",
    "java/res/layout/fragment_quick_search.xml",
  ]
}
''')

    with open(brave_flags_overrides, "w") as f:
        f.write('''/* Copyright (c) 2020 The Brave Authors. All rights reserved.
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this file,
 * You can obtain one at https://mozilla.org/MPL/2.0/. */

document.addEventListener('DOMContentLoaded', function () {
  const flagsApp = document.querySelector('flags-app')
  if (flagsApp) {
    flagsApp.shadowRoot.querySelectorAll(
      '#channel-promo-beta, #channel-promo-dev').forEach((node, index) => {
       const text1 = document.createTextNode('Interested in cool new Brave features? Try our ')
       const text2 = document.createTextNode('.')
       const link = document.createElement('a')
       node.textContent = ''
       node.appendChild(text1)
       node.appendChild(link)
       node.appendChild(text2)
       if (index === 0) {
         link.setAttribute('href', 'https://brave.com/download-beta/')
         link.textContent = 'beta channel'
       } else {
         link.setAttribute('href', 'https://brave.com/download-nightly/')
         link.textContent = 'nightly channel'
       }
     })
    flagsApp.shadowRoot.querySelector('div.blurb-container').after(
      (() => {
        const p = document.createElement('p')
        p.textContent = '* Overridden by active variations or a command line.'
        return p
      })()
    )
  }
});
''')

    with open(brave_content_client, "w") as f:
        f.write("""scoped_refptr<base::RefCountedMemory> BraveContentClient::GetDataResourceBytes(
    int resource_id) {
  if (resource_id == IDR_FLAGS_UI_APP_JS) {
    const ui::ResourceBundle& resource_bundle =
        ui::ResourceBundle::GetSharedInstance();
    const std::string flags_js =
        resource_bundle.LoadDataResourceString(resource_id) +
        resource_bundle.LoadDataResourceString(
            IDR_FLAGS_UI_BRAVE_FLAGS_OVERRIDES_JS);
    auto bytes = base::MakeRefCounted<base::RefCountedString>();
    bytes->as_string().assign(flags_js.data(), flags_js.length());
    return bytes;
  }
  return ChromeContentClient::GetDataResourceBytes(resource_id);
}
""")

    with open(user_agent_utils, "w") as f:
        f.write("""namespace {
constexpr char kBraveBrandNameForCHUA[] = "Brave";
}  // namespace

#define BRAVE_GET_USER_AGENT_BRAND_LIST brand = kBraveBrandNameForCHUA;

#define BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE \\
  base::StrCat({major_version, ".0.0.0"})
""")

    with open(brave_content_browser_client, "w") as f:
        f.write("""blink::UserAgentMetadata BraveContentBrowserClient::GetUserAgentMetadata() {
  blink::UserAgentMetadata metadata =
      ChromeContentBrowserClient::GetUserAgentMetadata();
  base::CommandLine* command_line = base::CommandLine::ForCurrentProcess();
  if (command_line->HasSwitch(embedder_support::kUserAgent)) {
    return metadata;
  }
  DCHECK_EQ(3UL, metadata.brand_version_list.size());
  for (auto& brand_version : metadata.brand_full_version_list) {
    base::Version version(brand_version.version);
    brand_version.version =
        base::StrCat({base::NumberToString(version.components()[0]), ".0.0.0"});
  }
  base::Version version(metadata.full_version);
  metadata.full_version =
      base::StrCat({base::NumberToString(version.components()[0]), ".0.0.0"});
  return metadata;
}
""")

    with open(brave_user_agent_exceptions, "w") as f:
        f.write("""bool BraveUserAgentExceptions::CanShowBrave(const GURL& url) {
  if (!is_ready_) {
    return true;
  }
  std::string domain = net::registry_controlled_domains::GetDomainAndRegistry(
      url, net::registry_controlled_domains::INCLUDE_PRIVATE_REGISTRIES);
  return !excepted_domains_.contains(domain);
}

bool ShouldHideBraveBrand(const GURL& url) {
  auto* exceptions = BraveUserAgentExceptions::GetInstance();
  return exceptions && !exceptions->CanShowBrave(url);
}
""")

    with open(brave_shields_features, "w") as f:
        f.write("""// Copyright (c) 2020 The Brave Authors. All rights reserved.
namespace brave_shields::features {
BASE_FEATURE(kBraveAdblockDefault1pBlocking, base::FEATURE_DISABLED_BY_DEFAULT);
}
""")

    with open(brave_shields_settings_values_h, "w") as f:
        f.write("""using CosmeticFilteringSetting = traits::BraveShieldsSetting<
    /*content_settings_type=*/ContentSettingsType::BRAVE_COSMETIC_FILTERING,
    /*SettingType=*/ControlType,
    /*default_value=*/ControlType::BLOCK_THIRD_PARTY>;
""")

    with open(ntp_view_counter_pref_registry_cc, "w") as f:
        f.write("registry->RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, true);\n")

    with open(brave_profile_prefs_cc, "w") as f:
        f.write("""registry->RegisterBooleanPref(kNewTabPageShowStats, true);
  registry->SetDefaultPrefValue(ntp_prefs::kNtpCustomLinksVisible,
                                base::Value(false));
""")

    with open(bottom_toolbar_config_java, "w") as f:
        f.write("""        if (ChromeSharedPreferences.getInstance()
                .readBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_SET_KEY, false)) {
            return ChromeSharedPreferences.getInstance()
                    .readBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, true);
        } else {
            ChromeSharedPreferences.getInstance()
                    .writeBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_SET_KEY, true);
            boolean enable = true;
            if (isSmallScreen()) {
                enable = false;
            }
            ChromeSharedPreferences.getInstance()
                    .writeBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, enable);

            return enable;
        }

    private static boolean isSmallScreen() {
        return false;
    }
""")

    with open(brave_toolbar_manager_java, "w") as f:
        f.write("""            if (sharedPreferences.getBoolean(
                    BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, true)) {
""")

    with open(ntp_util_java, "w") as f:
        f.write("""    public static boolean shouldDisplayTopSites() {
        return ChromeSharedPreferences.getInstance()
                .readBoolean(BackgroundImagesPreferences.PREF_SHOW_TOP_SITES, true);
    }

    public static boolean shouldDisplayBraveStats() {
        return ChromeSharedPreferences.getInstance()
                .readBoolean(BackgroundImagesPreferences.PREF_SHOW_BRAVE_STATS, true);
    }
""")

    with open(origin_branding, "w") as f:
        f.write("""COMPANY_FULLNAME=Brave Software, Inc.
COMPANY_SHORTNAME=Brave Software
PRODUCT_FULLNAME=Brave Origin
PRODUCT_SHORTNAME=Brave Origin
PRODUCT_INSTALLER_FULLNAME=Brave Origin Installer
PRODUCT_INSTALLER_SHORTNAME=Brave Origin Installer
""")

    with open(origin_branding_beta, "w") as f:
        f.write("""COMPANY_FULLNAME=Brave Software, Inc.
COMPANY_SHORTNAME=Brave Software
PRODUCT_FULLNAME=Brave Origin Beta
PRODUCT_SHORTNAME=Brave Origin Beta
PRODUCT_INSTALLER_FULLNAME=Brave Origin Installer
PRODUCT_INSTALLER_SHORTNAME=Brave Origin Installer
""")

    with open(origin_branding_dev, "w") as f:
        f.write("""COMPANY_FULLNAME=Brave Software, Inc.
COMPANY_SHORTNAME=Brave Software
PRODUCT_FULLNAME=Brave Origin Development
PRODUCT_SHORTNAME=Brave Origin Development
PRODUCT_INSTALLER_FULLNAME=Brave Origin Installer
PRODUCT_INSTALLER_SHORTNAME=Brave Origin Installer
""")

    with open(origin_branding_nightly, "w") as f:
        f.write("""COMPANY_FULLNAME=Brave Software, Inc.
COMPANY_SHORTNAME=Brave Software
PRODUCT_FULLNAME=Brave Origin Nightly
PRODUCT_SHORTNAME=Brave Origin Nightly
PRODUCT_INSTALLER_FULLNAME=Brave Origin Installer
PRODUCT_INSTALLER_SHORTNAME=Brave Origin Installer
""")

    pref_registry_cc = os.path.join(brave_dir, "components/brave_ads/core/internal/prefs/pref_registry.cc")
    install_worker_cc = os.path.join(brave_dir, "chromium_src/chrome/installer/setup/install_worker.cc")
    mini_installer_cc = os.path.join(brave_dir, "chromium_src/chrome/installer/mini_installer/mini_installer.cc")
    chromium_install_modes_h = os.path.join(brave_dir, "chromium_src/chrome/install_static/chromium_install_modes.h")
    brave_shell_util_cc = os.path.join(brave_dir, "installer/util/brave_shell_util.cc")

    for p in [pref_registry_cc, install_worker_cc, mini_installer_cc, chromium_install_modes_h, brave_shell_util_cc]:
        os.makedirs(os.path.dirname(p), exist_ok=True)

    with open(pref_registry_cc, "w") as f:
        f.write("registry->RegisterBooleanPref(prefs::kSponsoredEnabled, true);\n")

    with open(install_worker_cc, "w") as f:
        f.write("""void UpdateBraveVpn(const base::FilePath& target_path,
                    const base::Version& new_version,
                    WorkItemList* install_list) {
  // When one time cleanup happens, we don't want to install the services at
  // that time. Service will be installed at the time of purchase.
  if (OneTimeVpnServiceCleanup(target_path, new_version, install_list)) {
    return;
  }

  // If the VPN service is installed, we should update installed services to
  // make it have latest executable path.
  if (brave_vpn::IsBraveVPNHelperServiceInstalled()) {
    install_list->AddCallbackWorkItem(
        base::BindOnce(
            [](const base::FilePath& target_path, const CallbackWorkItem&) {
              return brave_vpn::InstallBraveVPNHelperService(target_path);
            },
            target_path.AppendASCII(new_version.GetString())),
        base::DoNothing());
  }
}
""")

    with open(mini_installer_cc, "w") as f:
        f.write("""  const bool result = RegKey::ReadSZValue( \\
      HKEY_CURRENT_USER, L"Software\\\\BraveSoftware\\\\Promo", \\
      L"StubInstallerPath", value, _countof(value)); \\
""")

    with open(chromium_install_modes_h, "w") as f:
        f.write("""inline constexpr wchar_t kCompanyPathName[] = L"BraveSoftware";
inline constexpr wchar_t kProductPathName[] = L"Brave-Origin";
inline constexpr wchar_t kProductPathName[] = L"Brave-Browser";
inline constexpr wchar_t kProductPathName[] = L"Brave-Browser-Development";
.base_app_name = L"Brave Origin",
.base_app_id = L"BraveOrigin",
.browser_prog_id_prefix = L"BraveOHTML",
.browser_prog_id_description =
            L"Brave Origin HTML Document",
.pdf_prog_id_prefix = L"BraveOPDF",
.pdf_prog_id_description =
            L"Brave Origin PDF Document",
.base_app_name = L"Brave",
.base_app_id = L"Brave",
.browser_prog_id_prefix = L"BraveHTML",
.browser_prog_id_description =
            L"Brave HTML Document",
.pdf_prog_id_prefix = L"BravePDF",
.pdf_prog_id_description =
            L"Brave PDF Document",
""")

    with open(brave_shell_util_cc, "w") as f:
        f.write("""std::wstring GetProgIdForFileType() {
  switch (install_static::GetChromeChannel()) {
    case version_info::Channel::STABLE:
      return L"BraveFile";
    case version_info::Channel::BETA:
      return L"BraveBFile";
    case version_info::Channel::DEV:
      return L"BraveDFile";
    case version_info::Channel::CANARY:
      return L"BraveSSFile";
    default:
      break;
  }
}
""")

    return {
        "webui_build_gn": webui_build_gn,
        "webui_sources_gni": webui_sources_gni,
        "nala_build_gn": nala_build_gn,
        "brave_java_res_gni": brave_java_res_gni,
        "branding_js": branding_js,
        "search_widget_layout": search_widget_layout,
        "quick_search_view_adapter": quick_search_view_adapter,
        "quick_search_adapter": quick_search_adapter,
        "qse_build_gn": qse_build_gn,
        "brave_flags_overrides": brave_flags_overrides,
        "brave_content_client": brave_content_client,
        "user_agent_utils": user_agent_utils,
        "brave_content_browser_client": brave_content_browser_client,
        "brave_user_agent_exceptions": brave_user_agent_exceptions,
        "brave_shields_features": brave_shields_features,
        "brave_shields_settings_values_h": brave_shields_settings_values_h,
        "ntp_view_counter_pref_registry_cc": ntp_view_counter_pref_registry_cc,
        "brave_profile_prefs_cc": brave_profile_prefs_cc,
        "bottom_toolbar_config_java": bottom_toolbar_config_java,
        "brave_toolbar_manager_java": brave_toolbar_manager_java,
        "ntp_util_java": ntp_util_java,
        "origin_branding": origin_branding,
        "origin_branding_beta": origin_branding_beta,
        "origin_branding_dev": origin_branding_dev,
        "origin_branding_nightly": origin_branding_nightly,
        "pref_registry_cc": pref_registry_cc,
        "install_worker_cc": install_worker_cc,
        "mini_installer_cc": mini_installer_cc,
        "chromium_install_modes_h": chromium_install_modes_h,
        "brave_shell_util_cc": brave_shell_util_cc,
    }


def setup_mock_src(src_dir):
    chrome_ver_gni = os.path.join(src_dir, "chrome/version.gni")
    ver_values = os.path.join(src_dir, "base/version_info/version_info_values.h.version")
    ver_consts = os.path.join(src_dir, "base/version_info/android/java/VersionConstants.java.version")
    ver_strings = os.path.join(src_dir, "chrome/android/java/version_strings.xml.template")
    timestamp_gni = os.path.join(src_dir, "build/timestamp.gni")
    ts_split_file = os.path.join(src_dir, "third_party/devtools-frontend/src/scripts/build/typescript/ts_library_split.gni")
    skills_build_gn = os.path.join(src_dir, "third_party/devtools-frontend/src/front_end/models/ai_assistance/skills/BUILD.gn")
    chrome_android_build_gn = os.path.join(src_dir, "chrome/android/BUILD.gn")
    ver_ua_cc = os.path.join(src_dir, "components/version_info/version_info_with_user_agent.cc")
    chrome_browser_prefs_cc = os.path.join(src_dir, "chrome/browser/prefs/browser_prefs.cc")
    most_visited_pref_observer_cc = os.path.join(src_dir, "chrome/browser/ui/webui/cr_components/most_visited/most_visited_pref_observer.cc")

    for p in [chrome_ver_gni, ver_values, ver_consts, ver_strings, timestamp_gni, ts_split_file, skills_build_gn, chrome_android_build_gn, ver_ua_cc, chrome_browser_prefs_cc, most_visited_pref_observer_cc]:
        os.makedirs(os.path.dirname(p), exist_ok=True)

    with open(chrome_browser_prefs_cc, "w") as f:
        f.write("registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, true);\n")

    with open(most_visited_pref_observer_cc, "w") as f:
        f.write("registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, true);\n")

    with open(ver_ua_cc, "w") as f:
        f.write("""#include "components/version_info/version_info_with_user_agent.h"

namespace version_info {

std::string GetProductNameAndVersionForReducedUserAgent() {
  return base::StrCat({"Chrome/", GetMajorVersionNumber(), ".0.0.0"});
}

}  // namespace version_info
""")

    with open(timestamp_gni, "w") as f:
        f.write("""# Copyright 2018 The Chromium Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Defines the build_timestamp variable.

import("//build/util/lastchange.gni")

if (is_android) {
  import("//build/config/android/abi.gni")

  # Ensure the exec_script() runs only once in default debug configs to
  # minimize "gn gen" overhead.
  if (!enable_android_secondary_abi) {
    assert(
        current_toolchain == default_toolchain,
        "Trying to run compute_build_timestamp.py in toolchain: $current_toolchain")
  }
}

declare_args() {
  compute_build_timestamp = "compute_build_timestamp.py"
}

if (is_official_build) {
  official_name = "official"
} else {
  official_name = "default"
}

build_timestamp = exec_script(compute_build_timestamp,
                              [ official_name ],
                              "trim string",
                              [ lastchange_file ])
""")

    with open(chrome_ver_gni, "w") as f:
        f.write("  chrome_version_name = chrome_version_full\n")

    with open(ver_values, "w") as f:
        f.write('#define PRODUCT_VERSION "@MAJOR@.@MINOR@.@BUILD@.@PATCH@"\n')

    with open(ver_consts, "w") as f:
        f.write('    public static final String PRODUCT_VERSION = "@MAJOR@.@MINOR@.@BUILD@.@PATCH@";\n')

    with open(ver_strings, "w") as f:
        f.write('  <string name="product_version" translatable="false" tools:ignore="UnusedResources">@MAJOR@.@MINOR@.@BUILD@.@PATCH@</string>\n')


    with open(ts_split_file, "w") as f:
        f.write('''template("ts_library_split") {
  if (true) {
    public_inputs = filter_include(_all_sources, [ "*.ts" ])
    sources = _all_sources
  }
  if (false) {
    public_inputs = filter_include(_dts_outputs, [ "*.d.ts" ]) +
                    filter_include(_all_sources, [ "*.d.ts" ])
    deps = []
  }
}
''')

    with open(skills_build_gn, "w") as f:
        f.write('''action_foreach("generate_skills") {
  script = "//third_party/node/node.py"
  sources = [ "accessibility.md" ]
  public_inputs =
      process_file_template(_skill_sources,
                            [
                              "{{source_name_part}}.md",
                            ])
  outputs = [ "$target_gen_dir/{{source_name_part}}.skill.js" ]
}
''')

    with open(chrome_android_build_gn, "w") as f:
        f.write('''# Mock chrome/android/BUILD.gn
_is_default_toolchain = current_toolchain == default_toolchain

# Used by android-binary-size trybot to validate expectations.
if (_is_default_toolchain &&
    (enable_libs_and_assets_verification || enable_manifest_verification)) {
  assert(android_64bit_target_cpu, "Can only do expectations on 64 bit bots")
  group("validate_expectations") {
    deps = []
    if (enable_libs_and_assets_verification) {
      deps += [
        ":trichrome_chrome_32_64_bundle_validate_libs_and_assets",
        ":trichrome_chrome_32_bundle_validate_libs_and_assets",
        ":trichrome_chrome_64_32_bundle_validate_libs_and_assets",
        ":trichrome_chrome_64_bundle_validate_libs_and_assets",
        ":trichrome_library_32_64_apk_validate_libs_and_assets",
        ":trichrome_library_32_apk_validate_libs_and_assets",
        ":trichrome_library_64_32_apk_validate_libs_and_assets",
        ":trichrome_library_64_apk_validate_libs_and_assets",
        "//android_webview:trichrome_webview_32_64_bundle_validate_libs_and_assets",
        "//android_webview:trichrome_webview_32_bundle_validate_libs_and_assets",
        "//android_webview:trichrome_webview_64_32_bundle_validate_libs_and_assets",
        "//android_webview:trichrome_webview_64_bundle_validate_libs_and_assets",
      ]
    }
    if (enable_manifest_verification) {
      deps += [
        ":trichrome_chrome_32_64_bundle__base_bundle_module_validate_android_manifest",
        ":trichrome_chrome_32_bundle__base_bundle_module_validate_android_manifest",
        ":trichrome_chrome_64_32_bundle__base_bundle_module_validate_android_manifest",
        ":trichrome_chrome_64_32_bundle_validate_manifests",
        ":trichrome_chrome_64_32_bundle_validate_proguard_config",
        ":trichrome_chrome_64_bundle__base_bundle_module_validate_android_manifest",
        ":trichrome_library_32_64_apk_validate_android_manifest",
        ":trichrome_library_32_apk_validate_android_manifest",
        ":trichrome_library_64_32_apk_validate_android_manifest",
        ":trichrome_library_64_apk_validate_android_manifest",
        "//android_webview:system_webview_32_64_base_bundle_module_validate_android_manifest",
        "//android_webview:system_webview_32_base_bundle_module_validate_android_manifest",
        "//android_webview:system_webview_64_32_base_bundle_module_validate_android_manifest",
        "//android_webview:system_webview_64_base_bundle_module_validate_android_manifest",
        "//android_webview:trichrome_webview_32_64_base_bundle_module_validate_android_manifest",
        "//android_webview:trichrome_webview_32_base_bundle_module_validate_android_manifest",
        "//android_webview:trichrome_webview_64_32_base_bundle_module_validate_android_manifest",
        "//android_webview:trichrome_webview_64_32_bundle_validate_proguard_config",
        "//android_webview:trichrome_webview_64_base_bundle_module_validate_android_manifest",
      ]
    }
  }
}
''')
    return {
        "timestamp_gni": timestamp_gni,
        "chrome_ver_gni": chrome_ver_gni,
        "ver_values": ver_values,
        "ver_consts": ver_consts,
        "ver_strings": ver_strings,
        "ts_split_file": ts_split_file,
        "skills_build_gn": skills_build_gn,
        "chrome_android_build_gn": chrome_android_build_gn,
        "ver_ua_cc": ver_ua_cc,
        "chrome_browser_prefs_cc": chrome_browser_prefs_cc,
        "most_visited_pref_observer_cc": most_visited_pref_observer_cc,
    }


def test_apply_features():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Setup mock files for apply-features
        mock_files = setup_mock_brave(tmpdir)
        webui_build_gn = mock_files["webui_build_gn"]
        webui_sources_gni = mock_files["webui_sources_gni"]
        nala_build_gn = mock_files["nala_build_gn"]
        brave_java_res_gni = mock_files["brave_java_res_gni"]
        branding_js = mock_files["branding_js"]
        search_widget_layout = mock_files["search_widget_layout"]
        quick_search_view_adapter = mock_files["quick_search_view_adapter"]
        quick_search_adapter = mock_files["quick_search_adapter"]
        qse_build_gn = mock_files["qse_build_gn"]
        brave_flags_overrides = mock_files["brave_flags_overrides"]
        brave_shields_features = mock_files["brave_shields_features"]

        script = os.path.join(REPO_ROOT, "scripts/core/apply-features.py")
        res = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res.returncode == 0, f"apply-features failed: {res.stderr}\n{res.stdout}"

        # Check modifications
        with open(webui_build_gn) as f:
            c = f.read()
            assert ":external_js_bundles" not in c.split("if (include_polymer)")[0]
            assert ":external_js_bundles" in c.split("if (include_polymer)")[1]

        with open(webui_sources_gni) as f:
            c = f.read()
            assert "if (!is_android && !is_ios) {" in c

        with open(nala_build_gn) as f:
            c = f.read()
            assert "//brave/app/theme/brave/android/shields_drawables/" in c
            assert "ic_social_brave_monochrome_favicon_fullheight_color.xml" in c

        with open(brave_java_res_gni) as f:
            c = f.read()
            assert "java/res_chromium_base/mipmap-anydpi-v26/app_icon.xml" in c
            assert "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon.xml" in c
            assert "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon_background.xml" in c

        with open(branding_js) as f:
            c = f.read()
            assert "'product_logo.svg'" in c

        with open(search_widget_layout) as f:
            assert 'android:src="@drawable/brave_icon_search"' in f.read()

        with open(quick_search_view_adapter) as f:
            assert 'R.drawable.ic_brave_icon_search' in f.read()

        with open(quick_search_adapter) as f:
            assert 'R.drawable.ic_brave_icon_search' in f.read()

        with open(qse_build_gn) as f:
            qse_content = f.read()
            assert '"java/res/drawable/brave_icon_search.xml"' not in qse_content
            assert 'android_resources("java_resources")' in qse_content

        brave_content_client = mock_files["brave_content_client"]
        user_agent_utils = mock_files["user_agent_utils"]
        brave_content_browser_client = mock_files["brave_content_browser_client"]
        brave_user_agent_exceptions = mock_files["brave_user_agent_exceptions"]

        with open(brave_flags_overrides) as f:
            bfo_content = f.read()
            assert "document.addEventListener('DOMContentLoaded'" not in bfo_content
            assert "Interested in cool new Brave features" not in bfo_content
            assert "// Cerium: Overrides disabled for clean Lit WebUI compatibility" in bfo_content

        with open(brave_content_client) as f:
            bcc_content = f.read()
            assert "return ChromeContentClient::GetDataResourceBytes(resource_id);" in bcc_content
            assert "IDR_FLAGS_UI_APP_JS" not in bcc_content

        with open(user_agent_utils) as f:
            uau_content = f.read()
            assert 'brand = "Google Chrome";' in uau_content
            assert "(void)kBraveBrandNameForCHUA;" in uau_content
            assert "[[maybe_unused]] constexpr char kBraveBrandNameForCHUA" in uau_content
            assert "BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE full_version" in uau_content

        with open(brave_content_browser_client) as f:
            bcbc_content = f.read()
            assert "return ChromeContentBrowserClient::GetUserAgentMetadata();" in bcbc_content
            assert "base::NumberToString(version.components()[0])" not in bcbc_content

        with open(brave_user_agent_exceptions) as f:
            buae_content = f.read()
            assert "return false;" in buae_content
            assert "return true;" in buae_content

        with open(brave_shields_features) as f:
            bsf_content = f.read()
            assert "BASE_FEATURE(kBraveAdblockDefault1pBlocking, base::FEATURE_ENABLED_BY_DEFAULT);" in bsf_content

        origin_branding = mock_files["origin_branding"]
        origin_branding_beta = mock_files["origin_branding_beta"]
        origin_branding_dev = mock_files["origin_branding_dev"]
        origin_branding_nightly = mock_files["origin_branding_nightly"]

        with open(origin_branding) as f:
            ob_content = f.read()
            assert "COMPANY_FULLNAME=Cerium Browser Team" in ob_content
            assert "COMPANY_SHORTNAME=Cerium" in ob_content
            assert "PRODUCT_FULLNAME=Cerium Browser" in ob_content
            assert "PRODUCT_SHORTNAME=Cerium" in ob_content
            assert "PRODUCT_INSTALLER_FULLNAME=Cerium Installer" in ob_content

        with open(origin_branding_beta) as f:
            obb_content = f.read()
            assert "PRODUCT_FULLNAME=Cerium Browser Beta" in obb_content
            assert "PRODUCT_SHORTNAME=Cerium Beta" in obb_content

        with open(origin_branding_dev) as f:
            obd_content = f.read()
            assert "PRODUCT_FULLNAME=Cerium Browser Development" in obd_content
            assert "PRODUCT_SHORTNAME=Cerium Development" in obd_content

        with open(origin_branding_nightly) as f:
            obn_content = f.read()
            assert "PRODUCT_FULLNAME=Cerium Browser Nightly" in obn_content
            assert "PRODUCT_SHORTNAME=Cerium Nightly" in obn_content

        with open(mock_files["pref_registry_cc"]) as f:
            assert "registry->RegisterBooleanPref(prefs::kSponsoredEnabled, false);" in f.read()

        with open(mock_files["brave_shields_settings_values_h"]) as f:
            assert "/*default_value=*/ControlType::BLOCK>;" in f.read()

        with open(mock_files["ntp_view_counter_pref_registry_cc"]) as f:
            assert "registry->RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, false);" in f.read()

        with open(mock_files["brave_profile_prefs_cc"]) as f:
            bpp_content = f.read()
            assert "registry->RegisterBooleanPref(kNewTabPageShowStats, false);" in bpp_content
            assert "registry->SetDefaultPrefValue(ntp_prefs::kNtpShortcutsVisible," in bpp_content

        with open(mock_files["bottom_toolbar_config_java"]) as f:
            btc_content = f.read()
            assert ".readBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, false);" in btc_content
            assert '@SuppressWarnings("unused")' in btc_content

        with open(mock_files["brave_toolbar_manager_java"]) as f:
            assert "BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, false)) {" in f.read()

        with open(mock_files["ntp_util_java"]) as f:
            ntp_u_content = f.read()
            assert ".readBoolean(BackgroundImagesPreferences.PREF_SHOW_TOP_SITES, false);" in ntp_u_content
            assert ".readBoolean(BackgroundImagesPreferences.PREF_SHOW_BRAVE_STATS, false);" in ntp_u_content

        with open(mock_files["install_worker_cc"]) as f:
            assert "// Cerium: Disable VPN NT background service registration" in f.read()

        with open(mock_files["mini_installer_cc"]) as f:
            assert "/* Cerium: Skip promo registry read */" in f.read()

        with open(mock_files["chromium_install_modes_h"]) as f:
            cim_content = f.read()
            assert 'inline constexpr wchar_t kCompanyPathName[] = L"Cerium";' in cim_content
            assert 'inline constexpr wchar_t kProductPathName[] = L"Cerium-Browser";' in cim_content
            assert 'inline constexpr wchar_t kProductPathName[] = L"Brave-Browser";' not in cim_content
            assert 'inline constexpr wchar_t kProductPathName[] = L"Brave-Origin";' not in cim_content
            assert '.browser_prog_id_prefix = L"CeriumHTML"' in cim_content

        with open(mock_files["brave_shell_util_cc"]) as f:
            assert 'return L"CeriumFile";' in f.read()

        with open(origin_branding, "w") as f:
            f.write(ob_content.replace("PRODUCT_SHORTNAME=Cerium", "PRODUCT_SHORTNAME=Incorrect", 1))
        res_partial = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_partial.returncode == 0, f"apply-features partial branding repair failed: {res_partial.stderr}"
        with open(origin_branding) as f:
            assert "PRODUCT_SHORTNAME=Cerium" in f.read()

        # Verify idempotence
        res_idem = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"apply-features idempotence failed: {res_idem.stderr}"
        assert "Skipped" in res_idem.stdout
        assert "Skipped components/brave_shields/core/common/features.cc (already patched)" in res_idem.stdout
        assert "Skipped android/nala/BUILD.gn (already patched)" in res_idem.stdout
        assert "Skipped common/brave_content_client.cc (already patched)" in res_idem.stdout
        assert "Skipped chromium_src/components/embedder_support/user_agent_utils.cc (already patched)" in res_idem.stdout

        # Test Chromium src clean version display mutators
        src_tmpdir = os.path.join(tmpdir, "mock_src")
        mock_src = setup_mock_src(src_tmpdir)
        timestamp_gni = mock_src["timestamp_gni"]
        chrome_ver_gni = mock_src["chrome_ver_gni"]
        ver_values = mock_src["ver_values"]
        ver_consts = mock_src["ver_consts"]
        ver_strings = mock_src["ver_strings"]
        ts_split_file = mock_src["ts_split_file"]
        skills_build_gn = mock_src["skills_build_gn"]

        res_src = subprocess.run([sys.executable, script, tmpdir, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
        assert res_src.returncode == 0, f"apply-features with --src-dir failed: {res_src.stderr}\n{res_src.stdout}"

        with open(timestamp_gni) as f:
            c = f.read()
            assert "assert(" not in c
            assert 'not_needed([ "enable_android_secondary_abi" ])' in c

        with open(chrome_ver_gni) as f:
            c = f.read()
            assert "chrome_version_name = chrome_version_full" not in c
            assert "$chrome_version_minor.$chrome_version_build.$chrome_version_patch" in c

        with open(ver_values) as f:
            c = f.read()
            assert '@MAJOR@.@MINOR@.@BUILD@.@PATCH@' in c

        with open(ver_consts) as f:
            c = f.read()
            assert '@MAJOR@.@MINOR@.@BUILD@.@PATCH@' in c


        with open(ver_strings) as f:
            c = f.read()
            assert "@MAJOR@" not in c
            assert '<string name="product_version" translatable="false" tools:ignore="UnusedResources">@MINOR@.@BUILD@.@PATCH@</string>' in c

        with open(ts_split_file) as f:
            c = f.read()
            assert c.count('not_needed([ "public_inputs" ])') == 2, f"Expected 2 not_needed calls in ts_split_file, got:\n{c}"

        with open(skills_build_gn) as f:
            c = f.read()
            assert 'not_needed([ "public_inputs" ])' in c, f"Expected not_needed in skills_build_gn, got:\n{c}"

        with open(mock_src["chrome_android_build_gn"]) as f:
            c = f.read()
            assert "defined(android_app_secondary_abi)" in c, f"Expected secondary ABI check in chrome/android/BUILD.gn, got:\n{c}"
            assert "Only validate 32-bit and dual-ABI targets when secondary ABI is enabled." in c

        with open(mock_src["ver_ua_cc"]) as f:
            c = f.read()
            assert "std::string major = GetMajorVersionNumber();" in c
            assert "defined(BRAVE_CHROMIUM_VERSION)" in c
            assert 'base::StrCat({"Chrome/", major, ".0.0.0"})' in c

        with open(mock_src["chrome_browser_prefs_cc"]) as f:
            assert "registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, false);" in f.read()

        with open(mock_src["most_visited_pref_observer_cc"]) as f:
            assert "registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, false);" in f.read()

        res_src_idem = subprocess.run([sys.executable, script, tmpdir, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
        assert res_src_idem.returncode == 0, f"apply-features with --src-dir idempotence failed: {res_src_idem.stderr}"
        assert "Skipped build/timestamp.gni (already patched)" in res_src_idem.stdout
        assert "Skipped third_party/devtools-frontend/src/scripts/build/typescript/ts_library_split.gni (already patched)" in res_src_idem.stdout
        assert "Skipped third_party/devtools-frontend/src/front_end/models/ai_assistance/skills/BUILD.gn (already patched)" in res_src_idem.stdout
        assert "Skipped chrome/android/BUILD.gn (already patched)" in res_src_idem.stdout
        assert "Skipped components/version_info/version_info_with_user_agent.cc (already patched)" in res_src_idem.stdout

        # Verify that passing an unpopulated/empty src-dir does not cause MISSING SRC errors in --strict mode
        with tempfile.TemporaryDirectory() as empty_src_tmpdir:
            res_empty_src = subprocess.run(
                [sys.executable, script, tmpdir, "--strict", f"--src-dir={empty_src_tmpdir}", "--target-os=win"],
                capture_output=True,
                text=True
            )
            assert res_empty_src.returncode == 0, f"apply-features with unpopulated src-dir failed: {res_empty_src.stderr}"
            assert "ERROR: MISSING SRC" not in res_empty_src.stderr

        # Verify template("nala_icon_override") syntax mutator
        with open(nala_build_gn, "w") as f:
            f.write("""template("nala_icon_override") {
  _source = "$nala_base_path/drawable/${invoker.source}"
  _output = "$target_gen_dir/${invoker.res_root}/drawable/${invoker.dest}"
}

copy("nala_icons") {
  sources = []
  foreach(icon, nala_icons) {
    sources +=
        [ "//brave/node_modules/@brave/leo/tokens/android/drawable/$icon" ]
  }
  outputs = [ "$target_gen_dir/res/drawable/{{source_file_part}}" ]
}
""")
        res_template = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_template.returncode == 0, f"apply-features with template syntax failed: {res_template.stderr}\n{res_template.stdout}"
        with open(nala_build_gn) as f:
            c_templ = f.read()
            assert "ic_social_brave_outline_favicon_fullheight.xml" in c_templ
            assert "ic_social_brave_monochrome_favicon_fullheight_color.xml" in c_templ
            assert "//brave/app/theme/brave/android/shields_drawables/" in c_templ

        # Verify idempotence for template syntax
        res_template_idem = subprocess.run([sys.executable, script, tmpdir, "--strict"], capture_output=True, text=True)
        assert res_template_idem.returncode == 0, f"apply-features template idempotence failed: {res_template_idem.stderr}"
        assert "Skipped android/nala/BUILD.gn (already patched)" in res_template_idem.stdout

        print("PASS: test_apply_features")


def test_patch_suite():
    patch_dir = os.path.join(REPO_ROOT, "patches")
    patches = []
    if os.path.exists(patch_dir):
        for root, _, files in os.walk(patch_dir):
            for f in sorted(files):
                if f.endswith(".patch"):
                    patches.append(os.path.join(root, f))
    assert len(patches) >= 6, f"Expected at least 6 modular patches, found {len(patches)}"
    for p in patches:
        assert os.path.getsize(p) > 50, f"Patch {p} is suspiciously small"

    # Ensure monolithic 0003 patch is retired in favor of patches/android/debloat/
    old_0003 = os.path.join(REPO_ROOT, "patches/android/0003-enforce-debloat-policies.patch")
    assert not os.path.exists(old_0003), f"Monolithic patch should be split into patches/android/debloat/: {old_0003}"

    # Verify 0001 branding patch (release-only)
    patch_0001 = os.path.join(REPO_ROOT, "patches/android/0001-cerium-branding.patch")
    if not os.path.isfile(patch_0001):
        patch_0001 = os.path.join(REPO_ROOT, "patches/android/0001-braving-branding.patch")
    assert os.path.isfile(patch_0001), f"Missing patch file: {patch_0001}"
    with open(patch_0001, "r", encoding="utf-8") as f:
        c0001 = f.read()
    assert "app/theme/brave/BRANDING" in c0001
    assert "app/theme/brave/BRANDING." not in c0001, "Dev/Beta/Nightly BRANDING files should not be in 0001"
    assert "PRODUCT_FULLNAME=Cerium Browser" in c0001
    assert "PRODUCT_SHORTNAME=Cerium" in c0001
    assert 'Cerium - Debug' not in c0001, "Found Debug suffix in 0001-cerium-branding.patch"
    assert '<string name="app_name" translatable="false">Cerium</string>' in c0001
    assert "org.cerium.browser" in c0001
    assert "R.mipmap.layered_app_icon" in c0001
    assert "R.mipmap.layered_app_icon_background" in c0001
    assert "R.drawable.btn_brave" in c0001
    assert "R.drawable.btn_brave_off" in c0001
    assert "R.string.prefs_support_section" in c0001
    assert "R.string.prefs_rate_brave" in c0001
    assert "R.string.in_app_update_text" in c0001
    assert "R.drawable.ic_star_circle" in c0001

    # Verify Android lint suppression regexes match both plain (SDK 37+) and backticked warning formats
    regexes = re.findall(r'<ignore regexp="([^"]+)"', c0001)
    for res_name in [
        "R.mipmap.layered_app_icon",
        "R.mipmap.layered_app_icon_background",
        "R.drawable.btn_brave",
        "R.drawable.btn_brave_off",
        "R.string.prefs_support_section",
        "R.string.prefs_rate_brave",
        "R.string.in_app_update_text",
        "R.drawable.ic_star_circle",
    ]:
        matching = [p for p in regexes if res_name in p]
        assert matching, f"No lint suppression pattern found for {res_name}"
        pattern = matching[0]
        # Match plain Android SDK 37+ warning format (as produced in CI)
        msg_plain = f"The resource {res_name} appears to be unused"
        assert re.search(pattern, msg_plain), f"Pattern '{pattern}' failed to match plain warning: '{msg_plain}'"
        # Match legacy backticked Android SDK warning format
        msg_backticked = f"The resource `{res_name}` appears to be unused"
        assert re.search(pattern, msg_backticked), f"Pattern '{pattern}' failed to match backticked warning: '{msg_backticked}'"

    # Verify 0002 custom updater endpoint patch (release-only, common)
    patch_0002 = os.path.join(REPO_ROOT, "patches/common/0002-custom-updater-endpoint.patch")
    assert os.path.isfile(patch_0002), f"Missing patch file: {patch_0002}"
    with open(patch_0002, "r", encoding="utf-8") as f:
        c0002 = f.read()
    assert 'https://ceriumbrowser.gitlab.io/cerium-updater/components' in c0002
    assert '+  updater_prod_endpoint = "https://ceriumbrowser.gitlab.io/cerium-updater/components"' in c0002
    assert '+  updater_dev_endpoint' not in c0002
    assert 'kCeriumPublisherKeyHash' in c0002
    assert 'IsStaticUpdaterGetUrl' in c0002
    assert ',disable-pings' in c0002
    assert 'adjusted.status = "noupdate"' in c0002
    assert 'ad_block_service();' not in c0002, "Eager startup ad_block_service causes premature profile crash on Android"

    # Verify modular debloat patches in patches/common/debloat and patches/android/debloat/
    common_debloat_dir = os.path.join(REPO_ROOT, "patches/common/debloat")
    android_debloat_dir = os.path.join(REPO_ROOT, "patches/android/debloat")
    assert os.path.isdir(common_debloat_dir), f"Missing common debloat patch directory: {common_debloat_dir}"
    assert os.path.isdir(android_debloat_dir), f"Missing android debloat patch directory: {android_debloat_dir}"

    p_flag = os.path.join(common_debloat_dir, "0001-hide-brave-origin-flag.patch")
    with open(p_flag, "r", encoding="utf-8") as f:
        c_flag = f.read()
    assert "BASE_FEATURE(kBraveOrigin, base::FEATURE_DISABLED_BY_DEFAULT);" in c_flag

    p_backend = os.path.join(common_debloat_dir, "0002-unlock-brave-origin-backend.patch")
    with open(p_backend, "r", encoding="utf-8") as f:
        c_backend = f.read()
    assert "brave_origin_policy_manager.cc" in c_backend
    assert "brave_origin_service.cc" in c_backend
    assert "brave_origin_utils.cc" in c_backend
    assert "return manager->IsInitialized();" in c_backend

    p_android_origin = os.path.join(android_debloat_dir, "0003-unlock-brave-origin-android-prefs.patch")
    with open(p_android_origin, "r", encoding="utf-8") as f:
        c_android_origin = f.read()
    assert "BraveOriginSubscriptionPrefs.java" in c_android_origin
    assert "getIsCredentialSummaryActiveCached" in c_android_origin

    p_policies = os.path.join(common_debloat_dir, "0004-enforce-enterprise-policies.patch")
    with open(p_policies, "r", encoding="utf-8") as f:
        c_policies = f.read()
    assert "RefreshPolicies(policy::PolicyFetchReason::kBrowserStart);" in c_policies
    assert 'enforce("MetricsReportingEnabled", false);' in c_policies
    assert 'enforce("BraveP3AEnabled", false);' in c_policies
    assert 'enforce("BraveStatsPingEnabled", false);' in c_policies
    assert 'enforce("BraveWalletDisabled", true);' in c_policies
    assert 'enforce("BraveVPNDisabled", true);' in c_policies
    assert 'enforce("BraveAIChatEnabled", false);' in c_policies
    assert 'enforce("BraveNewsDisabled", true);' in c_policies
    assert 'enforce("BraveRewardsDisabled", true);' in c_policies
    assert 'enforce("BraveWaybackMachineEnabled", false);' in c_policies
    assert 'enforce("BraveLocalAIEnabled", false);' in c_policies
    assert 'enforce("IPFSEnabled", false);' not in c_policies
    assert 'enforce("TorDisabled", true);' not in c_policies
    assert 'enforce("BravePlaylistEnabled", false);' not in c_policies
    assert 'enforce("EmailAliasesEnabled", false);' not in c_policies
    assert 'enforce("PsstEnabled", false);' not in c_policies

    p_rate_brave = os.path.join(android_debloat_dir, "0005-remove-rate-brave.patch")
    assert os.path.isfile(p_rate_brave), f"Missing debloat patch: {p_rate_brave}"
    with open(p_rate_brave, "r", encoding="utf-8") as f:
        c_rate_brave = f.read()
    assert "rate_brave" in c_rate_brave
    assert "support_section" in c_rate_brave
    assert "shouldShowRateDialog" in c_rate_brave
    assert "sendRateFeedback" in c_rate_brave

    p_play_update = os.path.join(android_debloat_dir, "0006-disable-play-in-app-update.patch")
    assert os.path.isfile(p_play_update), f"Missing debloat patch: {p_play_update}"
    with open(p_play_update, "r", encoding="utf-8") as f:
        c_play_update = f.read()
    assert "completeUpdateSnackbar" in c_play_update
    assert "checkAppUpdate" in c_play_update
    assert "showOriginSettingsForRestart" in c_play_update
    assert "launchReviewFlow" in c_rate_brave

    p_adblock = os.path.join(android_debloat_dir, "0005-default-adblock-subscriptions.patch")
    assert not os.path.exists(p_adblock), (
        "0005-default-adblock-subscriptions.patch must remain retired so CRX3 catalog components manage filter lists with permission_mask=3"
    )

    p_paywall = os.path.join(REPO_ROOT, "patches/common/0001-brave-origin-paywall-bypass.patch")
    assert os.path.isfile(p_paywall), f"Missing paywall bypass patch: {p_paywall}"
    with open(p_paywall, "r", encoding="utf-8") as f:
        c_paywall = f.read()
    assert "browser/ui/views/brave_origin/brave_origin_startup_view.cc" in c_paywall
    assert "return false;" in c_paywall

    # Dynamic brave-core detection: check BRAVE_CORE_DIR, build-workspace, or /run/media/pc/D/brave-core
    brave_core = os.environ.get("BRAVE_CORE_DIR", "")
    if not (brave_core and os.path.isdir(os.path.join(brave_core, ".git"))):
        if os.path.isdir("/run/media/pc/D/brave-core/.git"):
            brave_core = "/run/media/pc/D/brave-core"
        else:
            workspace_brave = os.path.join(REPO_ROOT, "build-workspace/src/brave")
            if os.path.isdir(os.path.join(workspace_brave, ".git")):
                brave_core = workspace_brave

    if brave_core and os.path.isdir(os.path.join(brave_core, ".git")):
        for p in patches:
            cmd = ["git", "-C", brave_core, "apply", "--check", p]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                cmd_rev = ["git", "-C", brave_core, "apply", "--check", "--reverse", p]
                res_rev = subprocess.run(cmd_rev, capture_output=True, text=True)
                if res_rev.returncode != 0:
                    cmd_c1 = ["git", "-C", brave_core, "apply", "-C1", "--check", p]
                    res_c1 = subprocess.run(cmd_c1, capture_output=True, text=True)
                    if res_c1.returncode != 0:
                        cmd_c1_rev = ["git", "-C", brave_core, "apply", "-C1", "--check", "--reverse", p]
                        res_c1_rev = subprocess.run(cmd_c1_rev, capture_output=True, text=True)
                        assert res_c1_rev.returncode == 0, f"Patch {os.path.basename(p)} failed to apply: {res.stderr}"

    print("PASS: test_patch_suite")


def test_apply_branding():
    import importlib.util
    script_path = os.path.join(REPO_ROOT, "scripts/core/apply-branding.py")
    spec = importlib.util.spec_from_file_location("apply_branding", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with tempfile.TemporaryDirectory() as tmpdir:
        grd_dir = os.path.join(tmpdir, "browser/ui/android/strings")
        xtb_dir = os.path.join(grd_dir, "translations")
        pref_dir = os.path.join(tmpdir, "android/java/res/xml")
        os.makedirs(xtb_dir, exist_ok=True)
        os.makedirs(pref_dir, exist_ok=True)

        grd_path = os.path.join(grd_dir, "android_brave_strings.grd")
        part_path = os.path.join(grd_dir, "sub_strings.grdp")
        xtb_path = os.path.join(xtb_dir, "android_brave_strings_es.xtb")
        pref_path = os.path.join(pref_dir, "developer_preferences.xml")

        import xml.etree.ElementTree as ET
        old_fp_1 = mod.get_fingerprint_for_xtb(ET.fromstring("<message>Welcome to Brave</message>"))
        new_fp_1 = mod.get_fingerprint_for_xtb(ET.fromstring("<message>Welcome to Cerium</message>"))

        old_fp_2 = mod.get_fingerprint_for_xtb(
            ET.fromstring('<message>Brave Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Brave 1.0</ex></ph></message>')
        )
        new_fp_2 = mod.get_fingerprint_for_xtb(
            ET.fromstring('<message>Cerium Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Cerium 1.0</ex></ph></message>')
        )

        with open(part_path, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<grit-part>
  <message name="IDS_SHIELDS_PRIVACY" desc="Shields label">
    Brave Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Brave 1.0</ex></ph>
  </message>
</grit-part>
""")

        with open(grd_path, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<grit latest_public_release="0" current_release="1">
  <outputs>
    <output filename="values/android_brave_strings.xml" lang="en" type="android" />
  </outputs>
  <translations>
    <file path="translations/android_brave_strings_es.xtb" lang="es" />
  </translations>
  <release seq="1">
    <messages fallback_to_english="true">
      <part file="sub_strings.grdp" />
      <message name="IDS_WELCOME_BRAVE" desc="Welcome">Welcome to Brave</message>
      <message name="IDS_CHROME_HISTORY" desc="History menu item">Brave history</message>
      <message name="IDS_JAVASCRIPT_OPT" desc="Protects against malicious actors">Brave runs faster</message>
      <message name="IDS_BRAVE_SEARCH_DESC" desc="Search">Try Brave Search at https://search.brave.com or brave://settings in Brave</message>
      <message name="IDS_TRY_BRAVE_SEARCH_WIDGET" desc="Title of Brave search widget promo">Try the Brave Search widget</message>
      <message name="IDS_LEGAL_INFORMATION_SUMMARY" desc="Legal">Copyright © %1$d The Brave Authors. All rights reserved.</message>
      <message name="IDS_BRAVE_WALLET_TITLE" desc="Wallet bloat">Brave Wallet</message>
      <message name="IDS_AI_CHAT_INTRO" desc="Leo bloat">Ask Brave Leo AI</message>
      <message name="IDS_TOR_STATUS" desc="Tor bloat">Brave Tor</message>
    </messages>
  </release>
</grit>
""")

        with open(xtb_path, "w", encoding="utf-8") as f:
            f.write(f"""<?xml version="1.0" ?>
<!DOCTYPE translationbundle>
<translationbundle lang="es">
<translation id="{old_fp_1}">Bienvenido a Brave</translation>
<translation id="{old_fp_2}">Escudos de Brave en <ph name="BRAVE_VERSION"/></translation>
</translationbundle>
""")

        with open(pref_path, "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="utf-8"?>
<!-- Copyright (c) 2020 The Brave Authors. All rights reserved. -->
<PreferenceScreen xmlns:android="http://schemas.android.com/apk/res/android">
    <Preference
        android:key="qa_hint"
        android:title="Tap Brave version in About Brave"
        android:summary="Visit https://brave.com for Brave Search" />
</PreferenceScreen>
""")

        env = dict(os.environ)
        env.pop("CI", None)
        res = subprocess.run([sys.executable, script_path, tmpdir], env=env, capture_output=True, text=True)
        assert res.returncode == 0, f"apply-branding failed: {res.stderr}\n{res.stdout}"

        with open(grd_path, "r", encoding="utf-8") as f:
            grd_out = f.read()
        assert ">Welcome to Cerium</message>" in grd_out
        assert ">Cerium history</message>" in grd_out
        assert ">Cerium runs faster</message>" in grd_out
        assert ">Try Brave Search at https://search.brave.com or brave://settings in Cerium</message>" in grd_out
        assert ">Try the Cerium Search widget</message>" in grd_out
        assert ">Copyright © %1$d The Cerium Browser Team. All rights reserved.</message>" in grd_out
        assert ">Brave Wallet</message>" in grd_out, "Bloat wallet string should not be branded"
        assert ">Ask Brave Leo AI</message>" in grd_out, "Bloat AI chat string should not be branded"
        assert ">Brave Tor</message>" in grd_out, "Bloat Tor string should not be branded"

        with open(part_path, "r", encoding="utf-8") as f:
            part_out = f.read()
        assert 'Cerium Shields &amp; privacy in <ph name="BRAVE_VERSION">%1$s<ex>Brave 1.0</ex></ph>' in part_out

        with open(xtb_path, "r", encoding="utf-8") as f:
            xtb_out = f.read()
        assert f'id="{new_fp_1}">Bienvenido a Cerium</translation>' in xtb_out
        assert f'id="{new_fp_2}">Escudos de Cerium en <ph name="BRAVE_VERSION"/></translation>' in xtb_out

        with open(pref_path, "r", encoding="utf-8") as f:
            pref_out = f.read()
        assert "The Brave Authors" in pref_out, "Copyright comment should not be modified"
        assert 'android:title="Tap Cerium version in About Cerium"' in pref_out
        assert 'android:summary="Visit https://brave.com for Brave Search"' in pref_out

        # Idempotence check
        res_idem = subprocess.run([sys.executable, script_path, tmpdir], env=env, capture_output=True, text=True)
        assert res_idem.returncode == 0, f"apply-branding idempotence failed: {res_idem.stderr}"
        assert "0 messages updated across 0 GRD/GRDP files and 0 XTB translation files" in res_idem.stdout

        print("PASS: test_apply_branding")


def test_python311_syntax_compatibility():
    """Ensure all Python scripts and embedded heredocs are compatible with Python 3.11 (Debian Bookworm)."""
    import ast
    import glob
    import re

    def verify_source(code: str, label: str):
        # On Python <= 3.11, ast.parse natively enforces Python 3.11 syntax (including pre-PEP-701 f-strings).
        tree = ast.parse(code, filename=label)
        if sys.version_info < (3, 12):
            return
        # On Python 3.12+, simulate Python 3.11 pre-PEP-701 f-string restrictions using FormattedValue spans.
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                seg = ast.get_source_segment(code, node)
                if not seg:
                    continue
                m = re.match(r"^[fFrR]+(\"\"\"|'''|\"|')", seg)
                outer_q = m.group(1) if m else '"'
                for val in node.values:
                    if isinstance(val, ast.FormattedValue):
                        vseg = ast.get_source_segment(code, val) or ""
                        if not (vseg.startswith("{") and vseg.endswith("}")):
                            continue
                        assert "\\" not in vseg, (
                            f"Python 3.11 SyntaxError: backslash in f-string expression at {label}:{node.lineno}: {vseg}"
                        )
                        if outer_q in ('"', "'"):
                            assert outer_q not in vseg, (
                                f"Python 3.11 SyntaxError: nested {outer_q} in f-string expression at {label}:{node.lineno}: {vseg}"
                            )
                        assert "#" not in vseg, (
                            f"Python 3.11 SyntaxError: comment in f-string expression at {label}:{node.lineno}: {vseg}"
                        )

    py_files = sorted(glob.glob(os.path.join(REPO_ROOT, "scripts/**/*.py"), recursive=True))
    for p in py_files:
        with open(p, "r", encoding="utf-8") as f:
            verify_source(f.read(), os.path.relpath(p, REPO_ROOT))

    sh_files = sorted(glob.glob(os.path.join(REPO_ROOT, "scripts/**/*.sh"), recursive=True))
    for p in sh_files:
        with open(p, "r", encoding="utf-8") as f:
            sh = f.read()
        for i, m in enumerate(re.finditer(r"python3 - [^\n]*<<'?PYEOF'?\n(.*?)\nPYEOF", sh, re.DOTALL)):
            verify_source(m.group(1), f"{os.path.relpath(p, REPO_ROOT)}[PYEOF#{i}]")

    print("PASS: test_python311_syntax_compatibility")


def test_timestamp_gni_gn_evaluation():
    gn_bin = shutil.which("gn")
    if not gn_bin:
        cand = os.path.join(REPO_ROOT, "build-workspace/src/buildtools/linux64/gn")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            gn_bin = cand
    if not gn_bin:
        print("SKIP: test_timestamp_gni_gn_evaluation (gn binary not available)")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, ".gn"), "w") as f:
            f.write("buildconfig = \"//BUILDCONFIG.gn\"\n")
        with open(os.path.join(tmpdir, "BUILDCONFIG.gn"), "w") as f:
            f.write("""
is_android = true
enable_android_secondary_abi = false
is_official_build = true
lastchange_file = "//LASTCHANGE"
set_default_toolchain("//:default_tc")
""")
        with open(os.path.join(tmpdir, "LASTCHANGE"), "w") as f:
            f.write("12345\n")

        os.makedirs(os.path.join(tmpdir, "build/config/android"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "build/util"), exist_ok=True)
        with open(os.path.join(tmpdir, "build/compute_build_timestamp.py"), "w") as f:
            f.write("import sys; print(12345)\n")
        with open(os.path.join(tmpdir, "build/util/lastchange.gni"), "w") as f:
            f.write("lastchange_file = \"//LASTCHANGE\"\n")
        with open(os.path.join(tmpdir, "build/config/android/abi.gni"), "w") as f:
            f.write("declare_args() { enable_android_secondary_abi = false }\n")

        setup_mock_src(tmpdir)
        timestamp_gni = os.path.join(tmpdir, "build/timestamp.gni")

        with open(os.path.join(tmpdir, "BUILD.gn"), "w") as f:
            f.write("""
if (current_toolchain == default_toolchain) {
  toolchain("default_tc") {
    tool("stamp") { command = "touch {{output}}" }
  }
  toolchain("android_clang_arm64_webview") {
    tool("stamp") { command = "touch {{output}}" }
  }
}

group("top") {
  deps = [ ":webview_target(//:android_clang_arm64_webview)" ]
}

group("webview_target") {
  import("//build/timestamp.gni")
}
""")

        out_unpatched = os.path.join(tmpdir, "out_unpatched")
        res_fail = subprocess.run([gn_bin, "gen", out_unpatched], cwd=tmpdir, capture_output=True, text=True)
        assert res_fail.returncode != 0, "Expected gn gen to fail before patch"
        assert "Trying to run compute_build_timestamp.py in toolchain:" in (res_fail.stdout + res_fail.stderr)

        # Apply mutator via apply-features.py
        script = os.path.join(REPO_ROOT, "scripts/core/apply-features.py")
        mock_brave = os.path.join(tmpdir, "brave")
        setup_mock_brave(mock_brave)
        res_mut = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={tmpdir}"], capture_output=True, text=True)
        assert res_mut.returncode == 0, f"apply-features failed: {res_mut.stderr}\n{res_mut.stdout}"

        # Test gn gen succeeds with patched timestamp.gni in webview toolchain
        out_patched = os.path.join(tmpdir, "out_patched")
        res_pass = subprocess.run([gn_bin, "gen", out_patched], cwd=tmpdir, capture_output=True, text=True)
        assert res_pass.returncode == 0, f"Expected gn gen to succeed after patch: {res_pass.stderr}\n{res_pass.stdout}"

    print("PASS: test_timestamp_gni_gn_evaluation")


def test_timestamp_gni_resilience_and_formatting():
    """Verify that apply-features.py mutates timestamp.gni across different upstream
    formatting styles (single-line assertion, extra spaces, custom error string)
    and remains strictly idempotent.
    """
    script = os.path.join(REPO_ROOT, "scripts/core/apply-features.py")
    variants = [
        # 1. Standard multi-line upstream
        """if (is_android) {
  import("//build/config/android/abi.gni")
  if (!enable_android_secondary_abi) {
    assert(
        current_toolchain == default_toolchain,
        "Trying to run compute_build_timestamp.py in toolchain: $current_toolchain")
  }
}
""",
        # 2. Single-line assertion
        """if (is_android) {
  import("//build/config/android/abi.gni")
  if (!enable_android_secondary_abi) { assert(current_toolchain == default_toolchain, "error") }
}
""",
        # 3. Spaces inside parentheses & alternate error string
        """if (is_android) {
  import("//build/config/android/abi.gni")
  if ( !enable_android_secondary_abi ) {
    assert( current_toolchain == default_toolchain )
  }
}
""",
        # 4. Custom indentation
        """if (is_android) {
    import("//build/config/android/abi.gni")
    if (!enable_android_secondary_abi) {
        assert(current_toolchain == default_toolchain)
    }
}
""",
    ]

    for idx, var in enumerate(variants):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_tmpdir = os.path.join(tmpdir, "mock_src")
            setup_mock_src(src_tmpdir)
            ts_path = os.path.join(src_tmpdir, "build/timestamp.gni")
            with open(ts_path, "w") as f:
                f.write(var)

            mock_brave = os.path.join(tmpdir, "mock_brave")
            setup_mock_brave(mock_brave)

            # 1. Run apply-features.py in strict mode
            res = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
            assert res.returncode == 0, f"Variant {idx} failed: {res.stderr}\n{res.stdout}"
            assert "Patched build/timestamp.gni" in res.stdout, f"Variant {idx} did not patch timestamp.gni: {res.stdout}"

            # 2. Verify assertion removed and not_needed present
            with open(ts_path) as f:
                c = f.read()
                assert "assert(" not in c, f"Variant {idx} still contains assert: {c}"
                assert 'not_needed([ "enable_android_secondary_abi" ])' in c, f"Variant {idx} missing not_needed: {c}"

            # 3. Test idempotence: re-running should report skipped and not change anything
            res_idem = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
            assert res_idem.returncode == 0, f"Variant {idx} idempotence failed: {res_idem.stderr}"
            assert "Skipped build/timestamp.gni (already patched)" in res_idem.stdout

    # Test error handling when search pattern cannot be matched in strict mode
    with tempfile.TemporaryDirectory() as tmpdir:
        src_tmpdir = os.path.join(tmpdir, "mock_src")
        setup_mock_src(src_tmpdir)
        ts_path = os.path.join(src_tmpdir, "build/timestamp.gni")
        # Write corrupted/unrecognized assertion block
        with open(ts_path, "w") as f:
            f.write("if (is_android) { unrecognised_structure = true }\n")

        mock_brave = os.path.join(tmpdir, "mock_brave")
        setup_mock_brave(mock_brave)

        res_err = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
        assert res_err.returncode != 0, "Expected apply-features to fail in strict mode when pattern is missing"
        assert "Search string not found in build/timestamp.gni" in (res_err.stdout + res_err.stderr)

    print("PASS: test_timestamp_gni_resilience_and_formatting")


def test_validate_expectations_gn_evaluation():
    """Verify that gn gen fails before validate_expectations patch with 24 unresolved dependencies,
    and succeeds after patch in single-arch (arm64, enable_android_secondary_abi=false),
    and succeeds in dual-ABI (with android_app_secondary_abi defined)."""
    gn_bin = shutil.which("gn")
    if not gn_bin:
        cand = os.path.join(REPO_ROOT, "build-workspace/src/buildtools/linux64/gn")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            gn_bin = cand
    if not gn_bin:
        print("SKIP: test_validate_expectations_gn_evaluation (gn binary not available)")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, ".gn"), "w") as f:
            f.write("buildconfig = \"//BUILDCONFIG.gn\"\n")
        with open(os.path.join(tmpdir, "BUILDCONFIG.gn"), "w") as f:
            f.write("""
set_default_toolchain("//:default_tc")
is_android = true
target_cpu = "arm64"
android_64bit_target_cpu = true
enable_libs_and_assets_verification = true
enable_manifest_verification = true
enable_android_secondary_abi = false
lastchange_file = "//LASTCHANGE"
""")
        with open(os.path.join(tmpdir, "LASTCHANGE"), "w") as f:
            f.write("12345\n")

        with open(os.path.join(tmpdir, "BUILD.gn"), "w") as f:
            f.write("""
toolchain("default_tc") {
  tool("stamp") { command = "touch {{output}}" }
}
group("top") {
  deps = [ "//chrome/android:validate_expectations" ]
}
""")

        setup_mock_src(tmpdir)

        # In android_webview: only 64-bit targets exist when enable_android_secondary_abi is false
        os.makedirs(os.path.join(tmpdir, "android_webview"), exist_ok=True)
        with open(os.path.join(tmpdir, "android_webview/BUILD.gn"), "w") as f:
            f.write("""
group("trichrome_webview_64_bundle_validate_libs_and_assets") {}
group("system_webview_64_base_bundle_module_validate_android_manifest") {}
group("trichrome_webview_64_base_bundle_module_validate_android_manifest") {}
""")

        # Add mock 64-bit targets in chrome/android/BUILD.gn
        ca_path = os.path.join(tmpdir, "chrome/android/BUILD.gn")
        with open(ca_path, "r") as f:
            ca_content = f.read()
        with open(ca_path, "w") as f:
            f.write("""
group("trichrome_chrome_64_bundle_validate_libs_and_assets") {}
group("trichrome_library_64_apk_validate_libs_and_assets") {}
group("trichrome_chrome_64_bundle__base_bundle_module_validate_android_manifest") {}
group("trichrome_library_64_apk_validate_android_manifest") {}
""" + ca_content)

        out_unpatched = os.path.join(tmpdir, "out_unpatched")
        res_fail = subprocess.run([gn_bin, "gen", out_unpatched], cwd=tmpdir, capture_output=True, text=True)
        assert res_fail.returncode != 0, "Expected gn gen to fail before patch"
        assert "ERROR Unresolved dependencies." in (res_fail.stdout + res_fail.stderr)
        assert res_fail.stdout.count("needs //") == 24, f"Expected 24 unresolved dependencies, got:\n{res_fail.stdout}"

        # Apply mutator via apply-features.py
        script = os.path.join(REPO_ROOT, "scripts/core/apply-features.py")
        mock_brave = os.path.join(tmpdir, "brave")
        setup_mock_brave(mock_brave)
        res_mut = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={tmpdir}"], capture_output=True, text=True)
        assert res_mut.returncode == 0, f"apply-features failed: {res_mut.stderr}\n{res_mut.stdout}"

        # Test gn gen succeeds with patched validate_expectations in single-arch
        out_patched = os.path.join(tmpdir, "out_patched")
        res_pass = subprocess.run([gn_bin, "gen", out_patched], cwd=tmpdir, capture_output=True, text=True)
        assert res_pass.returncode == 0, f"Expected gn gen to succeed after patch: {res_pass.stderr}\n{res_pass.stdout}"

        # Test dual-ABI mode succeeds when android_app_secondary_abi is defined
        with open(os.path.join(tmpdir, "BUILDCONFIG.gn"), "w") as f:
            f.write("""
set_default_toolchain("//:default_tc")
is_android = true
target_cpu = "arm64"
android_64bit_target_cpu = true
enable_libs_and_assets_verification = true
enable_manifest_verification = true
enable_android_secondary_abi = true
android_app_secondary_abi = "armeabi-v7a"
lastchange_file = "//LASTCHANGE"
""")
        # Add 32-bit and dual-ABI targets in android_webview and chrome/android
        with open(os.path.join(tmpdir, "android_webview/BUILD.gn"), "a") as f:
            f.write("""
group("trichrome_webview_32_64_bundle_validate_libs_and_assets") {}
group("trichrome_webview_32_bundle_validate_libs_and_assets") {}
group("trichrome_webview_64_32_bundle_validate_libs_and_assets") {}
group("system_webview_32_64_base_bundle_module_validate_android_manifest") {}
group("system_webview_32_base_bundle_module_validate_android_manifest") {}
group("system_webview_64_32_base_bundle_module_validate_android_manifest") {}
group("trichrome_webview_32_64_base_bundle_module_validate_android_manifest") {}
group("trichrome_webview_32_base_bundle_module_validate_android_manifest") {}
group("trichrome_webview_64_32_base_bundle_module_validate_android_manifest") {}
group("trichrome_webview_64_32_bundle_validate_proguard_config") {}
""")
        with open(ca_path, "a") as f:
            f.write("""
group("trichrome_chrome_32_64_bundle_validate_libs_and_assets") {}
group("trichrome_chrome_32_bundle_validate_libs_and_assets") {}
group("trichrome_chrome_64_32_bundle_validate_libs_and_assets") {}
group("trichrome_library_32_64_apk_validate_libs_and_assets") {}
group("trichrome_library_32_apk_validate_libs_and_assets") {}
group("trichrome_library_64_32_apk_validate_libs_and_assets") {}
group("trichrome_chrome_32_64_bundle__base_bundle_module_validate_android_manifest") {}
group("trichrome_chrome_32_bundle__base_bundle_module_validate_android_manifest") {}
group("trichrome_chrome_64_32_bundle__base_bundle_module_validate_android_manifest") {}
group("trichrome_chrome_64_32_bundle_validate_manifests") {}
group("trichrome_chrome_64_32_bundle_validate_proguard_config") {}
group("trichrome_library_32_64_apk_validate_android_manifest") {}
group("trichrome_library_32_apk_validate_android_manifest") {}
group("trichrome_library_64_32_apk_validate_android_manifest") {}
""")
        out_dual = os.path.join(tmpdir, "out_dual")
        res_dual = subprocess.run([gn_bin, "gen", out_dual], cwd=tmpdir, capture_output=True, text=True)
        assert res_dual.returncode == 0, f"Expected gn gen to succeed in dual-ABI: {res_dual.stderr}\n{res_dual.stdout}"

    print("PASS: test_validate_expectations_gn_evaluation")


def test_validate_expectations_resilience_and_formatting():
    """Verify that apply-features.py mutates validate_expectations across different formatting variants,
    is strictly idempotent, and fails cleanly in strict mode when pattern cannot be matched."""
    script = os.path.join(REPO_ROOT, "scripts/core/apply-features.py")

    variants = [
        # Variant 1: Extra whitespace and newlines
        """
  group ( "validate_expectations" ) {
    deps = [  ]
    if ( enable_libs_and_assets_verification ) {
      deps += [
        ":trichrome_chrome_32_64_bundle_validate_libs_and_assets",
        ":trichrome_library_64_apk_validate_libs_and_assets",
      ]
    }
    if ( enable_manifest_verification ) {
      deps += [
        ":trichrome_chrome_32_64_bundle__base_bundle_module_validate_android_manifest",
        ":trichrome_library_64_apk_validate_android_manifest",
      ]
    }
  }
""",
        # Variant 2: Standard compact formatting
        """  group("validate_expectations") {
    deps = []
    if (enable_libs_and_assets_verification) {
      deps += [
        ":trichrome_chrome_32_64_bundle_validate_libs_and_assets",
        ":trichrome_library_64_apk_validate_libs_and_assets",
      ]
    }
    if (enable_manifest_verification) {
      deps += [
        ":trichrome_chrome_32_64_bundle__base_bundle_module_validate_android_manifest",
        ":trichrome_library_64_apk_validate_android_manifest",
      ]
    }
  }""",
        # Variant 3: Reversed condition order (manifest before libs)
        """  group("validate_expectations") {
    deps = []
    if (enable_manifest_verification) {
      deps += [
        ":trichrome_chrome_32_bundle__base_bundle_module_validate_android_manifest",
        ":trichrome_chrome_64_bundle__base_bundle_module_validate_android_manifest",
      ]
    }
    if (enable_libs_and_assets_verification) {
      deps += [
        ":trichrome_chrome_32_bundle_validate_libs_and_assets",
        ":trichrome_chrome_64_bundle_validate_libs_and_assets",
      ]
    }
  }""",
        # Variant 4: Extra condition and custom targets
        """  group("validate_expectations") {
    deps = []
    if (enable_libs_and_assets_verification) {
      deps += [
        ":trichrome_chrome_32_bundle_validate_libs_and_assets",
        ":trichrome_chrome_64_bundle_validate_libs_and_assets",
      ]
    }
    if (enable_binary_size) {
      deps += [ ":custom_binary_size_check" ]
    }
  }""",
        # Variant 5: Comments with brackets inside deps lists
        """  group("validate_expectations") {
    deps = []
    if (enable_libs_and_assets_verification) {
      deps += [
        # Target [arm64] description
        ":trichrome_chrome_32_bundle_validate_libs_and_assets",
        ":trichrome_chrome_64_bundle_validate_libs_and_assets",
      ]
    }
  }""",
    ]

    for idx, var in enumerate(variants, 1):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_tmpdir = os.path.join(tmpdir, "mock_src")
            setup_mock_src(src_tmpdir)
            ca_path = os.path.join(src_tmpdir, "chrome/android/BUILD.gn")
            with open(ca_path, "w") as f:
                f.write(var)

            mock_brave = os.path.join(tmpdir, "mock_brave")
            setup_mock_brave(mock_brave)

            # 1. Run apply-features.py in strict mode
            res = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
            assert res.returncode == 0, f"Variant {idx} failed: {res.stderr}\n{res.stdout}"
            assert "Patched chrome/android/BUILD.gn" in res.stdout, f"Variant {idx} did not patch chrome/android/BUILD.gn: {res.stdout}"

            # 2. Verify defined(android_app_secondary_abi) is present
            with open(ca_path) as f:
                c = f.read()
                assert "defined(android_app_secondary_abi)" in c, f"Variant {idx} missing secondary ABI guard: {c}"
                if idx == 4:
                    assert ":custom_binary_size_check" in c, f"Variant 4 clobbered extra target: {c}"
                elif idx == 5:
                    assert "Target [arm64] description" in c, f"Variant 5 clobbered bracketed comment: {c}"

            # 3. Test idempotence: re-running should report skipped and not change anything
            res_idem = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
            assert res_idem.returncode == 0, f"Variant {idx} idempotence failed: {res_idem.stderr}"
            assert "Skipped chrome/android/BUILD.gn (already patched)" in res_idem.stdout

    # Test error handling when search pattern cannot be matched in strict mode
    with tempfile.TemporaryDirectory() as tmpdir:
        src_tmpdir = os.path.join(tmpdir, "mock_src")
        setup_mock_src(src_tmpdir)
        ca_path = os.path.join(src_tmpdir, "chrome/android/BUILD.gn")
        with open(ca_path, "w") as f:
            f.write("# group validate_expectations removed upstream\n")

        mock_brave = os.path.join(tmpdir, "mock_brave")
        setup_mock_brave(mock_brave)

        res_err = subprocess.run([sys.executable, script, mock_brave, "--strict", f"--src-dir={src_tmpdir}"], capture_output=True, text=True)
        assert res_err.returncode != 0, "Expected apply-features to fail in strict mode when pattern is missing"
        assert "Search string not found in chrome/android/BUILD.gn" in (res_err.stdout + res_err.stderr)

    print("PASS: test_validate_expectations_resilience_and_formatting")


def test_webui_and_feature_mutators_resilience_and_formatting():
    """Verify resilience of WebUI, resource GNI, webpack, and rust_to_wasm mutators
    across various upstream formatting variations, dependency orderings, and verify idempotence."""
    script = os.path.join(REPO_ROOT, "scripts/core/apply-features.py")

    # 1. Test WebUI BUILD.gn resilience
    webui_variants = [
        # Variant A: No existing include_polymer block, different dep order
        """group("grdp") {
  public_deps = [
    "//brave/components/brave_account/resources/opaque_ke",
    ":fonts_grdp",
    ":external_js_bundles",
    ":icons_grdp",
    ":static_grdp",
  ]
}
""",
        # Variant B: Existing include_polymer with existing deps
        """group("grdp") {
  public_deps = [
    ":external_js_bundles",
    ":fonts_grdp",
    "//brave/components/brave_account/resources/opaque_ke",
  ]
  if (include_polymer) {
    public_deps += [
      ":build_grdp",
      ":extra_polymer_component",
    ]
  }
}
""",
        # Variant C: Comments with brackets inside deps
        """group("grdp") {
  public_deps = [
    # Comment with [brackets]
    ":external_js_bundles",
    ":fonts_grdp",
    ":icons_grdp",
    "//brave/components/brave_account/resources/opaque_ke",
  ]
  if (include_polymer) {
    public_deps += [ ":build_grdp" ]
  }
}
""",
        # Variant D: if (include_polymer) appears earlier before group("grdp")
        """if (include_polymer) {
  # Earlier conditional
}
group("grdp") {
  public_deps = [
    ":external_js_bundles",
    ":fonts_grdp",
    "//brave/components/brave_account/resources/opaque_ke",
  ]
}
""",
    ]

    for idx, var in enumerate(webui_variants, 1):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_brave = os.path.join(tmpdir, "mock_brave")
            setup_mock_brave(mock_brave)
            target = os.path.join(mock_brave, "ui/webui/resources/BUILD.gn")
            with open(target, "w") as f:
                f.write(var)

            res = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
            assert res.returncode == 0, f"WebUI BUILD.gn variant {idx} failed: {res.stderr}\n{res.stdout}"
            with open(target) as f:
                c = f.read()
                assert "group(\"grdp\")" in c
                grdp_body = c.split("group(\"grdp\")", 1)[1]
                assert "if (include_polymer)" in grdp_body
                top_part, poly_part = grdp_body.split("if (include_polymer)", 1)
                assert ":external_js_bundles" not in top_part
                assert "opaque_ke" not in top_part
                assert ":external_js_bundles" in poly_part
                assert "opaque_ke" in poly_part
                if idx == 2:
                    assert ":extra_polymer_component" in poly_part
                elif idx == 3:
                    assert "Comment with [brackets]" in top_part

            # Idempotence
            res_idem = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
            assert res_idem.returncode == 0, f"WebUI BUILD.gn variant {idx} idempotence failed: {res_idem.stderr}"
            assert "Skipped ui/webui/resources/BUILD.gn (already patched)" in res_idem.stdout

    # 2. Test sources.gni resilience
    sources_variants = [
        # Variant A: Different ordering with external_js.grdp first
        """brave_resources_extra_grdps = [
  "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
  "$brave_resources_extra_grdps_path/brave_fonts_resources.grdp",
  "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
  "$brave_resources_extra_grdps_path/brave_static_resources.grdp",
]
if (!is_android && !is_ios) {
  brave_resources_extra_grdps +=
      [ "$brave_resources_extra_grdps_path/resources.grdp" ]
}
""",
        # Variant B: Multiple items already in conditional
        """brave_resources_extra_grdps = [
  "$brave_resources_extra_grdps_path/brave_fonts_resources.grdp",
  "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
  "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
]
if (!is_android && !is_ios) {
  brave_resources_extra_grdps += [
    "$brave_resources_extra_grdps_path/resources.grdp",
    "$brave_resources_extra_grdps_path/extra_desktop.grdp",
  ]
}
""",
        # Variant C: No existing conditional block at all
        """brave_resources_extra_grdps = [
  "$brave_resources_extra_grdps_path/brave_fonts_resources.grdp",
  "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
  "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
]
""",
    ]

    for idx, var in enumerate(sources_variants, 1):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_brave = os.path.join(tmpdir, "mock_brave")
            setup_mock_brave(mock_brave)
            target = os.path.join(mock_brave, "ui/webui/resources/sources.gni")
            with open(target, "w") as f:
                f.write(var)

            res = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
            assert res.returncode == 0, f"sources.gni variant {idx} failed: {res.stderr}\n{res.stdout}"
            with open(target) as f:
                c = f.read()
                top_part, cond_part = c.split("if (!is_android && !is_ios)", 1)
                assert "external_js.grdp" not in top_part
                assert "opaque_ke.grdp" not in top_part
                assert "external_js.grdp" in cond_part
                assert "opaque_ke.grdp" in cond_part
                if idx == 2:
                    assert "extra_desktop.grdp" in cond_part

            # Idempotence
            res_idem = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
            assert res_idem.returncode == 0, f"sources.gni variant {idx} idempotence failed: {res_idem.stderr}"
            assert "Skipped ui/webui/resources/sources.gni (already patched)" in res_idem.stdout

    # 3. Test brave_java_resources.gni resilience
    res_variants = [
        # Variant A: Multi-line with trailing comma
        """brave_base_module_resources = [
  "java/res_chromium_base/drawable-night/themed_app_icon.xml",
  "java/res_chromium_base/drawable/sample.xml",
]
""",
        # Variant B: Multi-line without trailing comma
        """brave_base_module_resources = [
  "java/res_chromium_base/drawable-night/themed_app_icon.xml"
]
""",
        # Variant C: Compact single line
        """brave_base_module_resources = [ "java/res_chromium_base/drawable-night/themed_app_icon.xml" ]
""",
        # Variant D: Array with GN comments containing brackets
        """brave_base_module_resources = [
  # Note: [themed_app_icon] is required
  "java/res_chromium_base/drawable-night/themed_app_icon.xml",
]
""",
    ]

    for idx, var in enumerate(res_variants, 1):
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_brave = os.path.join(tmpdir, "mock_brave")
            setup_mock_brave(mock_brave)
            target = os.path.join(mock_brave, "android/brave_java_resources.gni")
            with open(target, "w") as f:
                f.write(var)

            res = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
            assert res.returncode == 0, f"brave_java_resources.gni variant {idx} failed: {res.stderr}\n{res.stdout}"
            with open(target) as f:
                c = f.read()
                assert "java/res_chromium_base/mipmap-anydpi-v26/app_icon.xml" in c
                assert "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon.xml" in c
                assert "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon_background.xml" in c
                if idx == 4:
                    assert "# Note: [themed_app_icon] is required" in c

            # Idempotence
            res_idem = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
            assert res_idem.returncode == 0, f"brave_java_resources.gni variant {idx} idempotence failed: {res_idem.stderr}"
            assert "Skipped android/brave_java_resources.gni (already patched)" in res_idem.stdout

    # 4. Test version files
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_src = os.path.join(tmpdir, "mock_src")
        mock_brave = os.path.join(mock_src, "brave")
        setup_mock_brave(mock_brave)
        setup_mock_src(mock_src)

        v_tmpl = os.path.join(mock_src, "chrome/android/java/version_strings.xml.template")
        with open(v_tmpl, "w") as f:
            f.write('    <string name="product_version" translatable="false">@MAJOR@.@MINOR@.@BUILD@.@PATCH@</string>\n')

        res = subprocess.run([sys.executable, script, mock_brave, f"--src-dir={mock_src}", "--strict"], capture_output=True, text=True)
        assert res.returncode == 0, f"Version files mutator failed: {res.stderr}\n{res.stdout}"
        with open(v_tmpl) as f:
            c = f.read()
            assert ">@MINOR@.@BUILD@.@PATCH@<" in c
            assert "@MAJOR@" not in c

        # Idempotence
        res_idem = subprocess.run([sys.executable, script, mock_brave, f"--src-dir={mock_src}", "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"Version files idempotence failed: {res_idem.stderr}"
        assert "Skipped chrome/android/java/version_strings.xml.template (already patched)" in res_idem.stdout

    # 5. Test quick_search_engines mutator resilience
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_brave = os.path.join(tmpdir, "brave")
        mock_files = setup_mock_brave(mock_brave)
        qse_view = mock_files["quick_search_view_adapter"]
        qse_settings = mock_files["quick_search_adapter"]

        res = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
        assert res.returncode == 0, f"QSE mutator failed: {res.stderr}\n{res.stdout}"

        with open(qse_view) as f:
            view_content = f.read()
            assert "R.drawable.ic_brave_icon_search" in view_content
        with open(qse_settings) as f:
            settings_content = f.read()
            assert "R.drawable.ic_brave_icon_search" in settings_content

        # Verify idempotence
        res_idem = subprocess.run([sys.executable, script, mock_brave, "--strict"], capture_output=True, text=True)
        assert res_idem.returncode == 0, f"QSE idempotence failed: {res_idem.stderr}"
        assert "Skipped browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/views/QuickSearchEnginesViewAdapter.java (already patched)" in res_idem.stdout
        assert "Skipped browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/settings/QuickSearchEnginesAdapter.java (already patched)" in res_idem.stdout

    print("PASS: test_webui_and_feature_mutators_resilience_and_formatting")


if __name__ == "__main__":
    try:
        test_python311_syntax_compatibility()
        test_apply_features()
        test_apply_branding()
        test_patch_suite()
        test_timestamp_gni_gn_evaluation()
        test_timestamp_gni_resilience_and_formatting()
        test_validate_expectations_gn_evaluation()
        test_validate_expectations_resilience_and_formatting()
        test_webui_and_feature_mutators_resilience_and_formatting()
        print("ALL MUTATOR & PATCH TESTS PASSED.")
    except Exception as e:
        import sys, traceback
        traceback.print_exc()
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
