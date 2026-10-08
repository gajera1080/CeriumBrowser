#!/usr/bin/env python3
import os
import sys

common_script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "common", "resolve-versions.py")
os.execv(sys.executable, [sys.executable, common_script] + sys.argv[1:])
