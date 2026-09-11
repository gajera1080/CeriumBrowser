#!/bin/bash
sed -i 's|# Step 9: Run GN gen|# Configure Siso to store its cache inside the output directory\nexport SISO_LOCAL_CACHE_DIR="${OUT_DIR}/siso_cache"\n\n# Step 9: Run GN gen|g' scripts/build-android.sh

sed -i '/(cd "${BRAVE_DIR}" && pnpm run sync -- --no-history --nohooks)/a \
\n  # Download and extract the Chromium warm cache AFTER the source checkout and patches.\n  if [[ "${CACHE_PREP_ONLY:-false}" != "true" ]]; then\n    echo -e "\\n\\e[32;1m\\$ ./scripts/download-cache.sh\\e[0;m"\n    bash ./scripts/download-cache.sh || true\n  fi' scripts/build-android.sh

sed -i 's|tar -xzf|tar -xzmf|g' scripts/download-cache.sh
