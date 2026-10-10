"""
Windows Desktop Branding & Identity Mutator
(scripts/mutators/platforms/windows/branding.py)
Remaps company path, product path, app name, and ProgIDs in
chromium_install_modes.h and brave_shell_util.cc to Cerium.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    # 1. Update company, product paths, and install modes in chromium_install_modes.h
    def mutate_install_modes(content: str):
        replacements = [
            ('inline constexpr wchar_t kCompanyPathName[] = L"BraveSoftware";',
             'inline constexpr wchar_t kCompanyPathName[] = L"Cerium";'),
            ('inline constexpr wchar_t kProductPathName[] = L"Brave-Origin";',
             'inline constexpr wchar_t kProductPathName[] = L"Cerium-Browser";'),
            ('inline constexpr wchar_t kProductPathName[] = L"Brave-Browser";',
             'inline constexpr wchar_t kProductPathName[] = L"Cerium-Browser";'),
            ('inline constexpr wchar_t kProductPathName[] = L"Brave-Browser-Development";',
             'inline constexpr wchar_t kProductPathName[] = L"Cerium-Development";'),
            ('.base_app_name = L"Brave Origin"', '.base_app_name = L"Cerium"'),
            ('.base_app_id = L"BraveOrigin"', '.base_app_id = L"Cerium"'),
            ('.browser_prog_id_prefix = L"BraveOHTML"', '.browser_prog_id_prefix = L"CeriumHTML"'),
            ('.browser_prog_id_description =\n            L"Brave Origin HTML Document"',
             '.browser_prog_id_description =\n            L"Cerium HTML Document"'),
            ('.pdf_prog_id_prefix = L"BraveOPDF"', '.pdf_prog_id_prefix = L"CeriumPDF"'),
            ('.pdf_prog_id_description =\n            L"Brave Origin PDF Document"',
             '.pdf_prog_id_description =\n            L"Cerium PDF Document"'),
            ('.base_app_name = L"Brave"', '.base_app_name = L"Cerium"'),
            ('.base_app_id = L"Brave"', '.base_app_id = L"Cerium"'),
            ('.browser_prog_id_prefix = L"BraveHTML"', '.browser_prog_id_prefix = L"CeriumHTML"'),
            ('.browser_prog_id_description =\n            L"Brave HTML Document"',
             '.browser_prog_id_description =\n            L"Cerium HTML Document"'),
            ('.pdf_prog_id_prefix = L"BravePDF"', '.pdf_prog_id_prefix = L"CeriumPDF"'),
            ('.pdf_prog_id_description =\n            L"Brave PDF Document"',
             '.pdf_prog_id_description =\n            L"Cerium PDF Document"'),
        ]
        modified = False
        new_content = content
        for old, new in replacements:
            if old in new_content:
                new_content = new_content.replace(old, new)
                modified = True
        found = modified or ('inline constexpr wchar_t kCompanyPathName[] = L"Cerium";' in content)
        return new_content, modified, found

    ctx.mutate_file(
        "chromium_src/chrome/install_static/chromium_install_modes.h",
        mutate_install_modes,
    )

    # 2. File type ProgIDs in brave_shell_util.cc
    def mutate_shell_util(content: str):
        replacements = [
            ('return L"BraveFile";', 'return L"CeriumFile";'),
            ('return L"BraveBFile";', 'return L"CeriumBFile";'),
            ('return L"BraveDFile";', 'return L"CeriumDFile";'),
            ('return L"BraveSSFile";', 'return L"CeriumSSFile";'),
        ]
        modified = False
        new_content = content
        for old, new in replacements:
            if old in new_content:
                new_content = new_content.replace(old, new)
                modified = True
        found = modified or ('return L"CeriumFile";' in content)
        return new_content, modified, found

    ctx.mutate_file(
        "installer/util/brave_shell_util.cc",
        mutate_shell_util,
    )
