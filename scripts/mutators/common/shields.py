"""
Shields Feature Mutator (scripts/mutators/common/shields.py)
Enables kBraveAdblockDefault1pBlocking by default so first-party ad blocking works cleanly in Standard Mode.
"""

import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    ctx.replace_in_file(
        "components/brave_shields/core/common/features.cc",
        re.compile(
            r'BASE_FEATURE\(\s*kBraveAdblockDefault1pBlocking\s*,\s*base::FEATURE_DISABLED_BY_DEFAULT\s*\);'
        ),
        "BASE_FEATURE(kBraveAdblockDefault1pBlocking, base::FEATURE_ENABLED_BY_DEFAULT);",
        check_token="BASE_FEATURE(kBraveAdblockDefault1pBlocking, base::FEATURE_ENABLED_BY_DEFAULT);"
    )
