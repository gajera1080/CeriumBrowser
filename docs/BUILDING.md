# Building Braving Android

This guide describes how to build Braving Android from source in a clean environment.

---

## 1. System Requirements & Prerequisites

### Hardware
- **Operating System**: Linux (Ubuntu 22.04 / 24.04 or Debian 12 recommended)
- **RAM**: Minimum 32 GB (64 GB strongly recommended for parallel linking)
- **Disk Space**: At least 150 GB of free space on a fast SSD (ext4/btrfs)
- **CPU**: Multi-core (8+ cores / 16+ threads recommended)

### Software & Toolchains
- `git` (2.35+)
- `python3` (3.10+) and `python3-yaml`
- `node` (>= 24.16.0) and `pnpm` (>= 11.11.0)
- `openjdk-17-jdk`
- `curl`, `patch`, `ninja-build`

---

## 2. Environment Setup

Set up a dedicated Chromium / Brave project directory:

```bash
export WORKSPACE_DIR="/run/media/pc/D"
export BRAVING_DIR="${WORKSPACE_DIR}/Braving"
export SRC_DIR="${WORKSPACE_DIR}/src"
```

Clone the Braving repository:
```bash
git clone https://gitlab.com/braving/braving-browser.git "${BRAVING_DIR}"
```

---

## 3. Version Selection & Source Preparation (Phase 1)

Select the target Brave version or omit to resolve latest upstream stable automatically:

```bash
cd "${BRAVING_DIR}"
./scripts/core/prepare-source.sh
# Or specify a target version:
# ./scripts/core/prepare-source.sh <version>
```

What `prepare-source.sh` performs:
1. Dynamically resolves latest stable Brave version from GitHub API and Google Gitiles.
2. Generates `metadata/upstream-<version>.yaml` and release manifest at `metadata/releases/<version>.yaml`.
3. Fetches `brave-core` at exact release commit (`--depth 1`).
4. Applies Braving unified patches (`patches/common/` and platform patches).
5. Executes programmatic Python mutators (`apply-features.py`, `apply-assets.sh`, `apply-branding.py`).

---

## 4. Android Compilation (Phase 2)

Once the source is prepared, trigger the Android build:

```bash
cd "${BRAVING_DIR}"
./scripts/platforms/android/build.sh --arch=arm64 --release
```

### Build Arguments Configured by Braving:
```gn
target_os = "android"
target_cpu = "arm64"
is_debug = false
is_official_build = true
is_java_debug = false
symbol_level = 0
blink_symbol_level = 0
v8_symbol_level = 0
enable_resource_allowlist_generation = true
is_component_build = false
disable_fieldtrial_testing_config = true
chrome_public_manifest_package = "org.cerium.browser"
android_channel = "stable"
brave_channel = ""
target_android_output_format = "aab"
enable_android_secondary_abi = false
skip_secondary_abi_for_cq = true
dcheck_always_on = false
enable_java_asserts = false
exclude_unwind_tables = true
use_siso = true
disable_android_lint = true
```

The resulting signed APK will be placed in:
```
${BRAVING_DIR}/out/apks/Cerium-<version>-arm64.apk
```

---

## 5. Master Verification Suite

Run all verification tiers:
```bash
./scripts/core/verify-all.sh
```

---

## 6. Standalone APK Release Signing

To sign an existing or newly compiled APK using release credentials:
```bash
./scripts/platforms/android/package.sh --apk="out/apks/Cerium-<version>-arm64.apk"
```

---

## 7. Troubleshooting

- **Out of Memory during linking**:
  `args.gn` already configures `symbol_level = 0` to minimize linker memory pressure.
- **GitLab CI 4MB log truncation**:
  `build-android.sh` automatically routes compilation stdout through `filter-build-log.py`, throttling step progress while passing 100% of compiler errors and warnings unbuffered.

