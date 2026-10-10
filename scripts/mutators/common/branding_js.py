"""
WebUI Branding Logo Mutator (scripts/mutators/common/branding_js.py)
Points WebUI chrome_logo_dark.svg override in branding.js to app/theme/brave/product_logo.svg
instead of @brave/leo node_modules so WebUI pages use the colored Cerium logo.
"""

import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    ctx.replace_in_file(
        "build/commands/lib/branding.js",
        re.compile(
            r"path\.join\(\s*config\.braveCoreDir,\s*['\"]node_modules['\"],\s*['\"]@brave['\"],\s*['\"]leo['\"],\s*['\"]icons['\"],\s*config\.getBraveLogoIconName\(\),?\s*\)",
            re.DOTALL
        ),
        """path.join(
      braveAppDir,
      'theme',
      'brave',
      'product_logo.svg',
    )""",
        check_token="'product_logo.svg'"
    )
