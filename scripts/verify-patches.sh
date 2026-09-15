#!/usr/bin/env bash
# Braving Dynamic Patch Verification Script
# Verifies that all patches apply cleanly against a specified commit or version.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BRAVE_CORE_DIR="${BRAVE_CORE_DIR:-}"

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
  # Treat as version — extract commit with yaml fallback
  VERSION="${TARGET_ARG#v}"
  METADATA_FILE="${REPO_ROOT}/metadata/upstream-${VERSION}.yaml"
  if [[ ! -f "${METADATA_FILE}" ]]; then
    METADATA_FILE="${REPO_ROOT}/metadata/releases/${VERSION}.yaml"
  fi
  if [[ ! -f "${METADATA_FILE}" ]]; then
    echo "ERROR: Metadata not found for version ${VERSION}: ${METADATA_FILE}" >&2
    exit 1
  fi
  BRAVE_CORE_COMMIT=$(python3 - "${METADATA_FILE}" <<'PYEOF'
import sys
metadata_file = sys.argv[1]
try:
    import yaml
    with open(metadata_file) as f:
        data = yaml.safe_load(f)
    result = (data.get('repositories', {}).get('brave_core', {}).get('commit')
              or data.get('brave_core_commit', ''))
    print(result)
except Exception:
    val = ''
    with open(metadata_file) as f:
        for line in f:
            s = line.strip()
            for key in ('commit:', 'brave_core_commit:'):
                if s.startswith(key):
                    candidate = s[len(key):].strip().strip('"\'')
                    if len(candidate) == 40:
                        val = candidate
                        break
            if val:
                break
    print(val)
PYEOF
)
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

# Write patch list and parameters to temp files for safe passing to Python
PATCH_LIST_FILE=$(mktemp)
for p in "${PATCH_FILES[@]}"; do
  echo "$p" >> "${PATCH_LIST_FILE}"
done

# Run isolated verification in temporary git tree
python3 - "${BRAVE_CORE_COMMIT}" "${BRAVE_CORE_DIR}" "${PATCH_LIST_FILE}" <<'PYEOF'
import subprocess, tempfile, os, sys, urllib.request

target_commit = sys.argv[1]
brave_dir = sys.argv[2]
patch_list_file = sys.argv[3]

with open(patch_list_file) as f:
    patches = [line.strip() for line in f if line.strip()]
os.unlink(patch_list_file)

# Determine if local brave-core is available
use_local = bool(brave_dir) and os.path.isdir(os.path.join(brave_dir, '.git'))

if use_local:
    print(f'\nUsing local brave-core at {brave_dir}')
else:
    print('\nNo local brave-core found, fetching files from GitHub...')

print(f'\nExtracting upstream base files from commit {target_commit[:10]}...')

# Identify all files affected by the patches
affected_files = set()
for p in patches:
    with open(p, 'r') as f:
        for line in f:
            if line.startswith('--- a/') or line.startswith('+++ b/'):
                clean_path = line[6:].strip().split('\t')[0].split(' ')[0]
                if clean_path and clean_path not in ('/dev/null', 'dev/null'):
                    affected_files.add(clean_path)

affected_files = sorted(list(affected_files))
print(f'Detected {len(affected_files)} target file(s) affected across patch set:')
for af in affected_files:
    print(f' - {af}')

def fetch_file_content(filepath):
    """Fetch file content from local git or remote GitHub."""
    if use_local:
        return subprocess.check_output(
            ['git', '-C', brave_dir, 'cat-file', '-p', f'{target_commit}:{filepath}']
        )
    else:
        url = f'https://raw.githubusercontent.com/brave/brave-core/{target_commit}/{filepath}'
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception as e:
            print(f'  WARNING: Could not fetch {filepath}: {e}', file=sys.stderr)
            raise

with tempfile.TemporaryDirectory() as td:
    subprocess.run(['git', 'init', '-q'], cwd=td, check=True)
    subprocess.run(['git', 'config', 'user.email', 'ci@braving.org'], cwd=td, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Braving CI'], cwd=td, check=True)
    subprocess.run(['git', 'config', 'commit.gpgsign', 'false'], cwd=td, check=True)

    for f in affected_files:
        content = fetch_file_content(f)
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
    assert "args.chrome_public_manifest_package = 'org.braving.browser'" in bargs, 'Manifest package replacement missing'
    print(' [PASS] buildArgs.ts specifies org.braving.browser')

    # 2. Check channel constants
    chan_path = os.path.join(td, 'app/theme/brave/android/res_brave_base/values/channel_constants.xml')
    with open(chan_path, 'r') as f:
        chan = f.read()
    assert '<string name="app_name" translatable="false">Braving</string>' in chan, 'App name string replacement missing'
    print(' [PASS] channel_constants.xml specifies Braving')

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
PYEOF
