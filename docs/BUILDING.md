# Building Cerium Browser

This guide describes how to build Cerium Browser from source in a clean environment.

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
export CERIUM_DIR="${WORKSPACE_DIR}/Cerium"
export BRAVING_DIR="${CERIUM_DIR}"
export SRC_DIR="${WORKSPACE_DIR}/src"
```

Clone the Cerium repository:
```bash
git clone https://gitlab.com/CeriumBrowser/Cerium-Browser.git "${CERIUM_DIR}"
```

---

## 3. Version Selection & Source Preparation (Phase 1)

Select the target Brave version or omit to resolve latest upstream stable automatically:

```bash
cd "${CERIUM_DIR}"
./scripts/core/prepare-source.sh
# Or specify a target version:
# ./scripts/core/prepare-source.sh <version>
```

What `prepare-source.sh` performs:
1. Dynamically resolves latest stable Brave version from GitHub API and Google Gitiles.
2. Generates `metadata/upstream-<version>.yaml` and release manifest at `metadata/releases/<version>.yaml`, exporting environment to `build.env`.
3. Fetches `brave-core` at exact release commit (`--depth 1` zero-history clone/checkout).
4. Applies Cerium unified patches (`patches/common/` and platform patches) via `apply-patches.sh`.
5. Verifies patch set integrity (`apply-patches.sh --check`) ensuring all patches apply cleanly.
6. Executes programmatic Python mutators and Cerium branding overlays (`apply-features.py`, `apply-assets.sh`, `apply-branding.py`).
7. Packages the prepared source into a compressed tarball (`build-workspace/brave-src-<version>.tar.gz`) for GitLab pipeline cache transfer.

---

## 4. Android Compilation (Phase 2)

Once the source is prepared, trigger the Android build:

```bash
cd "${CERIUM_DIR}"
./scripts/platforms/android/build.sh --arch=arm64 --release
```

### Build Arguments Configured by Cerium:
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
${CERIUM_DIR}/out/apks/Cerium-<version>-arm64.apk
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

