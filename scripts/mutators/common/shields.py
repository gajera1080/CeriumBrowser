"""
Shields Feature Mutator (scripts/mutators/common/shields.py)
Enables aggressive shields ad/tracker blocking and 1p blocking by default.
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

    ctx.replace_in_file(
        "components/brave_shields/core/common/brave_shields_settings_values.h",
        "/*default_value=*/ControlType::BLOCK_THIRD_PARTY>;",
        "/*default_value=*/ControlType::BLOCK>;",
        check_token="/*default_value=*/ControlType::BLOCK>;"
    )
