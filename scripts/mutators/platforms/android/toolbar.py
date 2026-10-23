"""
Android Bottom Navigation Toolbar Mutator (scripts/mutators/platforms/android/toolbar.py)
Disables the bottom navigation toolbar by default out-of-the-box.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    # Disable bottom toolbar by default on first launch in BottomToolbarConfiguration
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/toolbar/bottom/BottomToolbarConfiguration.java",
        ".readBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, true);",
        ".readBoolean(BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY, false);",
    )
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/toolbar/bottom/BottomToolbarConfiguration.java",
        "boolean enable = true;",
        "boolean enable = false;",
    )

    # Silence unused method warning for isSmallScreen() in BottomToolbarConfiguration
    ctx.replace_in_file(
        "android/java/org/chromium/chrome/browser/toolbar/bottom/BottomToolbarConfiguration.java",
        "    private static boolean isSmallScreen() {",
        "    @SuppressWarnings(\"unused\")\n    private static boolean isSmallScreen() {",
    )
