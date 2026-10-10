"""
Android Validation Expectations Mutator (scripts/mutators/android/expectations.py)
Fixes validate_expectations unresolved dependencies when secondary ABI is disabled.
Guards 32-bit and dual-ABI expectations with `if (defined(android_app_secondary_abi))`.
"""

import os
import re
from scripts.mutators.context import MutatorContext


def _patch_validate_expectations_in_gn(content):
    m = re.search(r'([ \t]*)group\s*\(\s*"validate_expectations"\s*\)\s*\{', content)
    if not m:
        return content, False, False

    start_idx = m.start()
    brace_open_idx = m.end() - 1
    group_indent = m.group(1)

    end_idx = MutatorContext.find_matching_char(content, brace_open_idx, "{", "}")
    if end_idx == -1:
        return content, False, True

    group_text = content[start_idx : end_idx + 1]
    if "defined(android_app_secondary_abi)" in group_text:
        return content, False, True

    deps_matches = list(re.finditer(r"([ \t]*)deps\s*\+=\s*\[", group_text))
    if not deps_matches:
        return content, False, True

    new_group_text = group_text
    any_transformed = False

    for match in reversed(deps_matches):
        m_start = match.start()
        indent = match.group(1)
        bracket_open_idx = match.end() - 1
        bracket_close_idx = MutatorContext.find_matching_char(new_group_text, bracket_open_idx, "[", "]")
        if bracket_close_idx == -1:
            continue

        items_block = new_group_text[bracket_open_idx + 1 : bracket_close_idx]
        lines = items_block.splitlines()
        primary_lines = []
        secondary_lines = []
        pending_comments = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                pending_comments.append(line)
                continue

            if "32" in stripped:
                secondary_lines.extend(pending_comments)
                pending_comments = []
                secondary_lines.append("  " + line if line.startswith(indent) else f"{indent}  {stripped}")
            else:
                primary_lines.extend(pending_comments)
                pending_comments = []
                primary_lines.append(line if line.startswith(indent) else f"{indent}{stripped}")

        primary_lines.extend(pending_comments)

        if not secondary_lines:
            continue

        replacement_parts = []
        if primary_lines:
            replacement_parts.append(f"{indent}deps += [\n")
            for pl in primary_lines:
                replacement_parts.append(f"{pl}\n")
            replacement_parts.append(f"{indent}]\n")

        replacement_parts.append(f"{indent}if (defined(android_app_secondary_abi)) {{\n")
        replacement_parts.append(f"{indent}  deps += [\n")
        for sl in secondary_lines:
            replacement_parts.append(f"{sl}\n")
        replacement_parts.append(f"{indent}  ]\n")
        replacement_parts.append(f"{indent}}}")

        rep_str = "".join(replacement_parts)
        new_group_text = new_group_text[:m_start] + rep_str + new_group_text[bracket_close_idx + 1 :]
        any_transformed = True

    if any_transformed:
        header = f"{group_indent}# In Cerium, enable_android_secondary_abi is disabled for single-arch builds.\n{group_indent}# Only validate 32-bit and dual-ABI targets when secondary ABI is enabled.\n"
        new_group_text = header + new_group_text
        new_content = content[:start_idx] + new_group_text + content[end_idx + 1 :]
        return new_content, True, True

    return content, False, True


def apply(ctx: MutatorContext):
    ctx.mutate_file("chrome/android/BUILD.gn", _patch_validate_expectations_in_gn, in_src=True)
