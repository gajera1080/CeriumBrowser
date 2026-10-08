"""
Brave Origin Branding & Desktop Configuration Mutator (scripts/mutators/common/brave_origin.py)
Rebrands app/theme/brave_origin/BRANDING (and beta/development/nightly variants) to Braving.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    branding_variants = [
        ("app/theme/brave_origin/BRANDING", "Braving Browser", "Braving"),
        ("app/theme/brave_origin/BRANDING.beta", "Braving Browser Beta", "Braving Beta"),
        ("app/theme/brave_origin/BRANDING.development", "Braving Browser Development", "Braving Development"),
        ("app/theme/brave_origin/BRANDING.nightly", "Braving Browser Nightly", "Braving Nightly"),
    ]

    for rel_path, full_name, short_name in branding_variants:
        ctx.replace_in_file(
            rel_path,
            "COMPANY_FULLNAME=Brave Software, Inc.",
            "COMPANY_FULLNAME=Braving Project",
            check_token="COMPANY_FULLNAME=Braving Project",
        )
        ctx.replace_in_file(
            rel_path,
            "COMPANY_SHORTNAME=Brave Software",
            "COMPANY_SHORTNAME=Braving",
            check_token="COMPANY_SHORTNAME=Braving",
        )

        def make_mutator(fname, sname):
            def mutate_branding(content: str):
                lines = []
                found = False
                for line in content.splitlines(keepends=True):
                    if line.startswith("PRODUCT_FULLNAME="):
                        lines.append(f"PRODUCT_FULLNAME={fname}\n")
                        found = True
                    elif line.startswith("PRODUCT_SHORTNAME="):
                        lines.append(f"PRODUCT_SHORTNAME={sname}\n")
                        found = True
                    elif line.startswith("PRODUCT_INSTALLER_FULLNAME="):
                        lines.append("PRODUCT_INSTALLER_FULLNAME=Braving Installer\n")
                        found = True
                    elif line.startswith("PRODUCT_INSTALLER_SHORTNAME="):
                        lines.append("PRODUCT_INSTALLER_SHORTNAME=Braving Installer\n")
                        found = True
                    else:
                        lines.append(line)
                new_content = "".join(lines)
                return new_content, new_content != content, found
            return mutate_branding

        ctx.mutate_file(rel_path, make_mutator(full_name, short_name))
