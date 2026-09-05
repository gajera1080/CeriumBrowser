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
git clone https://gitlab.com/braving/braving.git "${BRAVING_DIR}"
```

---

## 3. Version Selection & Source Preparation (Phase 1)

Select the target Brave version (e.g. `1.94.120`):

```bash
cd "${BRAVING_DIR}"
./scripts/prepare-source.sh 1.94.120
```

What `prepare-source.sh` performs:
1. Validates `metadata/upstream-1.94.120.yaml`.
2. Resolves exact brave-core tag (`v1.94.120`) and commit (`449b91b1c032bd6c94aacd054757a97e128635b5`).
3. Resolves exact Chromium revision (`152.0.7977.76` / `0d89dfa2dd7c1ec4b8a14b9f303f887bb63b6174`).
4. Applies Braving patches sequentially and checks clean application.
5. Generates the release manifest at `metadata/releases/1.94.120.yaml`.

---

## 4. Android Compilation (Phase 2)

Once the source is prepared, trigger the Android build:

```bash
cd "${BRAVING_DIR}"
./scripts/build-android.sh --manifest="metadata/releases/1.94.120.yaml" --arch=arm64 --release
```

### Build Arguments Configured by Braving:
```gn
target_os = "android"
target_cpu = "arm64"
is_debug = false
is_official_build = true
is_component_build = false
symbol_level = 0
disable_fieldtrial_testing_config = true
chrome_public_manifest_package = "org.braving.browser"
enable_brave_wallet = false
enable_brave_rewards = false
enable_brave_ads = false
enable_brave_vpn = false
enable_ai_chat = false
enable_brave_news = false
enable_play_services = false
```

The resulting APK will be placed in:
```
${BRAVING_DIR}/out/apks/Braving-1.94.120-arm64.apk
```

---

## 5. Verification

Verify branding integrity:
```bash
./scripts/verify-branding.sh
```

---

## 6. Troubleshooting

- **Out of Memory during linking**:
  Add `concurrent_links = 2` or `symbol_level = 0` to `args.gn`.
- **Patch Application Failure**:
  Ensure the source checkout matches the exact git commit defined in `metadata/upstream-<version>.yaml`. Braving strictly avoids fuzzy patch application.
