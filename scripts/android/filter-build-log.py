#!/usr/bin/env python3
"""
Braving Build Stream Filter
Prevents GitLab CI log truncation (4MB limit) while preserving all progress,
errors, warnings, and failure diagnostics in real-time.

Usage:
  autoninja -C out/Release chrome_public_apk 2>&1 | python3 -u filter-build-log.py <path_to_build.log> [step_interval]
"""

import os
import re
import sys

def main():
    log_path = sys.argv[1] if len(sys.argv) > 1 else "build.log"
    step_interval = int(sys.argv[2]) if len(sys.argv) > 2 else 50

    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    progress_pattern = re.compile(r"^\[\s*(\d+)/(\d+)\]\s*(.*)$")

    last_step = 0
    total_steps = 0

    # Ensure stdout line buffering
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    with open(log_path, "w", encoding="utf-8", errors="replace") as f_out:
        for line in sys.stdin:
            # 1. Write 100% of raw output to the persistent build.log
            f_out.write(line)
            f_out.flush()

            # 2. Check if this is a standard ninja/siso step progress line
            m = progress_pattern.match(line)
            if m:
                current = int(m.group(1))
                total = int(m.group(2))
                last_step = current
                total_steps = total

                # Throttle progress lines: first step, every Nth step, and final step
                if current == 1 or current % step_interval == 0 or current == total:
                    pct = (current * 100.0) / total if total > 0 else 0.0
                    action_summary = m.group(3)
                    sys.stdout.write(f"[{current}/{total} ({pct:.1f}%)] {action_summary}\n")
                    sys.stdout.flush()
            else:
                # Always forward any non-progress lines immediately to stdout:
                # Compiler errors, warnings, Dart Sass notices, tracebacks, diagnostics, FAILED blocks
                sys.stdout.write(line)
                sys.stdout.flush()

        if total_steps > 0:
            sys.stdout.write(f"\n[Build Stream Completed: {last_step}/{total_steps} steps processed]\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
