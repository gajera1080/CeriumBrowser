#!/bin/bash
set -euo pipefail

set +e
( exit 1 | tee log | awk '{print $0}' )
BUILD_RES=${PIPESTATUS[0]}
set -e

if [[ ${BUILD_RES} -ne 0 ]]; then
  echo "FAILURE BLOCK EXECUTED. BUILD_RES=${BUILD_RES}"
else
  echo "SUCCESS BLOCK EXECUTED. BUILD_RES=${BUILD_RES}"
fi
