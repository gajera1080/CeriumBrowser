"""
NTP Sponsored Ads & Sponsored Sites Silencing Mutator (scripts/mutators/common/ntp_ads.py)
Changes default of brave_ads::prefs::kSponsoredEnabled from true to false in
components/brave_ads/core/internal/prefs/pref_registry.cc so sponsored wallpaper
takeovers and sponsored top site tiles are disabled by default out-of-the-box.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    ctx.replace_in_file(
        "components/brave_ads/core/internal/prefs/pref_registry.cc",
        "registry->RegisterBooleanPref(prefs::kSponsoredEnabled, true);",
        "registry->RegisterBooleanPref(prefs::kSponsoredEnabled, false);",
        check_token="registry->RegisterBooleanPref(prefs::kSponsoredEnabled, false);",
    )
