# Braving Release Process

This document outlines the standard release lifecycle for Braving Android builds.

---

## The Release Pipeline

```
1. Resolve Brave version (manual or dynamic GitHub API auto-resolve)
                  ↓
2. Trigger Phase 1: prepare-source.sh (fetches brave-core, applies patches & mutators)
                  ↓
3. Validate manifests and assets: verify-all.sh (runs all 5 verification tiers)
                  ↓
4. Trigger Phase 2: build-android.sh (restores warm cache, builds chrome_public_apk)
                  ↓
5. Sign and verify APK: sign-apk.sh (v1, v2, v3 release signatures)
                  ↓
6. Publish Braving GitHub / GitLab release artifacts
```

---

## Step-by-Step Instructions

### Step 1: Source Preparation
Execute the Phase 1 preparation script:
```bash
./scripts/android/prepare-source.sh
# Or pass a specific version:
# ./scripts/android/prepare-source.sh 1.95.104
```
This script:
- Dynamically resolves the latest upstream stable Brave version and pinned Chromium commit.
- Checks out `brave-core` at the exact commit hash (`--depth 1`).
- Applies unified patches from `patches/android/`.
- Executes programmatic Python mutators (`apply-features.py`, `apply-assets.sh`, `apply-branding.py`).
- Generates `metadata/upstream-<version>.yaml` and `metadata/releases/<version>.yaml`.

### Step 2: Run Verification Suite
Run the master verification suite before building:
```bash
./scripts/android/verify-all.sh
```
This verifies:
1. Manifest and upstream metadata schema validity.
2. Python 3.11 syntax compatibility and unit tests.
3. Patch application against `brave-core`.
4. Branding assets and AAPT2 limits.
5. Build and signing orchestration dry-run.

### Step 3: Compile Android Target
Run the Phase 2 compilation:
```bash
./scripts/android/build-android.sh --arch=arm64 --release
```

### Step 4: Sign Release APK
If signing credentials were provided via environment variables, `build-android.sh` signs automatically. Otherwise, run standalone signing:
```bash
./scripts/android/sign-apk.sh --apk="out/apks/Braving-<version>-arm64.apk"
```

### Step 5: Test APK
Install the signed APK on a physical device or emulator:
```bash
adb install -r out/apks/Braving-<version>-arm64.apk
```
Verify:
- Launcher icon displays the crisp Braving circular gradient icon.
- App displays "Braving" launcher title and application title.
- Android 13+ monochrome themed icon renders correctly in light and dark modes.
- Toolbar Shields icon displays the colored Braving icon when shields are ON and outline when OFF.
- Clean absence of crypto wallet, VPN upsells, AI chat prompts, and ads.
- Offline and online ad blocking works seamlessly.

