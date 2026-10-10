"""
Android Bottom Navigation Toolbar Mutator (scripts/mutators/platforms/android/toolbar.py)
Disables the bottom navigation toolbar by default out-of-the-box.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    # Disable bottom toolbar by default on first launch in BottomToolbarConfiguration
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/toolbar/bottom/BottomToolbarConfiguration.java",
        """        if (ChromeSharedPreferences.getInstance()
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
        }""",
        """        if (ChromeSharedPreferences.getInstance()
                .readBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_SET_KEY, false)) {
            return ChromeSharedPreferences.getInstance()
                    .readBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, false);
        } else {
            ChromeSharedPreferences.getInstance()
                    .writeBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_SET_KEY, true);
            boolean enable = false;
            ChromeSharedPreferences.getInstance()
                    .writeBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, enable);

            return enable;
        }""",
    )

    # Silence unused method warning for isSmallScreen() in BottomToolbarConfiguration
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/toolbar/bottom/BottomToolbarConfiguration.java",
        "    private static boolean isSmallScreen() {",
        "    @SuppressWarnings(\"unused\")\n    private static boolean isSmallScreen() {",
    )

    # Disable bottom toolbar fallback check in BraveToolbarManager
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/toolbar/BraveToolbarManager.java",
        """            if (sharedPreferences.getBoolean(
                    BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, true)) {""",
        """            if (sharedPreferences.getBoolean(
                    BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, false)) {""",
    )
