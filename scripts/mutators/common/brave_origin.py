"""
Brave Origin Branding & Desktop Configuration Mutator (scripts/mutators/common/brave_origin.py)
Rebrands app/theme/brave_origin/BRANDING (and beta/development/nightly variants) to Cerium.
"""

from scripts.mutators.context import MutatorContext


def apply(ctx: MutatorContext):
    branding_variants = [
        ("app/theme/brave_origin/BRANDING", "Cerium Browser", "Cerium"),
        ("app/theme/brave_origin/BRANDING.beta", "Cerium Browser Beta", "Cerium Beta"),
        ("app/theme/brave_origin/BRANDING.development", "Cerium Browser Development", "Cerium Development"),
        ("app/theme/brave_origin/BRANDING.nightly", "Cerium Browser Nightly", "Cerium Nightly"),
    ]

    for rel_path, full_name, short_name in branding_variants:
        def make_mutator(fname, sname):
            def mutate_branding(content: str):
                lines = []
                for line in content.splitlines(keepends=True):
                    if line.startswith("COMPANY_FULLNAME="):
                        lines.append("COMPANY_FULLNAME=Cerium Browser Team\n")
                    elif line.startswith("COMPANY_SHORTNAME="):
                        lines.append("COMPANY_SHORTNAME=Cerium\n")
                    elif line.startswith("PRODUCT_FULLNAME="):
                        lines.append(f"PRODUCT_FULLNAME={fname}\n")
                    elif line.startswith("PRODUCT_SHORTNAME="):
                        lines.append(f"PRODUCT_SHORTNAME={sname}\n")
                    elif line.startswith("PRODUCT_INSTALLER_FULLNAME="):
                        lines.append("PRODUCT_INSTALLER_FULLNAME=Cerium Installer\n")
                    elif line.startswith("PRODUCT_INSTALLER_SHORTNAME="):
                        lines.append("PRODUCT_INSTALLER_SHORTNAME=Cerium Installer\n")
                    else:
                        lines.append(line)
                new_content = "".join(lines)
                is_modified = new_content != content
                has_target = "COMPANY_FULLNAME=Cerium Browser Team" in new_content
                return new_content, is_modified, has_target
            return mutate_branding

        ctx.mutate_file(rel_path, make_mutator(full_name, short_name))
