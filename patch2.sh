#!/bin/bash
sed -i '/(cd "${WORKSPACE_DIR}" && gclient sync --no-history --shallow --nohooks -j16)/a \
\n# Download and extract the Chromium warm cache AFTER the source checkout and patches.\nif [[ "${CACHE_PREP_ONLY:-false}" != "true" ]]; then\n  echo -e "\\n\\e[32;1m\\$ ./scripts/download-cache.sh\\e[0;m"\n  bash ./scripts/download-cache.sh || true\nfi' scripts/build-android.sh
