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
        """void UpdateBraveVpn(const base::FilePath& target_path,
                    const base::Version& new_version,
                    WorkItemList* install_list) {""",
        """void UpdateBraveVpn(const base::FilePath& target_path,
                    const base::Version& new_version,
                    WorkItemList* install_list) {
  // Cerium: Disable VPN NT background service registration
  (void)target_path;
  (void)new_version;
  (void)install_list;
  return;""",
    )

    # Remove promo registry read in mini_installer.cc
    ctx.replace_in_file(
        "chromium_src/chrome/installer/mini_installer/mini_installer.cc",
        re.compile(
            r'const\s+bool\s+result\s*=\s*RegKey::ReadSZValue\([\s\S]*?_countof\(value\)\);\s*\\?'
        ),
        "const bool result = false; (void)value;  /* Cerium: Skip promo registry read */ \\\n  ",
    )
