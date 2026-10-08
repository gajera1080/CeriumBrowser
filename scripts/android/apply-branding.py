#!/usr/bin/env python3
"""
Braving — String & Localization Mutator Forwarder
Forwards to the canonical cross-platform script in scripts/common/apply-branding.py.
"""

import importlib.util
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COMMON_SCRIPT = os.path.join(os.path.dirname(SCRIPT_DIR), "common", "apply-branding.py")

spec = importlib.util.spec_from_file_location("_common_branding", COMMON_SCRIPT)
_common = importlib.util.module_from_spec(spec)
sys.modules["_common_branding"] = _common
spec.loader.exec_module(_common)

# Re-export all public symbols for backwards compatibility with tests and callers
for attr in dir(_common):
    if not attr.startswith("__"):
        globals()[attr] = getattr(_common, attr)

if __name__ == "__main__":
    import subprocess
    result = subprocess.run([sys.executable, COMMON_SCRIPT] + sys.argv[1:])
    sys.exit(result.returncode)
