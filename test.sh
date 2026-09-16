#!/bin/bash
set -euo pipefail
set +e
(cd /tmp && (exit 1) 2>&1 | tee /tmp/log | awk '{print $0}')
BUILD_RES=${PIPESTATUS[0]}
set -e
echo "BUILD_RES: $BUILD_RES"
