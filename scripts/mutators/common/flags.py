"""
Flags WebUI Mutator (scripts/mutators/common/flags.py)
Fixes brave://flags blank screen by neutralizing broken legacy DOM mutations in
brave_flags_overrides.js and brave_content_client.cc, restoring 100% native Lit 3.0 rendering.
"""

import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    ctx.replace_in_file(
        "components/flags_ui/resources/brave_flags_overrides.js",
        re.compile(r"document\.addEventListener\('DOMContentLoaded'[\s\S]*\}\);\s*"),
        "// Braving: Overrides disabled for clean Lit WebUI compatibility and complete de-branding.\n",
    )

    ctx.replace_in_file(
        "common/brave_content_client.cc",
        re.compile(
            r"scoped_refptr<base::RefCountedMemory>\s+BraveContentClient::GetDataResourceBytes\(\s*"
            r"int resource_id\)\s*\{\s*"
            r"if\s*\(resource_id\s*==\s*IDR_FLAGS_UI_APP_JS\)\s*\{[\s\S]*?\}\s*"
            r"return ChromeContentClient::GetDataResourceBytes\(resource_id\);\s*\}"
        ),
        """scoped_refptr<base::RefCountedMemory> BraveContentClient::GetDataResourceBytes(
    int resource_id) {
  // Braving: Direct delegate to pure Chromium Lit WebUI resources without Brave promo injection
  return ChromeContentClient::GetDataResourceBytes(resource_id);
}""",
    )
