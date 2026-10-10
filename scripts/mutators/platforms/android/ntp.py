"""
Android NTP Defaults Mutator (scripts/mutators/platforms/android/ntp.py)
Disables top sites and Brave stats on the Android New Tab Page by default out-of-the-box.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    # Disable Top Sites by default on Android NTP
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/ntp/NtpUtil.java",
        ".readBoolean(BackgroundImagesPreferences.PREF_SHOW_TOP_SITES, true);",
        ".readBoolean(BackgroundImagesPreferences.PREF_SHOW_TOP_SITES, false);",
    )

    # Disable Brave Stats by default on Android NTP
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/ntp/NtpUtil.java",
        ".readBoolean(BackgroundImagesPreferences.PREF_SHOW_BRAVE_STATS, true);",
        ".readBoolean(BackgroundImagesPreferences.PREF_SHOW_BRAVE_STATS, false);",
    )
