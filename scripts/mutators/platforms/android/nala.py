"""
Nala Drawables Mutator (scripts/mutators/android/nala.py)
Redirects Nala vector icon drawables to //brave/app/theme/brave/android/shields_drawables/$icon.
"""

import re
from scripts.mutators.context import MutatorContext


def _patch_nala_build_gn(content):
    has_outline = "ic_social_brave_outline_favicon_fullheight.xml" in content and "//brave/app/theme/brave/android/shields_drawables/" in content
    has_carved = "ic_social_brave_carved_favicon_fullheight.xml" in content and "//brave/app/theme/brave/android/shields_drawables/" in content
    has_monochrome = "ic_social_brave_monochrome_favicon_fullheight_color.xml" in content and "//brave/app/theme/brave/android/shields_drawables/" in content
    m_templ = re.search(r'template\s*\(\s*"nala_icon_override"\s*\)\s*\{', content)
    template_override = (
        'if (invoker.source == "ic_social_brave_outline_favicon_fullheight.xml") {'
        in content and
        '_source = "//brave/app/theme/brave/android/shields_drawables/${invoker.source}"'
        in content
    )
    if m_templ and template_override and has_outline and has_carved and has_monochrome:
        return content, False, True

    modified = False

    # 1. Template syntax
    if m_templ:
        if not template_override:
            pattern = re.compile(
                r'(_source\s*=\s*"\$nala_base_path/drawable/\$\{invoker\.source\}")',
                re.DOTALL
            )
            repl = """if (invoker.source == "ic_social_brave_outline_favicon_fullheight.xml") {
    _source = "//brave/app/theme/brave/android/shields_drawables/${invoker.source}"
  } else {
    _source = "$nala_base_path/drawable/${invoker.source}"
  }"""
            content, count = pattern.subn(repl, content, count=1)
            if count > 0:
                modified = True
                template_override = True
        if not template_override:
            return content, False, False
    else:
        # 2. Legacy copy(_name) syntax
        if "ic_social_brave_outline_favicon_fullheight.xml" not in content:
            pattern = re.compile(
                r'(\s*sources\s*=\s*\[\s*"\$nala_base_path/drawable/\$\{override\.source\}"\s*\])',
                re.DOTALL
            )
            repl = """
    if (override.source == "ic_social_brave_outline_favicon_fullheight.xml") {
      sources = [ "//brave/app/theme/brave/android/shields_drawables/${override.source}" ]
    } else {
      sources = [ "$nala_base_path/drawable/${override.source}" ]
    }"""
            content, count = pattern.subn(repl, content, count=1)
            if count > 0:
                modified = True

    # 3. copy("nala_icons")
    if "ic_social_brave_carved_favicon_fullheight.xml" not in content:
        pattern = re.compile(
            r'(\s*sources\s*\+=\s*\[\s*["\']//brave/node_modules/@brave/leo/tokens/android/drawable/\$icon["\']\s*\])',
            re.DOTALL
        )
        repl = """
    if (icon == "ic_social_brave_carved_favicon_fullheight.xml" ||
        icon == "ic_social_brave_outline_favicon_fullheight.xml" ||
        icon == "ic_social_brave_release_favicon_fullheight_color.xml" ||
        icon == "ic_social_brave_monochrome_favicon_fullheight_color.xml") {
      sources += [ "//brave/app/theme/brave/android/shields_drawables/$icon" ]
    } else {
      sources +=
          [ "//brave/node_modules/@brave/leo/tokens/android/drawable/$icon" ]
    }"""
        content, count = pattern.subn(repl, content, count=1)
        if count > 0:
            modified = True
    elif "ic_social_brave_monochrome_favicon_fullheight_color.xml" not in content:
        if 'icon == "ic_social_brave_release_favicon_fullheight_color.xml"' in content:
            content = content.replace(
                'icon == "ic_social_brave_release_favicon_fullheight_color.xml"',
                'icon == "ic_social_brave_release_favicon_fullheight_color.xml" ||\n        icon == "ic_social_brave_monochrome_favicon_fullheight_color.xml"',
                1
            )
            modified = True

    if modified:
        return content, True, True
    legacy_override = (
        'if (override.source == "ic_social_brave_outline_favicon_fullheight.xml") {'
        in content and
        'sources = [ "//brave/app/theme/brave/android/shields_drawables/${override.source}" ]'
        in content
    )
    return content, False, template_override or legacy_override


def apply(ctx: MutatorContext):
    ctx.mutate_file("android/nala/BUILD.gn", _patch_nala_build_gn)
