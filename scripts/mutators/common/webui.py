"""
WebUI Resources Mutator (scripts/mutators/common/webui.py)
Consolidates desktop-only WebUI bundles and opaque_ke into include_polymer block.
"""

import re
from scripts.mutators.context import MutatorContext


def _patch_webui_resources_build_gn(content):
    original_content = content
    m = re.search(r'\bgroup\s*\(\s*"grdp"\s*\)\s*\{', content)
    if not m:
        return content, False, False

    start = m.start()
    open_idx = m.end() - 1
    close_idx = MutatorContext.find_matching_char(content, open_idx, "{", "}")
    if close_idx == -1:
        return content, False, False

    body = content[start : close_idx + 1]

    # Find unconditional public_deps inside group("grdp")
    m_deps = re.search(r'\bpublic_deps\s*=\s*\[', body)
    if not m_deps:
        return content, False, False
    d_open = m_deps.end() - 1
    d_close = MutatorContext.find_matching_char(body, d_open, "[", "]")
    if d_close == -1:
        return content, False, False

    unconditional_deps = body[d_open + 1 : d_close]
    to_isolate = [":external_js_bundles", "resources/opaque_ke"]
    present_unconditional = [item for item in to_isolate if item in unconditional_deps]
    if not present_unconditional:
        if ":external_js_bundles" in body:
            return content, False, True

    deps_lines = unconditional_deps.splitlines()
    filtered_lines = [l for l in deps_lines if not any(item in l for item in to_isolate)]
    body = body[: d_open + 1] + "\n".join(filtered_lines) + "\n" + body[d_close:]

    m_poly = re.search(r'if\s*\(\s*include_polymer\s*\)\s*\{', body)
    if m_poly:
        p_open = m_poly.end() - 1
        p_close = MutatorContext.find_matching_char(body, p_open, "{", "}")
        if p_close == -1:
            return original_content, False, False
        poly_body = body[p_open + 1 : p_close]
        m_pld = re.search(r'public_deps\s*\+=\s*\[', poly_body)
        if m_pld:
            pd_open = m_pld.end() - 1
            pd_close = MutatorContext.find_matching_char(poly_body, pd_open, "[", "]")
            if pd_close == -1:
                return original_content, False, False
            before = poly_body[:pd_close].rstrip()
            last_char = before[-1:] if before else ""
            comma = "," if last_char not in (",", "[") else ""
            addition = comma + '\n      ":external_js_bundles",\n      "//brave/components/brave_account/resources/opaque_ke",'
            poly_body = before + addition + "\n    " + poly_body[pd_close:]
        else:
            return original_content, False, False
        body = body[: p_open + 1] + poly_body + body[p_close:]
    else:
        addition = """
  if (include_polymer) {
    public_deps += [
      ":build_grdp",
      ":external_js_bundles",
      "//brave/components/brave_account/resources/opaque_ke",
    ]
  }
"""
        body = body[:-1].rstrip() + "\n" + addition + "}"

    m_result_poly = re.search(r'if\s*\(\s*include_polymer\s*\)\s*\{', body)
    if not m_result_poly:
        return original_content, False, False
    result_poly_close = MutatorContext.find_matching_char(body, m_result_poly.end() - 1, "{", "}")
    if result_poly_close == -1:
        return original_content, False, False
    result_poly_body = body[m_result_poly.end() : result_poly_close]
    if ":external_js_bundles" not in result_poly_body or "//brave/components/brave_account/resources/opaque_ke" not in result_poly_body:
        return original_content, False, False

    res = content[:start] + body + content[close_idx + 1 :]
    return res, True, True


def _patch_webui_sources_gni(content):
    original_content = content
    m_arr = re.search(r'\bbrave_resources_extra_grdps\s*=\s*\[', content)
    if not m_arr:
        return content, False, False

    arr_open = m_arr.end() - 1
    arr_close = MutatorContext.find_matching_char(content, arr_open, "[", "]")
    if arr_close == -1:
        return content, False, False

    unconditional_items = content[arr_open + 1 : arr_close]
    to_move = ["external_js.grdp", "opaque_ke.grdp"]

    if not any(item in unconditional_items for item in to_move):
        if "external_js.grdp" in content:
            return content, False, True

    arr_lines = unconditional_items.splitlines()
    filtered_lines = [l for l in arr_lines if not any(item in l for item in to_move)]
    content = content[: arr_open + 1] + "\n".join(filtered_lines) + "\n" + content[arr_close:]

    m_cond = re.search(r'if\s*\(\s*!is_android\s*&&\s*!is_ios\s*\)\s*\{', content)
    if m_cond:
        c_open = m_cond.end() - 1
        c_close = MutatorContext.find_matching_char(content, c_open, "{", "}")
        if c_close == -1:
            return original_content, False, False
        cond_body = content[c_open + 1 : c_close]
        m_plus = re.search(r'brave_resources_extra_grdps\s*\+=\s*\[', cond_body)
        if m_plus:
            p_open = m_plus.end() - 1
            p_close = MutatorContext.find_matching_char(cond_body, p_open, "[", "]")
            if p_close == -1:
                return original_content, False, False
            before = cond_body[:p_close].rstrip()
            last_char = before[-1:] if before else ""
            comma = "," if last_char not in (",", "[") else ""
            addition = comma + '\n    "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",\n    "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",'
            cond_body = before + addition + "\n  " + cond_body[p_close:]
        else:
            return original_content, False, False
        content = content[: c_open + 1] + cond_body + content[c_close:]
    else:
        addition = """

if (!is_android && !is_ios) {
  brave_resources_extra_grdps += [
    "$root_gen_dir/brave/web-ui-external_js/external_js.grdp",
    "$root_gen_dir/brave/web-ui-opaque_ke/opaque_ke.grdp",
  ]
}
"""
        m_arr2 = re.search(r'\bbrave_resources_extra_grdps\s*=\s*\[', content)
        if m_arr2:
            close2 = MutatorContext.find_matching_char(content, m_arr2.end() - 1, "[", "]")
            if close2 != -1:
                content = content[: close2 + 1] + addition + content[close2 + 1 :]
            else:
                content += addition
        else:
            content += addition

    m_result_cond = re.search(r'if\s*\(\s*!is_android\s*&&\s*!is_ios\s*\)\s*\{', content)
    if not m_result_cond:
        return original_content, False, False
    result_cond_close = MutatorContext.find_matching_char(content, m_result_cond.end() - 1, "{", "}")
    if result_cond_close == -1:
        return original_content, False, False
    result_cond_body = content[m_result_cond.end() : result_cond_close]
    if "external_js.grdp" not in result_cond_body or "opaque_ke.grdp" not in result_cond_body:
        return original_content, False, False

    return content, True, True


def apply(ctx: MutatorContext):
    ctx.mutate_file("ui/webui/resources/BUILD.gn", _patch_webui_resources_build_gn)
    ctx.mutate_file("ui/webui/resources/sources.gni", _patch_webui_sources_gni)
