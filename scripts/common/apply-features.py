#!/usr/bin/env python3
"""
Braving — GN Build Fix Mutators Runner (Cross-Platform)
Delegates to the modular component-based mutator engine in scripts/mutators/.
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.mutators.runner import run_mutators

if __name__ == "__main__":
    sys.exit(run_mutators(sys.argv[1:]))
