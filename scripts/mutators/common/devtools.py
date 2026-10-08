"""
DevTools Frontend GN Mutator (scripts/mutators/common/devtools.py)
Silences GN unused variable errors in third_party/devtools-frontend files.
"""

import os
import re
from scripts.mutators.context import MutatorContext


def _strip_gn_comments_and_strings(line):
    res = []
    in_str = False
    escaped = False
    for ch in line:
        if in_str:
            if ch == "\\" and not escaped:
                escaped = True
            elif ch == '"' and not escaped:
                in_str = False
            else:
                escaped = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '#':
                break
            else:
                res.append(ch)
    return "".join(res)


def _silence_public_inputs_in_gn(content):
    lines = content.splitlines(keepends=True)
    new_lines = []
    i = 0
    modified = False
    found_any = False

    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([ \t]*)public_inputs\s*(\+?=)", line)
        if m:
            found_any = True
            indent = m.group(1)
            stmt_lines = [line]
            clean = _strip_gn_comments_and_strings(line)
            open_parens = clean.count("(") - clean.count(")")
            open_brackets = clean.count("[") - clean.count("]")
            open_braces = clean.count("{") - clean.count("}")
            stripped = clean.strip()
            ends_with_op = stripped.endswith("+") or stripped.endswith("=")

            while i + 1 < len(lines) and (open_parens > 0 or open_brackets > 0 or open_braces > 0 or ends_with_op):
                i += 1
                next_line = lines[i]
                stmt_lines.append(next_line)
                clean_next = _strip_gn_comments_and_strings(next_line)
                open_parens += clean_next.count("(") - clean_next.count(")")
                open_brackets += clean_next.count("[") - clean_next.count("]")
                open_braces += clean_next.count("{") - clean_next.count("}")
                stripped_next = clean_next.strip()
                ends_with_op = stripped_next.endswith("+") or stripped_next.endswith("=")

            new_lines.extend(stmt_lines)

            has_not_needed = False
            j = i + 1
            while j < len(lines) and (lines[j].strip() == "" or lines[j].strip().startswith("#")):
                j += 1
            if j < len(lines) and "not_needed" in lines[j] and "public_inputs" in lines[j]:
                has_not_needed = True

            if not has_not_needed:
                newline = "\r\n" if line.endswith("\r\n") else "\n"
                new_lines.append(f"{indent}not_needed([ \"public_inputs\" ]){newline}")
                modified = True
        else:
            new_lines.append(line)
        i += 1

    return "".join(new_lines), modified, found_any


def apply(ctx: MutatorContext):
    if not ctx.src_dir:
        return

    target_gn_files = [
        "third_party/devtools-frontend/src/scripts/build/typescript/ts_library_split.gni",
        "third_party/devtools-frontend/src/scripts/build/typescript/typescript.gni",
        "third_party/devtools-frontend/src/scripts/build/ninja/copy.gni",
        "third_party/devtools-frontend/src/scripts/build/ninja/devtools_pre_built.gni",
        "third_party/devtools-frontend/src/scripts/build/ninja/devtools_entrypoint.gni",
        "third_party/devtools-frontend/src/front_end/models/ai_assistance/skills/BUILD.gn",
    ]

    for devtools_sub in ["third_party/devtools-frontend/src", "third_party/devtools-frontend"]:
        full_dir = os.path.join(ctx.src_dir, devtools_sub)
        if os.path.isdir(full_dir):
            for root, dirs, files in os.walk(full_dir):
                dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "out", "target")]
                for file in files:
                    if file.endswith(".gni") or file == "BUILD.gn":
                        rel = os.path.relpath(os.path.join(root, file), ctx.src_dir)
                        if rel not in target_gn_files:
                            target_gn_files.append(rel)
            break

    for gn_rel in target_gn_files:
        gn_path = os.path.join(ctx.src_dir, gn_rel)
        if not os.path.exists(gn_path):
            continue
        with open(gn_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if "public_inputs" not in content:
            continue
        new_content, modified, found_any = _silence_public_inputs_in_gn(content)
        if modified:
            with open(gn_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Patched {gn_rel} (silenced public_inputs)")
        elif found_any:
            print(f"Skipped {gn_rel} (already patched)")
