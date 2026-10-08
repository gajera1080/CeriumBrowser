"""
Search Widget & QSE Logo Mutator (scripts/mutators/android/search_widget.py)
Rebrands home screen search widget logo to Brave search lion and decouples
omnibox quick search engines Brave Search logo from rebranded shields icon.
"""

import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    # Rebrand home screen search widget logo to Brave search lion
    ctx.replace_in_file(
        "android/java/brave-res/layout/quick_action_search_and_bookmark_widget_layout.xml",
        'android:src="@mipmap/app_icon"',
        'android:src="@drawable/brave_icon_search"'
    )

    # Decouple omnibox quick search engines Brave Search logo from rebranded shields icon
    ctx.replace_in_file(
        "browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/views/QuickSearchEnginesViewAdapter.java",
        re.compile(
            r'quickSearchViewHolder\.mSearchEngineLogo\.setImageResource\s*\(\s*'
            r'R\.drawable\.(?:ic_social_brave_release_favicon_fullheight_color|brave_icon_search)\s*\);'
        ),
        "quickSearchViewHolder.mSearchEngineLogo.setImageResource(\n                    R.drawable.ic_brave_icon_search);",
        check_token="R.drawable.ic_brave_icon_search"
    )

    ctx.replace_in_file(
        "browser/quick_search_engines/android/java/src/org/chromium/brave/browser/quick_search_engines/settings/QuickSearchEnginesAdapter.java",
        re.compile(
            r'quickSearchEnginesSettingsViewHolder\.mSearchEngineLogo\.setImageResource\s*\(\s*'
            r'R\.drawable\.(?:ic_social_brave_release_favicon_fullheight_color|brave_icon_search)\s*\);'
        ),
        "quickSearchEnginesSettingsViewHolder.mSearchEngineLogo.setImageResource(\n                    R.drawable.ic_brave_icon_search);",
        check_token="R.drawable.ic_brave_icon_search"
    )
