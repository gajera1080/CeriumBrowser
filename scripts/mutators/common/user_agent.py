"""
User Agent & Client Hints Mutator (scripts/mutators/common/user_agent.py)
Ensures Client Hints and User-Agent always identify as standard modern Chrome
across all websites, removing Brave brand leakage and version freezing.
"""

import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    ctx.replace_in_file(
        "chromium_src/components/embedder_support/user_agent_utils.cc",
        re.compile(r"constexpr\s+char\s+kBraveBrandNameForCHUA\[\]\s*=\s*\"Brave\";"),
        '[[maybe_unused]] constexpr char kBraveBrandNameForCHUA[] = "Brave";',
        check_token='[[maybe_unused]] constexpr char kBraveBrandNameForCHUA'
    )

    ctx.replace_in_file(
        "chromium_src/components/embedder_support/user_agent_utils.cc",
        re.compile(
            r"#define\s+BRAVE_GET_USER_AGENT_BRAND_LIST\s+brand\s*=\s*(?:kBraveBrandNameForCHUA|\"Google Chrome\");(?:\s*\(void\)kBraveBrandNameForCHUA;)?"
        ),
        '#define BRAVE_GET_USER_AGENT_BRAND_LIST brand = "Google Chrome"; (void)kBraveBrandNameForCHUA;',
        check_token='brand = "Google Chrome"; (void)kBraveBrandNameForCHUA;'
    )

    ctx.replace_in_file(
        "chromium_src/components/embedder_support/user_agent_utils.cc",
        re.compile(
            r"#define\s+BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE\s*\\\s*\n\s*"
            r"base::StrCat\(\s*\{\s*major_version\s*,\s*\"\.0\.0\.0\"\s*\}\s*\)"
        ),
        "#define BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE full_version",
        check_token="#define BRAVE_BRAND_VERSION_OVERRIDE_FOR_FULL_BRAND_VERSION_TYPE full_version"
    )

    # Preserve full version fidelity in UserAgentMetadata instead of zeroing out last 3 version components
    ctx.replace_in_file(
        "browser/brave_content_browser_client.cc",
        re.compile(
            r"blink::UserAgentMetadata\s+BraveContentBrowserClient::GetUserAgentMetadata\(\)\s*\{[\s\S]*?"
            r"metadata\.full_version\s*=\s*base::StrCat\([\s\S]*?\);\s*"
            r"return\s+metadata;\s*\}"
        ),
        """blink::UserAgentMetadata BraveContentBrowserClient::GetUserAgentMetadata() {
  // Braving: Return standard Chromium / Chrome UserAgentMetadata with full version fidelity
  return ChromeContentBrowserClient::GetUserAgentMetadata();
}""",
        check_token="// Braving: Return standard Chromium / Chrome UserAgentMetadata with full version fidelity"
    )

    # Always hide Brave brand across all domains so Braving consistently identifies as Chrome
    ctx.replace_in_file(
        "components/brave_user_agent/browser/brave_user_agent_exceptions.cc",
        re.compile(
            r"bool\s+BraveUserAgentExceptions::CanShowBrave\s*\(\s*const\s+GURL&\s*url\s*\)\s*\{[\s\S]*?"
            r"return\s+!excepted_domains_\.contains\(domain\);\s*\}"
        ),
        """bool BraveUserAgentExceptions::CanShowBrave(const GURL& url) {
  // Braving: Never show Brave brand; always identify as standard Chrome
  (void)url;
  return false;
}""",
        check_token="// Braving: Never show Brave brand; always identify as standard Chrome"
    )

    ctx.replace_in_file(
        "components/brave_user_agent/browser/brave_user_agent_exceptions.cc",
        re.compile(
            r"bool\s+ShouldHideBraveBrand\s*\(\s*const\s+GURL&\s*url\s*\)\s*\{[\s\S]*?"
            r"return\s+exceptions\s*&&\s*!exceptions->CanShowBrave\(url\);\s*\}"
        ),
        """bool ShouldHideBraveBrand(const GURL& url) {
  // Braving: Always hide Brave brand across all domains
  (void)url;
  return true;
}""",
        check_token="// Braving: Always hide Brave brand across all domains"
    )

    # Ensure reduced user agent resolves full Chromium major milestone instead of Brave's "1"
    ctx.replace_in_src(
        "components/version_info/version_info_with_user_agent.cc",
        re.compile(
            r"std::string\s+GetProductNameAndVersionForReducedUserAgent\(\)\s*\{[\s\S]*?"
            r"return\s+base::StrCat\(\s*\{\s*\"Chrome/\"\s*,\s*GetMajorVersionNumber\(\)\s*,\s*\"\.0\.0\.0\"\s*\}\s*\);\s*"
            r"\}"
        ),
        """std::string GetProductNameAndVersionForReducedUserAgent() {
  std::string major = GetMajorVersionNumber();
#if defined(BRAVE_CHROMIUM_VERSION)
  if (major == "1") {
    std::string_view cr_ver = BRAVE_CHROMIUM_VERSION;
    size_t dot_pos = cr_ver.find('.');
    if (dot_pos != std::string_view::npos) {
      major = std::string(cr_ver.substr(0, dot_pos));
    }
  }
#endif
  return base::StrCat({"Chrome/", major, ".0.0.0"});
}""",
        check_token="BRAVE_CHROMIUM_VERSION"
    )
