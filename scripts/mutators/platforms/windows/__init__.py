"""Windows-specific mutator components (scripts/mutators/platforms/windows/__init__.py)."""
from scripts.mutators.platforms.windows import installer, branding

ALL_WINDOWS_MUTATORS = [
    installer,
    branding,
]
