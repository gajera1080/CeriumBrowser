"""
NTP Defaults Mutator (scripts/mutators/common/ntp_ads.py)
Disables background images, sponsored images, top sites, and Brave stats by default out-of-the-box.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    # Disable sponsored ads / wallpaper takeovers
    ctx.replace_in_file(
        "components/brave_ads/core/internal/prefs/pref_registry.cc",
        "registry->RegisterBooleanPref(prefs::kSponsoredEnabled, true);",
        "registry->RegisterBooleanPref(prefs::kSponsoredEnabled, false);",
        check_token="registry->RegisterBooleanPref(prefs::kSponsoredEnabled, false);",
    )

    # Disable background images on New Tab Page
    ctx.replace_in_file(
        "components/ntp_background_images/common/view_counter_pref_registry.cc",
        "registry->RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, true);",
        "registry->RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, false);",
        check_token="registry->RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, false);",
    )

    # Disable Brave stats on New Tab Page
    ctx.replace_in_file(
        "browser/brave_profile_prefs.cc",
        "registry->RegisterBooleanPref(kNewTabPageShowStats, true);",
        "registry->RegisterBooleanPref(kNewTabPageShowStats, false);",
        check_token="registry->RegisterBooleanPref(kNewTabPageShowStats, false);",
    )

    # Disable top sites shortcuts on Desktop NTP directly in brave-core
    ctx.replace_in_file(
        "browser/brave_profile_prefs.cc",
        """  registry->SetDefaultPrefValue(ntp_prefs::kNtpCustomLinksVisible,
                                base::Value(false));""",
        """  registry->SetDefaultPrefValue(ntp_prefs::kNtpCustomLinksVisible,
                                base::Value(false));
  registry->SetDefaultPrefValue(ntp_prefs::kNtpShortcutsVisible,
                                base::Value(false));""",
        check_token="registry->SetDefaultPrefValue(ntp_prefs::kNtpShortcutsVisible, base::Value(false));",
    )

    # Disable top sites shortcuts when Chromium src is present
    if ctx.has_chromium_src():
        ctx.replace_in_src(
            "chrome/browser/prefs/browser_prefs.cc",
            "registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, true);",
            "registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, false);",
            check_token="registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, false);",
        )
        ctx.replace_in_src(
            "chrome/browser/ui/webui/cr_components/most_visited/most_visited_pref_observer.cc",
            "registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, true);",
            "registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, false);",
            check_token="registry->RegisterBooleanPref(ntp_prefs::kNtpShortcutsVisible, false);",
        )
