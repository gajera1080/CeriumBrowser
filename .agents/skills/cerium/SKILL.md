---
name: cerium-browser
description: Canonical guide and operational expert for the Cerium Browser project (customized, de-branded, debloated downstream Brave distribution for Android, Linux, Windows, macOS). Use whenever working with Cerium architecture, GN build arguments, programmatic Python mutators, Shields adblock settings, branding assets, Siso/Ninja build orchestration, distributed GitLab Generic Package Registry caching, verifying changes end-to-end via prepare-source and verify-all, or CI/CD pipelines.
---

# Cerium Browser: The Complete Engineering & Agent Guide

Welcome to the **Cerium Browser** skill. This guide serves as the definitive reference for autonomous agents and engineers working on the Cerium codebase (downstream distribution of Brave Browser).

---

## 1. Project Vision & Architectural Foundation

### What is Cerium?
**Cerium** (maintained by **Cerium Browser Team**) is an independent downstream distribution of the Brave Browser. It is customized to be:
1. **Completely De-Branded**: Stripped of all Brave Lion branding, proprietary telemetry, and promotional assets; replaced with Cerium's clean identity and `org.cerium.browser` package ID.
2. **Radically Debloated**: Stripped of cryptocurrency wallets, Web3 features, AI chatbots (Leo), VPN background services, BAT rewards, news feeds, and user profiling.
3. **Out-of-the-Box Privacy & Aggressive Shields**: Aggressive ad & tracker blocking enabled by default (`ControlType::BLOCK`), first-party ad blocking enabled by default, and a completely clean New Tab Page (zero background images, sponsored takeovers, top sites, or stats).
4. **Dynamically Built**: Built against upstream Brave and Chromium tags without maintaining a permanent 100 GB hard-forked Git repository.

### Critical Principle: Multi-Platform Vision
While Android (`arm64`, `arm`, `x86_64`) and Windows (`x64`, `arm64`) are currently the active reference targets in GitLab CI/CD, Cerium's architecture is **fundamentally multi-platform**:
- **Supported / Roadmap Platforms**: Android (APK & AAB), Windows (`x64`, `arm64`), Desktop Linux (`x86_64`, `aarch64`), macOS (Apple Silicon `arm64`, Intel `x64`), and iOS.
- **Platform-Agnostic Design Principles**:
  - Release manifests (`metadata/releases/*.yaml`) declare `target_os` and `target_cpu` dynamically.
  - GN build arguments (`args.gn`) debloat features across all platforms (`enable_ai_chat`, `enable_brave_wallet`, `enable_brave_vpn`, `enable_brave_rewards`, `enable_brave_news`, `enable_sparkle`, etc.).
  - Programmatic Python mutators target shared cross-platform C++ subsystems (`components/brave_origin`, `components/brave_shields`, `components/resources`, `components/ntp_background_images`).
  - Modular platform build entry points reside in `scripts/platforms/{android,windows}/` alongside core scripts in `scripts/core/`.

---

## 2. The Ephemeral Upstream & Dynamic Version Flow

```mermaid
flowchart TD
    A[Upstream Brave Releases API] -->|Auto-resolve latest stable| B[scripts/core/prepare-source.sh]
    B -->|Fast commit lookup via Gitiles & GitHub| C[Generate metadata/releases/VERSION.yaml]
    C -->|Shallow fetch --depth 1| D[build-workspace/src/brave]
    D -->|Execute Programmatic Mutators| E[Apply C++ / Python Mutators]
    E -->|Bundle uBlock Defaults| F[Download Offline Shields Rules]
    F -->|Export DYNAMIC_BRAVE_VERSION| G[GitLab CI Pipeline]
```

### Key Principles:
1. **Zero Permanent Commits in `brave-core`**:
   The `build-workspace/src/brave` and `build-workspace/src` directories are ephemeral build artifacts fetched and constructed at build time. Never make permanent commits in `brave-core`.
2. **Version Independence & Continuous Roll Forward (Always Target Latest Upstream)**:
   Never hardcode versions (e.g. `<version>`) into scripts or CI files. Cerium is engineered to roll forward continuously with upstream Brave and Chromium tags. All mutators, patches, branding assets, and verification workflows must always be tested and maintained to work against the latest stable upstream release tag. When `BRAVE_VERSION` is omitted, `prepare-source.sh` dynamically queries GitHub's `/releases/latest` and Google's Gitiles API to determine the exact pinned commits for both `brave-core` and Chromium.
3. **Lightweight Metadata Generation**:
   `metadata/releases/*.yaml` files are generated dynamically at build time and stored as pipeline artifacts.

---

## 3. Modification Strategy: Hybrid Patching

### The Hybrid Patching Architecture
Modifications to `brave-core` use a **hybrid approach** to balance simplicity with resilience across upstream version bumps:

1. **Git Patches (`patches/`) for standard modifications**:
   - Use standard unified diff (`.patch`) files for straightforward edits like removing XML preference blocks, changing simple C++ constants, or modifying self-contained UI layouts.
   - Example: `patches/android/0001-cerium-branding.patch`.
   - **Important**: Avoid using `.patch` files for highly dynamic code, such as GN build arrays (e.g. `deps = [...]`), which change constantly in upstream Chromium/Brave and will break patch application.

2. **Programmatic Python Mutators (`scripts/`) for complex/dynamic changes**:
   - Use Python scripts (e.g. `apply-features.py`) strictly for modifications that are too brittle for standard patches.
   - Example: Conditionally modifying GN dependency arrays based on debloat flags, or silencing warnings in rapidly changing build scripts.

### Anatomy of an Idempotent Mutator:
```python
def replace_in_file(filepath, search, replacement):
    path = os.path.join(repo_root, filepath)
    if not os.path.exists(path):
        if STRICT:
            print(f"ERROR: MISSING {filepath}", file=sys.stderr)
            sys.exit(1)
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Idempotency check: never re-apply if already present
    if replacement in content:
        print(f"Skipped {filepath} (already patched)")
        return

    # 2. Semantic replacement
    if search in content:
        content = content.replace(search, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    else:
        if STRICT:
            print(f"ERROR: Search string not found in {filepath}", file=sys.stderr)
            sys.exit(1)
```

---

## 4. Architectural Reuse: No Parallel Engines

### Rule: Reuse Existing Brave & Chromium Subsystems
Do not reinvent browser engines. When implementing custom behavior, hook into the existing system's fallback/failure paths rather than constructing a parallel engine.

### Component Updates & Shields Protection
Cerium routes component updates through our secure GitLab Pages static endpoint (`https://ceriumbrowser.gitlab.io/cerium-updater/components`) via `patches/common/0002-custom-updater-endpoint.patch`:
1. **Default Aggressive Blocking**: Cerium defaults to Aggressive ad and tracker blocking out-of-the-box (`ControlType::BLOCK` in `brave_shields_settings_values.h`) and enables `kBraveAdblockDefault1pBlocking` by default via `scripts/mutators/common/shields.py`.
2. **Key Verification**: Enforces publisher key verification (`kCeriumPublisherKeyHash`), batches component checks into a single request, and appends `disable-pings`.
3. **On-Demand Service Initialization**: Initializes `ad_block_service()` on demand with full profile integration to ensure stable browser startup without race conditions.

---

## 5. De-Branding & Debloating

### 1. De-Branding Suite
- Master vector logo lives at `branding/logo.svg`.
- 156 static raster PNG logos across all standard Android densities (`mipmap-mdpi` through `mipmap-xxxhdpi`) and 10 static SVGs reside in `branding/brave-core-static/`.
- `scripts/core/apply-assets.sh` deploys all static assets into `brave-core` resource overlays with zero build-time dynamic rendering (no PIL or rsvg-convert).
- Dedicated vector icons for Cerium Shields reside in `branding/android/shields_drawables/`.
- `scripts/core/apply-branding.py` rebrands GRD/GRDP strings to "Cerium", credits attribution to "Cerium Browser Team", and remaps Grit 63-bit XTB translation fingerprints safely across all locales.
- Desktop ProgIDs (`CeriumHTML`, `CeriumPDF`, `CeriumFile`, `CeriumBFile`, `CeriumDFile`, `CeriumSSFile`) and product names remapped via `scripts/mutators/platforms/windows/branding.py`.

### 2. Radical Debloating & Clean Defaults
Cerium strips all unneeded promotional, cryptocurrency, and auxiliary subsystems:
- **Clean New Tab Page (NTP) Defaults**:
  - Background images and sponsored wallpaper takeovers disabled by default (`kNewTabPageShowBackgroundImage = false`, `kSponsoredEnabled = false`).
  - Top sites tiles & shortcuts disabled by default (`kNtpShortcutsVisible = false`).
  - Cerium / Brave stats counters disabled by default (`kNewTabPageShowStats = false`).
  - Applied cross-platform via `scripts/mutators/common/ntp_ads.py` and on Android via `scripts/mutators/platforms/android/ntp.py`.
- **Android Bottom Navigation Toolbar**:
  - Disabled by default via `scripts/mutators/platforms/android/toolbar.py` (`BottomToolbarConfiguration.java` and `BraveToolbarManager.java`).
- **Windows Services & Installer Debloating**:
  - Neutralized `UpdateBraveVpn` in `install_worker.cc` (preventing registration of Windows NT VPN & WireGuard services).
  - Skipped promo registry reading in `mini_installer.cc`.
- **Enforced via Native Policies**:
  To avoid constant upstream build breakages caused by GN dependency mismatches on Android, Cerium compiles modules cleanly but locks them down unconditionally at runtime:
  - **Native Brave Origin Policy Enforcement**: Bypassing the paywall in `patches/common/0001-brave-origin-paywall-bypass.patch` unlocks `IsBraveOriginPurchased() == true`, which natively triggers `LoadBraveOriginPolicies(bundle)` to enforce IPFS, Tor, Playlist, Email Aliases, and Psst lockdown.
  - **Explicit Enterprise Policies (`patches/common/debloat/0004-enforce-enterprise-policies.patch`)**: Enforces runtime lockout for `BraveWalletDisabled`, `BraveVPNDisabled`, `BraveAIChatEnabled`, `BraveNewsDisabled`, `BraveRewardsDisabled`, `BraveSearchResultAdsEnabled`, `BraveTalkDisabled`, `BraveStatsPingEnabled`, `BraveWebDiscoveryEnabled`, `BraveP3AEnabled`, `BraveWaybackMachineEnabled`, and `BraveLocalAIEnabled`.
  - Debloat Patches: `patches/common/debloat/` (0001, 0002, 0004) and `patches/android/debloat/` (0003, 0005, 0006) disable promotional flags, unlock backend policy state, remove rating prompts, disable Play in-app updates, and enforce mandatory privacy policies so hidden features cannot be reached or leak data.
- `scripts/core/apply-features.py` isolates Polymer and WebUI resources so Android builds do not transpile unused desktop-only frontend bundles.

---

## 6. Distributed Multi-Platform CI/CD & Two-Tier Caching Architecture

### 1. The 3-Hour SaaS Runner Limit & Pipeline Stages
Chromium + Brave compilation is massive: over 43,000 compilation steps, requiring 1.5 to 3.5 hours on 32-core runners. GitLab CI SaaS runners (`saas-linux-2xlarge-amd64`) enforce a strict job timeout. Running a cold build from checkout to APK or Windows distribution in a single monolithic job risks timing out and losing all compilation progress.

To guarantee that no runner exceeds the 3-hour limit, Cerium splits compilation into a strictly structured 4-stage multi-platform pipeline:
1. **Stage 1: `prepare_source`**: Lightweight runner. Resolves upstream versions dynamically, fetches exact `brave-core`, executes all patches/mutators/branding, and pushes the **Tier 1 Source Cache** via GitLab CI runner cache.
2. **Stage 2: `cache_prep` (`prepare_android_cache` & `prepare_windows_cache`)**: Pulls the Tier 1 Source Cache, syncs Chromium for the target OS, compiles heavy common sub-targets (`v8`, `blink`, `skia`, `gpu`, `angle`), and uploads the **Tier 2 Compiler Cache** to the Generic Package Registry.
3. **Stage 3: `build` (`build_android` & `build_windows`)**: Pulls the Tier 1 Source Cache, restores the Tier 2 warm compiler cache from the Package Registry, completes the remaining targets incrementally, and packages official distributions (APK/AAB/ZIP).
4. **Stage 4: `publish` (`publish_release`)**: Collects all multi-platform binary packages and publishes an official GitLab Release with checksums.

---

### 2. The Two-Tier Caching Architecture

| Cache Tier | Storage Layer | Scope & Contents | Key / Identifier | Policy |
|---|---|---|---|---|
| **Tier 1: Source Transport** | GitLab CI Runner Cache | Fully prepared, patched, branded `src/brave/` | `cerium-src-$CI_PIPELINE_ID` | Stage 1: push<br>Stages 2–3: pull |
| **Tier 2: Compiler Cache** | GitLab Generic Package Registry | Compiled `out/Release/` object files (`v8`, `blink`, obj/, gen/, Siso state) | `${DYNAMIC_BRAVE_VERSION}-${TARGET_ARCH}`<br>(or `-win-${TARGET_ARCH}`) | Stage 2: `upload-cache.sh`<br>Stage 3: `download-cache.sh` |

#### Tier 1: Pre-Patched Source Transport (`src/brave/`) via GitLab CI Runner Cache
- **All `brave-core` modifications MUST happen exclusively in `prepare_source`**:
  - Shallow checkout of exact `brave-core` release commit.
  - Applying all git patches in `patches/` via `apply-patches.sh`.
  - Verifying patch set integrity via `apply-patches.sh --check`.
  - Applying cross-platform GN mutators via `apply-features.py --strict`.
  - Applying Cerium branding overlay and vector assets via `apply-assets.sh`.
  - Applying UI strings remapping via `apply-branding.py --strict`.
  - Prepares `build-workspace/src/brave/` directly in place and caches it via GitLab CI runner cache (`key: cerium-src-$CI_PIPELINE_ID`, `paths: [build-workspace/src/brave/]`, `policy: push`).
- **Runner Cache Transport Configuration**:
  - `prepare_source` caches `build-workspace/src/brave/` directly into GitLab runner cache (`policy: push`).
  - Downstream runners (`prepare_android_cache`, `prepare_windows_cache`, `build_android`, `build_windows`) pull it via `.build_environment_setup` (`policy: pull`, `key: cerium-src-$CI_PIPELINE_ID`).
  - Platform build scripts (`scripts/platforms/{android,windows}/build.sh`) verify `src/brave` and protect `src/brave` and `src/out` during cleanups via `git clean -ffd -e brave -e out`.
- **CRITICAL RULE FOR AGENTS**: Downstream build runners MUST NEVER re-patch, re-brand, or re-run mutators on `brave-core`. `brave-core` is guaranteed to be completely prepared by Stage 1.

#### Tier 2: Compiler Object Cache (`out/Release/`) via GitLab Generic Package Registry
- **Why We Cannot Use GitLab Runner `cache:` for Compiler Output**:
  - **Dotenv Variable Expansion Failure**: In dynamic release mode, `DYNAMIC_BRAVE_VERSION` is generated at runtime in Stage 1 and exported via `build.env` (dotenv report). GitLab CI evaluates `cache:key` **prior to job execution**. Dotenv variables are NOT expanded in `cache:key`. A key like `cerium-cache-${DYNAMIC_BRAVE_VERSION}` evaluates literally to `cerium-cache-`, causing cross-version cache poisoning!
  - **Zip Compression Bottleneck & Size Limits**: GitLab runner native caching compresses target directories into a single monolithic `.zip` archive on the runner and uploads it to object storage. For 5–10 GB compiler trees, zip compression and decompression take 15–20 minutes, frequently timeout, and saturate runner memory.
- **The Solution: Distributed Generic Package Registry (`upload-cache.sh` & `download-cache.sh`)**:
  - Compresses the `out/Release` directory, splitting into 4.5 GB chunks (`chunk.tar.gz.*`) with SHA256 verification (`checksums.sha256`).
  - Uses GitLab's official Package Registry API authenticated via `CI_JOB_TOKEN`:
    `PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/cerium-cache/${CACHE_VERSION}"`
    where `CACHE_VERSION="${DYNAMIC_BRAVE_VERSION}-${TARGET_ARCH}"` (or `${DYNAMIC_BRAVE_VERSION}-win-${TARGET_ARCH}`).
  - If no package exists (e.g. local builds), it logs `Starting cold build` and exits 0 cleanly.

---

### 3. Chromium Source & Build Runners Responsibilities
- Chromium `src` is ephemeral, target-dependent, and heavy (25–30 GB). It is synced on compilation runners via `gclient sync` using target-specific `.gclient` configurations (`target_os = ["android"]` vs `target_os = ["win"]`).
- Downstream build runners (`scripts/platforms/android/build.sh`, `scripts/platforms/windows/build.sh`) ONLY perform Chromium-specific operations after `gclient sync`:
  1. `(cd "${BRAVE_DIR}" && pnpm run apply_patches)`: Applies upstream Brave patches onto Chromium `src`.
  2. `python3 "${REPO_ROOT}/scripts/core/apply-features.py" "${BRAVE_DIR}" --strict --src-dir="${SRC_DIR}" --target-os=...`: Applies Chromium-side mutators (e.g. User-Agent milestone resolution in `components/version_info/` and version display).
- **CRITICAL GUARD**: In `scripts/mutators/context.py`, `has_chromium_src()` verifies that Chromium `src` is populated before allowing any `in_src=True` file mutations. Never run Chromium mutations before `gclient sync`.

---

### 4. Siso vs. Ninja Cache State Files (`.siso_deps` vs. `.ninja_deps`)
- When `use_siso = true`, Siso tracks dependencies through `.siso_deps` and `.siso_fs_state` (and command history in `.ninja_log`).
- **Siso never creates or updates `.ninja_deps`**. Never add checks, warnings, or scripts expecting `.ninja_deps`.
- `download-cache.sh` automatically deletes `build.ninja.d` upon restore so Siso does not compare freshly checked-out source timestamps against `build.ninja` inputs, preserving the cached build graph and command hashes.

---

### 5. Multi-Platform Pipeline Flow

```mermaid
sequenceDiagram
    participant S1 as Stage 1: prepare_source
    participant C1 as Runner Cache (Tier 1)
    participant S2 as Stage 2: cache_prep (Android / Win)
    participant Reg as Package Registry (Tier 1.5 & 2)
    participant S3 as Stage 3: build (Android / Win)
    participant S4 as Stage 4: publish_release

    Note over S1: Resolves version & commits<br/>Applies all patches, mutators, branding<br/>Prepares build-workspace/src/brave
    S1->>C1: Push cerium-src-$CI_PIPELINE_ID cache
    
    C1->>S2: Pull src/brave/ cache
    Note over S2: gclient sync (Chromium for target_os)<br/>pnpm run apply_patches<br/>Compiles heavy targets (v8 & blink)
    S2->>Reg: upload-cache.sh (split 4.5GB chunks + SHA256)
    
    C1->>S3: Pull src/brave/ cache
    Reg->>S3: download-cache.sh (restores warm out/Release)
    Note over S3: Fast incremental compile (chrome / brave)<br/>Packages APK, AAB, ZIP distributions
    
    S3->>S4: Artifacts (APK, AAB, ZIP, checksums)
    Note over S4: publish-release-direct.sh<br/>Creates official GitLab Release

```

---

## 7. GitLab CI 4MB Log Limit & Stream Filtering

### The Problem
GitLab CI runner enforces a strict 4 MB (4,194,304 bytes) truncation limit on job console logs. Compiling Chromium produces >20 MB of stdout. Raw streaming causes GitLab to truncate output around step 3,000, hiding subsequent build steps, compiler errors, and failure summaries.

### The Solution: `filter-build-log.py`
In platform build scripts (`scripts/platforms/android/build.sh` and `scripts/platforms/windows/build.sh`), the build stream is piped through `filter-build-log.py`:
```bash
autoninja -C "${OUT_DIR}" ${BUILD_TARGET} 2>&1 | python3 -u "${REPO_ROOT}/scripts/core/filter-build-log.py" "${WORKSPACE_DIR}/build.log"
BUILD_RES=${PIPESTATUS[0]}
```
- **100% Raw Logging**: All lines are written unbuffered to `${WORKSPACE_DIR}/build.log` and uploaded as a CI artifact.
- **Console Throttling**: Standard progress steps (`^\[\s*(\d+)/(\d+)\]`) are throttled to every 50th step plus first and final step (`[50/43210 (0.1%)] ...`).
- **Immediate Error Forwarding**: **100% of non-progress lines** (compiler errors, warnings, tracebacks, notes, linker errors, diagnostic dumps) are passed directly to `stdout` with unbuffered line flushing.
- Reduces console log size from >20 MB to ~150 KB (less than 4% of the limit), completely preventing truncation.
- `after_script` blocks in `.gitlab-ci.yml` dump the tail of `build.log`, `siso_output`, and `siso_failed_commands.sh` in an isolated collapsible section.

---

## 8. Operational Runbooks for Agents

### 1. Mandatory Two-Step Local Verification
Before proposing changes, creating pull requests, or finalizing work:
Agents must ALWAYS perform the two-step verification workflow:

1. **Step 1: Fast Local Master Verification Suite (`verify-all.sh`)**
   ```bash
   ./scripts/core/verify-all.sh
   ```
   Runs 6 master verification steps: manifest validation, mutator syntax & unit tests, CI automation script checks, patch retirement across trees, branding asset limits, and orchestration dry-run.

2. **Step 2: ALWAYS Validate Using `prepare-source.sh`**
   ```bash
   # Dynamically auto-resolves latest upstream stable release (default):
   ./scripts/core/prepare-source.sh

   # Or validate against an explicit target release version:
   ./scripts/core/prepare-source.sh "<version>"
   ```
   Why this is mandatory:
   `verify-all.sh` verifies syntax, unit tests, and dry-run execution, but `prepare-source.sh` executes the complete end-to-end source pipeline against real upstream trees:
   - Queries GitHub / Gitiles APIs to resolve exact commit pins.
   - Shallow-fetches or resets `brave-core` at the exact tag.
   - Applies all unified diff patches in `patches/`.
   - Executes `apply-features.py --strict`.
   - Executes `apply-assets.sh` (branding overlay and vector icons).
   - Executes `apply-branding.py --strict` (GRD/GRDP/XTB string and translation remapping).
   If any patch fails or mutator breaks against real sources, `prepare-source.sh` fails loudly and immediately. Both commands must pass with exit code 0.

### 2. Testing Build Orchestration (Dry-Run / GN-Only)
```bash
# Validate argument parsing and manifest loading:
./scripts/platforms/android/build.sh --manifest="metadata/releases/<version>.yaml" --arch=arm64 --release --dry-run
./scripts/platforms/windows/build.sh --manifest="metadata/releases/<version>.yaml" --arch=x64 --release --dry-run

# Run up to gn gen (verifies args.gn syntax without starting compilation):
./scripts/platforms/android/build.sh --manifest="metadata/releases/<version>.yaml" --arch=arm64 --release --gn-only
./scripts/platforms/windows/build.sh --manifest="metadata/releases/<version>.yaml" --arch=x64 --release --gn-only
```

### 3. Adding a New Debloating Flag
1. Check flag declaration in `brave-core` (search `declare_args()` in `buildflags.gni`).
2. Add flag to `build_arguments` in `prepare-source.sh` release manifest generation.
3. Add flag to `args.gn` template in platform build scripts.
4. Run `./scripts/core/verify-all.sh` to confirm manifest validation passes.

---

## 9. Guardrails & Agent Commandments

1. **Always target and validate the latest upstream release**: Develop, test, and maintain all patches, mutators, and build configs against the latest stable upstream Brave tag. Fix any upstream code shifts or patch conflicts immediately.
2. **NEVER make permanent direct commits in `brave-core` or `chromium`**.
3. **ALWAYS validate using `prepare-source.sh` and `verify-all.sh`**: Every patch, mutator, and branding asset must pass against real upstream sources via `prepare-source.sh` in addition to unit tests in `verify-all.sh`.
4. **Use Hybrid Patching**: `.patch` files for simple edits (XML/constants), Python mutators for dynamic/GN array edits.
5. **NEVER hardcode version numbers** in scripts or CI configs (always use `<version>` placeholders in comments and templates).
6. **NEVER commit secrets** (tokens, keystore passwords, API keys) into the repository.
7. **Always preserve `set -euo pipefail`** in all shell scripts.
8. **Always verify idempotence** on all programmatic mutators.
9. **Always respect user instructions regarding Git operations** (e.g. "dont commit and push" or "commit but do not push").
10. **Branch Model (`release` vs `main`)**:
    - `release` is the production release branch (official signed releases and release tags). By default on push/merge, it compiles all target architectures (`COMPILE_TARGET="all"`) and publishes official releases. When triggered via the GitLab Web UI, it supports interactive `compile_target` selection (`all`, `android`, `windows`, `windows_x64`, `windows_arm64` with default `all`), enabling single-platform releases (e.g. Android only) as well as full multi-platform releases.
    - `main` is for active development, automated testing, and community merges. When triggered manually in the GitLab Web UI, it provides an interactive `compile_target` input dropdown (`all`, `android`, `windows`, `windows_x64`, `windows_arm64` with default `all`) allowing developers to choose target compilation on demand without publishing official releases. All merge requests must target `main`.
11. **Keep modifications strictly minimalist and essential**: Never add speculative checks, defensive clutter, multi-tier fallback globbing, or unnecessary code that wasn't requested. Keep all patches and mutators lean, structured, and focused solely on the required behavior with direct fail-fast error reporting to prevent fragility across upstream version bumps.
12. **Authoritative Packaging Scripts**: `scripts/platforms/{android,windows}/package.sh` is the authoritative multi-platform packaging and signing entry point. (`sign-apk.sh` exists solely as a compatibility wrapper).
13. **Toolchain Prerequisites**: Windows cross-compilation on Linux runner containers requires `libfuse2` for `ciopfs` to mount the Visual Studio toolchain (`vs_files`), and `GCLIENT_SUPPRESS_GIT_VERSION_WARNING: "1"` set across CI.
