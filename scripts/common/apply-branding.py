#!/usr/bin/env python3
"""
Programmatic Braving String & Localization Mutator (apply-branding.py)

Safely rebrands user-visible "Brave" browser and Shields strings to "Braving"
across Android and shared cross-platform .grd/.grdp files, remapping XTB
translation fingerprints so all locales resolve the updated strings cleanly.

Preserves:
- Hidden/debloated feature strings (Leo, Wallet, Rewards, VPN, News, Talk, etc.)
- "Brave Search" (kept as upstream search provider name)
- URLs, domains (brave.com, brave.software), protocol schemes (brave://)
- XML element/attribute identifiers (name="IDS_...", <ph> placeholders)
"""

import hashlib
import os
import re
import sys
import xml.etree.ElementTree as ET

BLOAT_KEYWORDS = (
    "LEO",
    "AI_CHAT",
    "WALLET",
    "REWARDS",
    "VPN",
    "TALK",
    "BRAVE_NEWS",
    "CRYPTO",
    "SOLANA",
    "TOR",
    "IPFS",
    "WAYBACK",
    "SPEEDREADER",
)

AUTHORS_RE = re.compile(r"\b(?:Brave|Braving)\s+Authors\b")

# Match standalone "Brave" (or "Brave's"), excluding:
# - URLs/domains/paths (preceded by ., /, _, - or followed by ://, .[a-zA-Z])
# - "Brave Search" (unless followed by "widget", e.g. "Try the Brave Search widget" -> "Try the Braving Search widget")
# - Debloated sub-brands ("Brave Rewards", "Brave Wallet", etc.)
BRAVE_RE = re.compile(
    r"(?<![./_-])\bBrave\b"
    r"(?!://|\.[a-zA-Z]|\s+(?:Search(?!\s+[Ww]idget\b)|Rewards|Leo|Wallet|News|Talk|VPN|Ads|Creators)\b)"
)

BRAVING_CHECK_RE = re.compile(r"\bBraving\b")
MSG_BLOCK_RE = re.compile(r"<message\b[^>]*>.*?</message>", re.DOTALL)
PART_FILE_RE = re.compile(r'<part\s+file="([^"]+\.grdp)"')
XTB_FILE_RE = re.compile(r'<file\s+[^>]*path="([^"]+\.xtb)"')
PH_OR_TAG_RE = re.compile(r"(<ph\b[^>]*>.*?</ph>|<[^>]+>)", re.DOTALL)
TRANSLATION_RE = re.compile(
    r'(<translation\s+[^>]*\bid=")(\d+)("[^>]*>)(.*?)(</translation>)',
    re.DOTALL,
)

TOP_LEVEL_GRD_FILES = (
    "browser/ui/android/strings/android_brave_strings.grd",
    "browser/ui/android/strings/android_chrome_strings.grd",
    "browser/ui/android/strings/android_chrome_strings_override.grd",
    "components/browser_ui/strings/android/browser_ui_strings.grd",
    "components/browser_ui/strings/android/browser_ui_strings_override.grd",
    "android/features/tab_ui/java/strings/android_chrome_tab_ui_strings.grd",
    "android/features/tab_ui/java/strings/android_chrome_tab_ui_strings_override.grd",
    "components/webapps/browser/android/android_webapps_strings.grd",
    "components/webapps/browser/android/android_webapps_strings_override.grd",
    "browser/quick_search_engines/android/java/strings/android_quick_search_engines_strings.grd",
    "app/brave_strings.grd",
    "app/brave_strings_override.grd",
    "app/brave_origin_strings.grd",
    "app/brave_generated_resources.grd",
    "app/generated_resources.grd",
    "app/generated_resources_override.grd",
    "components/resources/brave_components_strings.grd",
    "components/components_brave_strings.grd",
    "components/components_brave_strings_override.grd",
    "components/components_brave_origin_strings.grd",
    "components/components_strings.grd",
    "components/components_strings_override.grd",
)

EXPLICIT_GRDP_FILES = (
    "components/browser_ui/strings/android/site_settings.grdp",
    "app/settings_brave_strings.grdp",
    "app/settings_brave_strings_override.grdp",
    "app/brave_settings_strings.grdp",
    "components/resources/brave_shields_strings.grdp",
)

XML_PREFERENCE_FILES = (
    "android/java/res/xml/developer_preferences.xml",
)


def unsigned_fp(s: str) -> int:
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:16], 16)


def signed_fp(s: str) -> int:
    fp = unsigned_fp(s)
    if fp & 0x8000000000000000:
        fp = -((~fp & 0xFFFFFFFFFFFFFFFF) + 1)
    return fp


def clean_triple_quoted(val: str) -> str:
    val = val.strip()
    if val.startswith("'''"):
        val = val[3:]
    if val.endswith("'''"):
        val = val[:-3]
    return val.strip()


def get_fingerprint_for_xtb(msg_elem: ET.Element) -> str:
    """Computes Grit's 63-bit XTB translation fingerprint for a <message> element."""
    s = msg_elem.text or ""
    for ph in msg_elem.findall("ph"):
        s += (ph.get("name") or "").upper() + (ph.tail or "")
    s = clean_triple_quoted(s.strip())
    fp = signed_fp(s)
    meaning = msg_elem.get("meaning")
    if meaning:
        fp2 = signed_fp(meaning)
        if fp < 0:
            fp = fp2 + (fp << 1) + 1
        else:
            fp = fp2 + (fp << 1)
    return str(fp & 0x7FFFFFFFFFFFFFFF)


TOR_TOKEN_RE = re.compile(r"(?<![A-Z0-9])TOR(?![A-Z0-9])")


def _matches_bloat_keyword(upper_text: str) -> bool:
    for k in BLOAT_KEYWORDS:
        if k == "TOR":
            if TOR_TOKEN_RE.search(upper_text):
                return True
        elif k in upper_text:
            return True
    return False


def should_skip_bloat(name: str, desc: str) -> bool:
    combined = f"{name or ''} {desc or ''}".upper()
    return _matches_bloat_keyword(combined)


def should_skip_grdp_file(rel_path: str) -> bool:
    base = os.path.basename(rel_path).upper()
    if base == "CHROMEOS_STRINGS.GRDP":
        return True
    return _matches_bloat_keyword(base)


def replace_outside_ph_and_tags(block_str: str) -> str:
    parts = PH_OR_TAG_RE.split(block_str)
    for i in range(0, len(parts), 2):
        parts[i] = AUTHORS_RE.sub("Braving Contributors", parts[i])
        parts[i] = BRAVE_RE.sub("Braving", parts[i])
    return "".join(parts)


def process_grd_or_grdp_file(full_path: str, fp_map: dict, branded_fps: set) -> int:
    if not os.path.isfile(full_path):
        return 0

    with open(full_path, "r", encoding="utf-8") as f:
        content = f.read()

    mutated_count = 0

    def repl_msg(match: re.Match) -> str:
        nonlocal mutated_count
        msg_str = match.group(0)
        has_brave = "Brave" in msg_str
        has_braving = "Braving" in msg_str
        has_authors = "Authors" in msg_str
        if not has_brave and not has_braving and not has_authors:
            return msg_str

        try:
            elem = ET.fromstring(msg_str)
        except Exception:
            return msg_str

        name = elem.get("name", "")
        desc = elem.get("desc", "")
        if should_skip_bloat(name, desc):
            return msg_str

        new_msg_str = replace_outside_ph_and_tags(msg_str)
        if new_msg_str == msg_str:
            if has_braving:
                branded_fps.add(get_fingerprint_for_xtb(elem))
            return msg_str

        try:
            new_elem = ET.fromstring(new_msg_str)
        except Exception:
            return msg_str

        old_fp = get_fingerprint_for_xtb(elem)
        new_fp = get_fingerprint_for_xtb(new_elem)
        if old_fp != new_fp:
            fp_map[old_fp] = new_fp
        branded_fps.add(new_fp)
        mutated_count += 1
        return new_msg_str

    new_content = MSG_BLOCK_RE.sub(repl_msg, content)
    if new_content != content:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return mutated_count


def update_xtb_file(xtb_path: str, fp_map: dict, branded_fps: set) -> int:
    if not os.path.isfile(xtb_path) or (not fp_map and not branded_fps):
        return 0

    with open(xtb_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Fast check: does any old_fp in fp_map appear in this XTB file?
    has_any = any(old_fp in content for old_fp in fp_map)
    if not has_any:
        return 0

    updated_count = 0
    seen_ids = set()

    # First pass: collect existing IDs that won't be remapped so we avoid creating duplicate IDs
    for m in TRANSLATION_RE.finditer(content):
        tid = m.group(2)
        if tid not in fp_map:
            seen_ids.add(tid)

    def repl_trans(match: re.Match) -> str:
        nonlocal updated_count
        prefix, tid, mid, body, suffix = match.groups()
        if tid not in fp_map:
            return match.group(0)

        new_id = fp_map[tid]
        if new_id in seen_ids:
            # Avoid duplicate translation IDs in the same translationbundle
            updated_count += 1
            return ""
        seen_ids.add(new_id)
        new_body = replace_outside_ph_and_tags(body)
        updated_count += 1
        return f"{prefix}{new_id}{mid}{new_body}{suffix}"

    new_content = TRANSLATION_RE.sub(repl_trans, content)
    if new_content != content:
        with open(xtb_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return updated_count


PREF_ATTR_RE = re.compile(r'(\b(?:android|app):(?:title|summary|dialogTitle|dialogMessage)=")([^"]*)(")')
STRING_NODE_RE = re.compile(r'(<string\b[^>]*>)([^<]*)(</string>)')
BRAVE_WORD_RE = re.compile(r"\b(?:Brave|Braving)(\s*-\s*Debug\b)?")


def process_xml_preferences(brave_dir: str) -> int:
    changed = 0
    candidate_prefs = list(XML_PREFERENCE_FILES)
    for res_dir in ["android/java/res/xml", "android/java/brave-res/xml"]:
        full_res = os.path.join(brave_dir, res_dir)
        if os.path.isdir(full_res):
            for f in sorted(os.listdir(full_res)):
                if f.endswith(".xml"):
                    rel = os.path.relpath(os.path.join(full_res, f), brave_dir)
                    if rel not in candidate_prefs:
                        candidate_prefs.append(rel)

    for rel in candidate_prefs:
        p = os.path.join(brave_dir, rel)
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = PREF_ATTR_RE.sub(
            lambda m: m.group(1) + BRAVE_RE.sub("Braving", m.group(2)) + m.group(3),
            content,
        )
        if new_content != content:
            with open(p, "w", encoding="utf-8") as f:
                f.write(new_content)
            changed += 1

    for rel in [
        "app/theme/brave/android/res_brave_base/values/channel_constants.xml",
        "app/theme/brave/android/res_brave_default_base/values/channel_constants.xml",
        "app/theme/brave/android/values/channel_constants.xml",
    ]:
        p = os.path.join(brave_dir, rel)
        if not os.path.isfile(p):
            continue
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = STRING_NODE_RE.sub(
            lambda m: m.group(1) + BRAVE_WORD_RE.sub(
                lambda word: "Braving" + (word.group(1) or ""), m.group(2)
            ) + m.group(3),
            content,
        )
        if new_content != content:
            with open(p, "w", encoding="utf-8") as f:
                f.write(new_content)
            changed += 1
    return changed


def apply_branding(brave_dir: str, strict: bool = False) -> int:
    if not os.path.isdir(brave_dir):
        msg = f"ERROR: brave-core directory does not exist: {brave_dir}"
        print(msg, file=sys.stderr)
        return 1

    total_messages = 0
    total_files = 0
    total_xtbs = 0
    file_results = {}

    def run_file(norm_path: str, display_rel: str):
        nonlocal total_messages, total_files
        if norm_path not in file_results:
            f_fp_map = {}
            f_branded_fps = set()
            c = process_grd_or_grdp_file(norm_path, f_fp_map, f_branded_fps)
            file_results[norm_path] = (c, f_fp_map, f_branded_fps)
            if c > 0:
                total_messages += c
                total_files += 1
                print(f" [OK] Branded {c} messages in {display_rel}")
        return file_results[norm_path]

    # Discover top-level GRDs dynamically to handle newly added upstream string files
    grd_targets = list(TOP_LEVEL_GRD_FILES)
    for root, dirs, files in os.walk(brave_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "vendor", "out", "target", "build-workspace")]
        for f in files:
            if f.endswith(("_strings.grd", "_strings_override.grd", "_generated_resources.grd")):
                rel = os.path.relpath(os.path.join(root, f), brave_dir)
                if rel not in grd_targets and not should_skip_bloat(rel, ""):
                    grd_targets.append(rel)

    # Process top-level GRDs, their <part> GRDPs, and their <file> XTBs
    for rel_grd in grd_targets:
        grd_path = os.path.join(brave_dir, rel_grd)
        if not os.path.isfile(grd_path):
            continue

        grd_dir = os.path.dirname(grd_path)
        with open(grd_path, "r", encoding="utf-8") as f:
            grd_raw = f.read()

        part_rels = PART_FILE_RE.findall(grd_raw)
        xtb_rels = XTB_FILE_RE.findall(grd_raw)

        fp_map = {}
        branded_fps = set()

        # Process the GRD itself
        norm_grd = os.path.normpath(grd_path)
        _, g_fp_map, g_branded = run_file(norm_grd, rel_grd)
        fp_map.update(g_fp_map)
        branded_fps.update(g_branded)

        # Process <part file="...grdp"> children
        for part_rel in part_rels:
            if should_skip_grdp_file(part_rel):
                continue
            part_path = os.path.normpath(os.path.join(grd_dir, part_rel))
            if os.path.isfile(part_path):
                rel_part_display = os.path.relpath(part_path, brave_dir)
                _, p_fp_map, p_branded = run_file(part_path, rel_part_display)
                fp_map.update(p_fp_map)
                branded_fps.update(p_branded)

            if part_rel.endswith(".grdp"):
                ov_rel = part_rel[:-5] + "_override.grdp"
                ov_path = os.path.normpath(os.path.join(grd_dir, ov_rel))
                if os.path.isfile(ov_path) and not should_skip_grdp_file(ov_rel):
                    rel_ov_display = os.path.relpath(ov_path, brave_dir)
                    _, o_fp_map, o_branded = run_file(ov_path, rel_ov_display)
                    fp_map.update(o_fp_map)
                    branded_fps.update(o_branded)

        # Update XTB files for this GRD
        if fp_map:
            xtb_mod = 0
            for xtb_rel in xtb_rels:
                xtb_path = os.path.normpath(os.path.join(grd_dir, xtb_rel))
                if update_xtb_file(xtb_path, fp_map, branded_fps) > 0:
                    xtb_mod += 1
            total_xtbs += xtb_mod
            if xtb_mod > 0:
                print(f" [OK] Updated {len(fp_map)} translation fingerprints across {xtb_mod} XTB locale files for {rel_grd}")

    # Process any explicit GRDPs not already visited via a parent GRD
    for rel_grdp in EXPLICIT_GRDP_FILES:
        grdp_path = os.path.normpath(os.path.join(brave_dir, rel_grdp))
        if os.path.isfile(grdp_path):
            run_file(grdp_path, rel_grdp)

    pref_count = process_xml_preferences(brave_dir)
    if pref_count > 0:
        print(f" [OK] Branded {pref_count} Android XML preference file(s).")

    print(
        f"Braving string branding complete: {total_messages} messages updated across "
        f"{total_files} GRD/GRDP files and {total_xtbs} XTB translation files."
    )
    return 0


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-brave-core> [--strict]", file=sys.stderr)
        sys.exit(1)

    brave_dir = sys.argv[1]
    strict = "--strict" in sys.argv[2:] or os.environ.get("CI") == "true"
    sys.exit(apply_branding(brave_dir, strict=strict))


if __name__ == "__main__":
    main()
