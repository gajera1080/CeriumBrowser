"""
Android Base Module Resources Mutator (scripts/mutators/android/resources.py)
Registers Braving mipmap-anydpi-v26 vector app icons in brave_base_module_resources
so chrome_base_module_resources and chrome_public_apk_base_module_resources list all files.
"""

import re
from scripts.mutators.context import MutatorContext


def _patch_brave_java_resources_gni(content):
    if "mipmap-anydpi-v26/app_icon.xml" in content:
        return content, False, True
    m = re.search(r'\bbrave_base_module_resources\s*=\s*\[', content)
    if not m:
        return content, False, False
    bracket_open = m.end() - 1
    bracket_close = MutatorContext.find_matching_char(content, bracket_open, "[", "]")
    if bracket_close == -1:
        return content, False, False
    items = content[bracket_open + 1 : bracket_close]
    extra_items = """
  "java/res_chromium_base/mipmap-anydpi-v26/app_icon.xml",
  "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon.xml",
  "java/res_chromium_base/mipmap-anydpi-v26/layered_app_icon_background.xml",
"""
    trimmed = items.rstrip()
    comma = "" if trimmed.endswith(",") else ","
    new_items = trimmed + comma + extra_items
    new_content = content[: bracket_open + 1] + new_items + content[bracket_close :]
    return new_content, True, True


def apply(ctx: MutatorContext):
    ctx.mutate_file("android/brave_java_resources.gni", _patch_brave_java_resources_gni)
