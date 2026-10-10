"""
Windows Background Services & Installer Debloating Mutator
(scripts/mutators/platforms/windows/installer.py)
Neutralizes UpdateBraveVpn in install_worker.cc to prevent registering
Windows NT services (VPN helper and Wireguard services), and removes
the promo registry key lookup in mini_installer.cc.
"""

import re
from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    # Neutralize UpdateBraveVpn in install_worker.cc
    ctx.replace_in_file(
        "chromium_src/chrome/installer/setup/install_worker.cc",
        re.compile(
            r"void\s+UpdateBraveVpn\s*\(\s*const\s+base::FilePath&\s*target_path,\s*\n"
            r"\s*const\s+base::Version&\s*new_version,\s*\n"
            r"\s*WorkItemList\*\s*install_list\s*\)\s*\{[\s\S]*?"
            r"OneTimeVpnServiceCleanup[\s\S]*?\n\}"
        ),
        """void UpdateBraveVpn(const base::FilePath& target_path,
                    const base::Version& new_version,
                    WorkItemList* install_list) {
  // Cerium: Disable VPN NT background service registration
  (void)target_path;
  (void)new_version;
  (void)install_list;
  return;
}""",
        check_token="// Cerium: Disable VPN NT background service registration",
    )

    # Remove promo registry read in mini_installer.cc
    ctx.replace_in_file(
        "chromium_src/chrome/installer/mini_installer/mini_installer.cc",
        re.compile(
            r"const\s+bool\s+result\s*=\s*RegKey::ReadSZValue\(\s*(?:\\\s*)?\n"
            r"\s*HKEY_CURRENT_USER,\s*L\"Software\\\\BraveSoftware\\\\Promo\",\s*(?:\\\s*)?\n"
            r"\s*L\"StubInstallerPath\",\s*value,\s*_countof\(value\)\);\s*(?:\\)?"
        ),
        "const bool result = false; (void)value;  /* Cerium: Skip promo registry read */ \\\n  ",
        check_token="/* Cerium: Skip promo registry read */",
    )
