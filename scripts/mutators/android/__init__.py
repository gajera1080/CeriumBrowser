"""Android-specific mutator components."""
from scripts.mutators.android import nala, resources, search_widget, version_display, toolchain, expectations

ALL_ANDROID_MUTATORS = [
    nala,
    resources,
    search_widget,
    version_display,
    toolchain,
    expectations,
]
