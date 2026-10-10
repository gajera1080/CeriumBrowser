#!/usr/bin/env bash
# Compatibility wrapper for package.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/package.sh" "$@"
