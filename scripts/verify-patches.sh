#!/usr/bin/env bash
# Braving Dynamic Patch Verification Script
# Verifies that all patches apply cleanly against a specified commit or version.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BRAVE_CORE_DIR="${BRAVE_CORE_DIR:-/run/media/pc/D/brave-core}"

TARGET_ARG="${1:-}"

# Auto-detect target if not supplied
if [[ -z "${TARGET_ARG}" ]]; then
  LATEST_META=$(ls -t "${REPO_ROOT}/metadata/upstream-"*.yaml 2>/dev/null | head -n 1 || true)
  if [[ -n "${LATEST_META}" ]]; then
    TARGET_ARG=$(basename "${LATEST_META}" | sed 's/upstream-//;s/\.yaml//')
  else
    echo "ERROR: Target commit or version required." >&2
    exit 1
  fi
fi

if [[ "${TARGET_ARG}" =~ ^[0-9a-fA-F]{40}$ ]]; then
  BRAVE_CORE_COMMIT="${TARGET_ARG}"
  echo "Targeting explicit brave-core commit: ${BRAVE_CORE_COMMIT}"
else
  # Treat as version
  VERSION="${TARGET_ARG#v}"
  METADATA_FILE="${REPO_ROOT}/metadata/upstream-${VERSION}.yaml"
  if [[ ! -f "${METADATA_FILE}" ]]; then
    METADATA_FILE="${REPO_ROOT}/metadata/releases/${VERSION}.yaml"
  fi
  if [[ ! -f "${METADATA_FILE}" ]]; then
    echo "ERROR: Metadata not found for version ${VERSION}: ${METADATA_FILE}" >&2
    exit 1
  fi
  BRAVE_CORE_COMMIT=$(python3 -c "
import yaml
with open('${METADATA_FILE}') as f:
    data = yaml.safe_load(f)
print(data.get('repositories', {}).get('brave_core', {}).get('commit') or data.get('brave_core_commit', ''))
")
fi

echo "========================================================"
echo " Braving Patch Set Verification"
echo " Target brave-core commit: ${BRAVE_CORE_COMMIT}"
echo "========================================================"

# Collect all patch files in order
PATCH_FILES=()
while IFS= read -r -d $'\0' file; do
  PATCH_FILES+=("$file")
done < <(find "${REPO_ROOT}/patches" -name "*.patch" -print0 | sort -z)

if [[ ${#PATCH_FILES[@]} -eq 0 ]]; then
  echo "ERROR: No patch files found in ${REPO_ROOT}/patches" >&2
  exit 1
fi

echo "Discovered ${#PATCH_FILES[@]} patch(es):"
for p in "${PATCH_FILES[@]}"; do
  echo " - $(realpath --relative-to="${REPO_ROOT}" "$p")"
done

# Run isolated verification in temporary git tree
python3 -c "
import subprocess, tempfile, os, sys

target_commit = '${BRAVE_CORE_COMMIT}'
brave_dir = '${BRAVE_CORE_DIR}'
patches = [
$(for p in "${PATCH_FILES[@]}"; do echo "    '$p',"; done)
]

print('\nExtracting upstream base files from commit ' + target_commit[:10] + '...')

# Identify all files affected by the patches
affected_files = set()
for p in patches:
    with open(p, 'r') as f:
        for line in f:
            if line.startswith('--- a/'):
                affected_files.add(line.strip()[6:])
            elif line.startswith('+++ b/'):
                affected_files.add(line.strip()[6:])

affected_files = sorted(list(affected_files))
print(f'Detected {len(affected_files)} target file(s) affected across patch set:')
for af in affected_files:
    print(f' - {af}')

with tempfile.TemporaryDirectory() as td:
    subprocess.run(['git', 'init', '-q'], cwd=td, check=True)
    subprocess.run(['git', 'config', 'user.email', 'ci@braving.org'], cwd=td, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Braving CI'], cwd=td, check=True)

    for f in affected_files:
        content = subprocess.check_output(['git', '-C', brave_dir, 'cat-file', '-p', f'{target_commit}:{f}'])
        dst = os.path.join(td, f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as out:
            out.write(content)

    subprocess.run(['git', 'add', '.'], cwd=td, check=True)
    subprocess.run(['git', 'commit', '-q', '-m', 'upstream base'], cwd=td, check=True)

    print('\nApplying patches sequentially:')
    for p in patches:
        pname = os.path.basename(p)
        chk = subprocess.run(['git', 'apply', '--check', p], cwd=td, capture_output=True, text=True)
        if chk.returncode != 0:
            print(f' [FAIL] git apply --check failed for {pname}:', file=sys.stderr)
            print(chk.stderr, file=sys.stderr)
            sys.exit(1)

        app = subprocess.run(['git', 'apply', p], cwd=td, capture_output=True, text=True)
        if app.returncode != 0:
            print(f' [FAIL] git apply failed for {pname}:', file=sys.stderr)
            print(app.stderr, file=sys.stderr)
            sys.exit(1)

        subprocess.run(['git', 'add', '.'], cwd=td, check=True)
        subprocess.run(['git', 'commit', '-q', '-m', f'apply {pname}'], cwd=td, check=True)
        print(f' [PASS] {pname}')

    print('\nVerifying resulting files:')
    # 1. Check manifest package
    build_args_path = os.path.join(td, 'build/commands/lib/buildArgs.ts')
    with open(build_args_path, 'r') as f:
        bargs = f.read()
    assert 'args.chrome_public_manifest_package = \'org.braving.browser\'' in bargs, 'Manifest package replacement missing'
    print(' [PASS] buildArgs.ts specifies org.braving.browser')

    # 2. Check channel constants
    chan_path = os.path.join(td, 'app/theme/brave/android/res_brave_base/values/channel_constants.xml')
    with open(chan_path, 'r') as f:
        chan = f.read()
    assert '<string name=\"app_name\" translatable=\"false\">Braving</string>' in chan, 'App name string replacement missing'
    print(' [PASS] channel_constants.xml specifies Braving')

    # 3. Check GN defaults
    defaults_path = os.path.join(td, 'build/args/android_defaults.gni')
    with open(defaults_path, 'r') as f:
        defs = f.read()
    assert 'enable_brave_wallet = false' in defs, 'Wallet disabling missing'
    assert 'enable_brave_vpn = false' in defs, 'VPN disabling missing'
    assert 'enable_ai_chat = false' in defs, 'AI chat disabling missing'
    assert 'enable_brave_stats_updater = false' in defs, 'Stats updater disabling missing'
    assert 'enable_web_discovery = false' in defs, 'Web discovery disabling missing'
    print(' [PASS] android_defaults.gni disables bloat & telemetry features')

    # 4. Check Telemetry & P3A removal
    p3a_path = os.path.join(td, 'components/p3a/p3a_service.cc')
    with open(p3a_path, 'r') as f:
        p3a_c = f.read()
    assert 'registry->RegisterBooleanPref(kP3AEnabled, false);' in p3a_c, 'P3A default false missing'
    assert 'registry->RegisterBooleanPref(kP3ANoticeAcknowledged, true);' in p3a_c, 'P3A notice acknowledged missing'
    print(' [PASS] p3a_service.cc disables P3A analytics')

    metrics_path = os.path.join(td, 'browser/metrics/metrics_reporting_util.cc')
    with open(metrics_path, 'r') as f:
        met_c = f.read()
    assert 'bool GetDefaultPrefValueForMetricsReporting() {\n  return false;\n}' in met_c, 'Metrics default false missing'
    print(' [PASS] metrics_reporting_util.cc defaults reporting to false')

print('\n========================================================')
print(' ALL PATCHES VERIFIED CLEAN & DETERMINISTIC')
print('========================================================')
"
