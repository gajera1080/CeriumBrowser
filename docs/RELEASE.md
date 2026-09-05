# Braving Release Process

This document outlines the standard release lifecycle for Braving Android builds.

---

## The Monthly Release Pipeline

```
1. Choose Brave version (e.g. BRAVE_VERSION=1.94.120)
                  ↓
2. Trigger Phase 1 (prepare-source.sh)
                  ↓
3. Validate generated release manifest
                  ↓
4. Trigger Phase 2 (build-android.sh)
                  ↓
5. Run automated test suite & branding verifier
                  ↓
6. Publish Braving GitHub / GitLab release
```

---

## Step-by-Step Instructions

### Step 1: Select Upstream Brave Version
Identify the new stable release tag from upstream `brave-core` (e.g. `v1.94.120`).
Create the upstream metadata file:
```
metadata/upstream-<BRAVE_VERSION>.yaml
```
Record:
- exact brave-core tag and commit hash
- exact Chromium revision and version tag

### Step 2: Run Source Preparation
Execute the Phase 1 script:
```bash
./scripts/prepare-source.sh <BRAVE_VERSION>
```
This script checks out the exact revisions, verifies all patches apply cleanly, and writes the release manifest to `metadata/releases/<BRAVE_VERSION>.yaml`.

### Step 3: Verify the Manifest
Inspect `metadata/releases/<BRAVE_VERSION>.yaml` to confirm:
- `package_id` is `org.braving.browser`
- No floating versions (`latest`, `master`) are used
- All patch hashes and target architectures are explicitly declared

### Step 4: Build Android Target
Run the Phase 2 compilation:
```bash
./scripts/build-android.sh --manifest="metadata/releases/<BRAVE_VERSION>.yaml" --arch=arm64 --release
```

### Step 5: Test APK
Run the branding verification tool:
```bash
./scripts/verify-branding.sh
```
Install the generated APK onto a physical device or emulator to test:
- App launches and displays "Braving" launcher title
- Navigation, tabs, and HTTPS loading
- Zero crashes on startup
- Privacy Shields functioning properly
- Complete absence of Wallet, Ads, and VPN prompts

### Step 6: Publish Release
Tag the Braving repository with the release version:
```bash
git tag -a v1.94.120 -m "Braving release 1.94.120"
git push origin v1.94.120
```
Upload the release APKs and SHA256 checksums to the release page.
