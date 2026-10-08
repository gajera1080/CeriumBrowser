"""Android-specific mutator components (scripts/mutators/platforms/android/__init__.py)."""
from scripts.mutators.platforms.android import nala, resources, search_widget, version_display, toolchain, expectations

ALL_ANDROID_MUTATORS = [
    nala,
    resources,
    search_widget,
    version_display,
    toolchain,
    expectations,
]
