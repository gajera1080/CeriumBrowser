# Braving Android

**Braving** is an independently branded Android browser based on exact Brave and Chromium releases, featuring a maintainable patch-based architecture.

Braving does **not** simply rebrand an APK. It builds directly from clean upstream source code with reproducible, patch-driven modifications.

---

## Architecture Overview

```
User selects BRAVE_VERSION
          ↓
matching brave-core release
          ↓
exact Chromium revision
          ↓
Braving patches
          ↓
Braving Android source
          ↓
reproducible Android build
          ↓
Braving APK / AAB
```

---

## Repository Structure

```
braving/
├── android/                 # Android-specific override sources & configs
├── patches/
│   ├── branding/            # App identity, strings, package name, icons
│   ├── build/               # GN arguments, toolchain settings, manifest
│   ├── features/            # Feature disabling (Wallet, Ads, Rewards, VPN, Leo)
│   ├── origin/              # Minimal / origin policy configurations
│   └── telemetry/           # Disable P3A analytics and metrics reporting
├── scripts/
│   ├── build-android.sh     # Phase 2: Compiles the Android APK
│   ├── generate-icons.sh    # Generates Android launcher icons
│   ├── prepare-source.sh    # Phase 1: Validates revisions & applies patches
│   ├── verify-all.sh        # Runs all verifications
│   ├── verify-branding.sh   # Lints for unintentional Brave trademark remnants
│   └── verify-patches.sh    # Verifies patch integrity
├── metadata/
│   ├── upstream-1.94.120.yaml # Exact upstream tags and commit hashes
│   └── releases/            # Generated release manifests
├── docs/
│   ├── ARCHITECTURE.md      # Detailed technical architecture
│   ├── BUILDING.md          # Complete build instructions
│   ├── FEATURE-AUDIT.md     # Component audit of upstream features
│   ├── RELEASE.md           # Monthly release pipeline guide
│   └── SHIELDS-DEPENDENCY-AUDIT.md # Audit of Shields dependencies
├── tests/                   # Automated build & branding tests
├── .gitlab-ci.yml           # Two-phase GitLab CI pipeline
├── LICENSE                  # MPL-2.0
└── README.md
```

---

## Quick Start: Building Braving

### 1. Prerequisites
- Linux (x86_64 or aarch64)
- Node.js >= 24.16.0, pnpm >= 11.11.0
- Python 3.10+, JDK 17+
- Android SDK & NDK

### 2. Prepare Source
```bash
./scripts/prepare-source.sh 1.94.120
```

### 3. Build Android APK
```bash
./scripts/build-android.sh --arch=arm64 --release
```

---

## License

This project is licensed under the [Mozilla Public License 2.0](LICENSE).
Upstream Chromium is licensed under BSD-3-Clause and upstream Brave Core under MPL-2.0.
