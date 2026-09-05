#!/usr/bin/env bash
# Braving Comprehensive Patch Verification Script
# Verifies that all patches in patches/ apply cleanly and deterministically
# against the exact upstream brave-core release commit without modifying working trees.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BRAVE_CORE_DIR="${BRAVE_CORE_DIR:-/run/media/pc/D/brave-core}"

BRAVE_VERSION="${1:-1.94.120}"
METADATA_FILE="${REPO_ROOT}/metadata/upstream-${BRAVE_VERSION}.yaml"

if [[ ! -f "${METADATA_FILE}" ]]; then
  echo "ERROR: Upstream metadata not found: ${METADATA_FILE}" >&2
  exit 1
fi

echo "========================================================"
echo " Braving Patch Set Verification"
echo " Target Version: ${BRAVE_VERSION}"
echo "========================================================"

BRAVE_CORE_COMMIT=$(python3 -c "
import yaml
with open('${METADATA_FILE}') as f:
    data = yaml.safe_load(f)
print(data['repositories']['brave_core']['commit'])
")

echo "Target brave-core commit: ${BRAVE_CORE_COMMIT}"

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
        # Check first
        chk = subprocess.run(['git', 'apply', '--check', p], cwd=td, capture_output=True, text=True)
        if chk.returncode != 0:
            print(f' [FAIL] git apply --check failed for {pname}:', file=sys.stderr)
            print(chk.stderr, file=sys.stderr)
            sys.exit(1)

        # Apply
        app = subprocess.run(['git', 'apply', p], cwd=td, capture_output=True, text=True)
        if app.returncode != 0:
            print(f' [FAIL] git apply failed for {pname}:', file=sys.stderr)
            print(app.stderr, file=sys.stderr)
            sys.exit(1)

        subprocess.run(['git', 'add', '.'], cwd=td, check=True)
        subprocess.run(['git', 'commit', '-q', '-m', f'apply {pname}'], cwd=td, check=True)
        print(f' [PASS] {pname}')

    print('\nVerifying resulting files:')
    # Check manifest package
    build_args_path = os.path.join(td, 'build/commands/lib/buildArgs.ts')
    with open(build_args_path, 'r') as f:
        bargs = f.read()
    assert 'args.chrome_public_manifest_package = \'org.braving.browser\'' in bargs, 'Manifest package replacement missing'
    print(' [PASS] buildArgs.ts specifies org.braving.browser')

    # Check channel constants
    chan_path = os.path.join(td, 'app/theme/brave/android/res_brave_base/values/channel_constants.xml')
    with open(chan_path, 'r') as f:
        chan = f.read()
    assert '<string name=\"app_name\" translatable=\"false\">Braving</string>' in chan, 'App name string replacement missing'
    print(' [PASS] channel_constants.xml specifies Braving')

    # Check GN defaults
    defaults_path = os.path.join(td, 'build/args/android_defaults.gni')
    with open(defaults_path, 'r') as f:
        defs = f.read()
    assert 'enable_brave_wallet = false' in defs, 'Wallet disabling missing'
    assert 'enable_brave_vpn = false' in defs, 'VPN disabling missing'
    print(' [PASS] android_defaults.gni disables bloat features')

    # Check Play deps
    config_path = os.path.join(td, 'build/android/config.gni')
    with open(config_path, 'r') as f:
        cfg = f.read()
    assert 'enable_play_services = false' in cfg, 'Play services flag missing'
    assert 'if (enable_play_services)' in cfg, 'Play services gating missing'
    print(' [PASS] config.gni gates proprietary Play dependencies')

print('\n========================================================')
print(' ALL PATCHES VERIFIED CLEAN & DETERMINISTIC')
print('========================================================')
"
