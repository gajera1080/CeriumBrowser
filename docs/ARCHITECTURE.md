# Braving System Architecture & Modular Design

Braving is an independent, customized, fully de-branded, debloated, and privacy-hardened downstream distribution of the Brave Browser. It is designed to be built dynamically against upstream Brave and Chromium releases without maintaining a permanent, unwieldy hard-forked Git repository.

---

## 1. Modular Repository Architecture

The repository is organized into distinct, decoupled subsystems with strict separation of concerns:

```
Braving Repository Structure
├── branding/                       # [Module 1] Brand Identity & Assets
│   ├── logo.svg                    # Master vector identity
│   ├── android/                    # Adaptive & themed vector drawables
│   │   ├── drawable/               # 10 core vector logo drawables
│   │   ├── res_brave_base/         # Adaptive launcher & Android 13+ themed icons
│   │   └── shields_drawables/      # Dedicated Braving Shields toolbar icons (24dp)
│   └── brave-core-static/          # 156 density PNGs & 10 static SVGs for brave-core
│
├── patches/                        # [Module 2 & 3] Standard Unified Patches
│   └── android/
│       ├── 0001-braving-branding.patch           # Core branding & package ID
│       ├── 0002-custom-updater-endpoint.patch    # Custom updater & telemetry suppression
│       └── debloat/                              # Modular Enterprise Debloating
│           ├── 0001-hide-brave-origin-flag.patch
│           ├── 0002-unlock-brave-origin-backend.patch
│           ├── 0003-unlock-brave-origin-android-prefs.patch
│           └── 0004-enforce-enterprise-policies.patch
│
├── scripts/                        # Operational Scripts & Mutators
│   ├── android/                    # Android Target Entry Points
│   │   ├── prepare-source.sh       # Version resolution, checkout, patch/mutator orchestration
│   │   ├── apply-features.py       # [Module 2] Programmatic GN array mutator
│   │   ├── apply-branding.py       # [Module 1] GRD/GRDP string & XTB translation mutator
│   │   ├── apply-assets.sh         # [Module 1] Static asset overlay deployment
│   │   ├── build-android.sh        # [Module 4] Release build orchestration & GN configuration
│   │   ├── filter-build-log.py     # [Module 4] Real-time CI 4MB stream log filter
│   │   ├── sign-apk.sh             # [Module 5] APK release signing & verification
│   │   ├── verify-branding.sh      # [Module 1] Standalone branding verification
│   │   └── verify-all.sh           # [Module 7] Master 5-tier verification suite
│   ├── download-cache.sh           # [Module 6] Generic Package Registry cache restore & Siso sync
│   ├── upload-cache.sh             # [Module 6] Generic Package Registry cache chunker & upload
│   └── tests/                      # [Module 7] Automated Unit & Integration Tests
│       ├── test_manifest.py        # Manifest schema & package_id verification
│       ├── test_branding.py        # Asset dimensions, XML syntax, AAPT2 string limits
│       ├── test_mutators.py        # Python 3.11 syntax, mutator idempotence, patch checks
│       └── test_cache_scripts.py   # Siso timestamp sync & script syntax tests
│
├── metadata/                       # Upstream Revisions & Release Manifests
│   ├── releases/*.yaml             # Generated release manifests (package_id, commits, arch)
│   └── upstream-*.yaml             # Pinned upstream repositories & GN base arguments
│
└── docs/                           # Architecture, Building, and Release Documentation
```

---

## 2. Separation of Concerns

### Module 1: Branding Assets & Localization
- **Assets (`branding/` & `apply-assets.sh`)**: Houses all visual assets. `apply-assets.sh` performs zero dynamic rendering at build time; it copies 100% pre-validated static raster PNGs, SVGs, and Android XML drawables directly into the appropriate resource overlays.
- **Strings (`apply-branding.py`)**: Parses GRD/GRDP XML message definitions safely without naive global regex substitutions. Computes Grit 63-bit fingerprints and remaps XTB translation IDs across all supported locales.
- **Verification (`verify-branding.sh` & `test_branding.py`)**: Enforces AAPT2 ResStringPool limits (<32,767 bytes), intrinsic dimensions (e.g. 24dp for toolbar shields), and verifies the complete absence of upstream Brave lion vector paths.

### Module 2: Enterprise Policies & Radical Debloating
- Rather than maintaining fragile GN build flags that break upstream compiler trees, Braving compiles modules cleanly but disables them unconditionally via Enterprise Policies.
- `patches/android/debloat/0004-enforce-enterprise-policies.patch` injects mandatory policies at browser start:
  - `BraveWalletDisabled = true`
  - `BraveVPNDisabled = true`
  - `BraveAIChatEnabled = false`
  - `BraveNewsDisabled = true`
  - `BraveRewardsDisabled = true`
  - `BraveSearchResultAdsEnabled = false`
  - `BraveStatsPingEnabled = false`
  - `BraveP3AEnabled = false`
  - `BraveWebDiscoveryEnabled = false`
  - `MetricsReportingEnabled = false`
- `apply-features.py` isolates Polymer and WebUI resources so Android builds do not transpile unused desktop-only frontend bundles.

### Module 3: Component Updater & Privacy
- `patches/android/0002-custom-updater-endpoint.patch` points component updates to `https://braving.gitlab.io/braving-updater/components`.
- Verifies custom Braving publisher key hashes (`kBravingPublisherKeyHash`).
- Batches update checks and appends `disable-pings` to component updater invocations.

### Module 4: Release Build Orchestration
- `scripts/android/build-android.sh` configures hermetic, reproducible release arguments:
  - `is_debug = false`, `is_official_build = true`, `is_java_debug = false`
  - `symbol_level = 0`, `blink_symbol_level = 0`, `v8_symbol_level = 0`
  - `dcheck_always_on = false`, `enable_java_asserts = false`
  - `exclude_unwind_tables = true`
  - `target_android_output_format = "apk"`
- Build output streams through `filter-build-log.py`, which throttles progress lines (`[50/43210 (0.1%)]`) while immediately flushing 100% of compiler errors, warnings, and failure diagnostics to stdout, fully preventing GitLab CI's 4MB console log truncation limit.

### Module 5: Standalone APK Release Signing
- `scripts/android/sign-apk.sh` operates as an independent module.
- Strips any intermediate debug v1 signatures to guarantee a single release identity.
- Zipaligns APKs to 4-byte boundaries.
- Signs with Android APK Signature Schemes v1, v2, and v3.
- Verifies cryptographically with `apksigner verify`.

### Module 6: Distributed CI Caching (Siso-Aware)
- Chromium compilation involves >43,000 steps. Braving splits compilation across CI stages and bridges them via GitLab Generic Package Registry.
- `upload-cache.sh` splits the `out/Release` directory into 4.5 GB chunks with SHA256 checksums.
- `download-cache.sh` streams and extracts the cache, removing `build.ninja.d` to prevent spurious manifest regeneration.
- Timestamp synchronization enforces:
  $$T_{\text{source}} \le T_{\text{manifest}} < T_{\text{output}}$$
  ensuring Siso's `inmtime.After(outmtime)` condition evaluates to false, preserving pre-built objects and command hashes.

### Module 7: Master Verification Suite
- `scripts/android/verify-all.sh` orchestrates:
  1. Manifest & upstream metadata schema validation (`test_manifest.py`)
  2. Python 3.11 syntax compatibility & mutator unit tests (`test_mutators.py`, `test_cache_scripts.py`)
  3. Patch application validation against `brave-core`
  4. Visual branding and AAPT2 asset verification (`verify-branding.sh`, `test_branding.py`)
  5. Android build and APK signing orchestration dry-run

