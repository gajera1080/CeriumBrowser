# Braving Project: Canonical Agent Instructions

Welcome, agent. This document outlines the architectural vision, constraints, workflows, and core principles of the **Braving** project. Read this carefully before making any modifications, proposing plans, or writing code.

---

## 1. Project Overview & Multi-Platform Vision

**Braving** is a customized, fully de-branded, debloated, and privacy-hardened downstream distribution of the Brave Browser. It is designed to be built dynamically against upstream Brave and Chromium releases without maintaining a massive, unwieldy hard-forked Git repository.

### Critical Principle: Braving is NOT Android-Only
While Android (ARM64, ARM, x86_64) is currently the active primary target in CI/CD, Braving's architectural foundation is **fundamentally multi-platform**:
- **Supported / Planned Targets**: Android, Desktop Linux (x86_64, aarch64), Windows (x64, arm64), macOS (Apple Silicon arm64, Intel x64), and iOS.
- **Platform-Agnostic Abstractions**:
  - Release manifests (`metadata/releases/*.yaml`) declare `target_os` and `target_cpu` dynamically.
  - GN build arguments (`args.gn`) debloat features across all platforms (`enable_ai_chat`, `enable_brave_wallet`, `enable_brave_vpn`, `enable_brave_rewards`, `enable_brave_news`, `enable_sparkle`, etc.).
  - Programmatic Python mutators target shared cross-platform C++ subsystems (`components/brave_origin`, `components/brave_shields`, `components/resources`).
  - Desktop-specific scripts and build entry points will reside in `scripts/desktop/` alongside `scripts/android/`.
- **Rule for Agents**: Never assume a feature or mutator is only for Android unless it specifically modifies Android-only paths (e.g. `android/java/` or Android XML drawables). Keep core C++ and build logic cleanly reusable across all target operating systems.

---

## 2. Ephemeral Upstream & The Dynamic Flow

### CRITICAL RULE: Do NOT make permanent direct commits in `brave-core` or `chromium`.
- The `build-workspace/src/brave` and `build-workspace/src` directories are treated as **ephemeral, dynamic build artifacts**. They are fetched and constructed dynamically at build time.
- If you make a manual change in `brave-core` for local testing, you **MUST** extract that change into an automated programmatic Python mutator script stored in the **Braving** repository. The CI pipeline clones a fresh upstream repository and will never see local `brave-core` Git commits.
- **The build flow MUST be version-independent:**
  - If `BRAVE_VERSION` is empty in CI/CD, the build system automatically resolves the latest stable release from the GitHub API and Google Gitiles API.
  - **Never hardcode versions** (e.g., `1.95.102`) in CI configs or scripts to "fix" a build. The pipeline is engineered to roll forward continuously with upstream Brave and Chromium tags.
  - Manifests (`metadata/releases/` and `metadata/upstream/`) are generated dynamically by preparation scripts and are pipeline artifacts, not static git-pinned files.

---

## 3. Modification Strategy: Hybrid Patching

Modifications to `brave-core` use a **hybrid approach** to balance simplicity with resilience across upstream version bumps:

1. **Git Patches (`patches/`) for standard modifications**:
   - Use standard unified diff (`.patch`) files for straightforward edits like removing XML preference blocks, changing simple C++ constants, or modifying self-contained UI layouts.
   - Example: `patches/android/0001-braving-branding.patch`.
   - **Important**: Avoid using `.patch` files for highly dynamic code, such as GN build arrays (e.g. `deps = [...]`), which change constantly in upstream Chromium/Brave and will break patch application.

2. **Programmatic Python Mutators (`scripts/`) for complex/dynamic changes**:
   - Use Python scripts (e.g. `apply-features.py`) strictly for modifications that are too brittle for standard patches.
   - Example: Conditionally modifying GN dependency arrays based on debloat flags, or silencing warnings in rapidly changing build scripts.
   - **Requirements for Mutators:**
     - **Semantic Anchors**: Anchor replacements to stable tokens (method signatures, unique array entries) rather than arbitrary line numbers or exact multi-line blocks.
     - **Strict Idempotence**: Running a mutator twice on the same codebase must be a safe, clean no-op. If a patch is missing but already applied, it should silently skip. If a patch is missing and NOT applied, it must throw a fatal error to fail the CI build loudly.

### CRITICAL SUB-RULE: No Naive Global String Replacements
- **Never perform global find-and-replace for branding** (e.g., naively replacing "Brave" with "Braving" across `.grd`, `.cc`, or `.gn` files via a regex loop).
- **Why:** The codebase relies on exact string matches for C++ variable names, GN targets, and translation IDs (e.g., `IDS_Brave_Rewards`). A global regex replacement will accidentally mutate these internal identifiers, causing widespread compiler and runtime crashes.
- **How to de-brand safely:**
  - For UI strings (GRD/GRDP files), only mutate strings explicitly using proper XML parsing targeting the inner text of `<message>` nodes, or via safe targeted regex with negative lookbehinds that explicitly protect `name=` attributes.
  - For C++ strings, replace specific constants or definitions rather than the word itself.
  - Rely on `apply-assets.sh` for logo and image asset de-branding.

---

## 4. Architectural Reuse: No Parallel Engines

### Do NOT reinvent the wheel.
- If Brave or Chromium provides an existing system (e.g., `AdBlockComponentServiceManager`, `AdBlockEngine`, `SubresourceFilter`), **reuse it**.
- If custom behavior is required (such as offline ad-block rules when the network is down or before first update), **hook into the existing system's fallback/failure paths** rather than constructing a parallel engine.
- Modifications must remain asynchronous, non-blocking to the main browser thread, and preserve native Blink/V8 performance characteristics.

### Offline Shields & Resource Bundling
- Braving includes pre-bundled, offline adblock lists sourced from uBlock Origin defaults (EasyList, EasyPrivacy, Peter Lowe, scriptlets, redirect resources).
- These rules are downloaded dynamically at preparation time (`prepare-source.sh`) and packaged into `brave_components_resources.pak` via Grit (`brave_shields_resources.grdp`).
- `apply-shields-fallback.py` hooks `ad_block_component_filters_provider.cc` and `ad_block_default_resource_provider.cc` so that if component updater rules are not yet downloaded or fail to load, the engine immediately falls back to the internal bundled resources.

---

## 5. De-Branding & Debloating

### 1. Complete De-Branding
- Eliminate all visible Brave Lion branding across the browser:
  - App icons, launcher icons (legacy and adaptive foreground/background).
  - Splash screens, First Run Experience (FRE) graphics.
  - Themed icons (Android 13+ monochrome / themed drawables).
  - Browser toolbar shields vector drawables (`shields_drawables`).
  - Strings: "Brave" $\to$ "Braving", package ID `com.brave.browser` $\to$ `org.braving.browser`.
- Brand assets are tracked in `branding/` and applied deterministically via `scripts/android/apply-assets.sh` and `apply-branding.py`.

### 2. Radical Debloating (Enterprise Policy Approach)
Braving strips all unneeded promotional, cryptocurrency, and auxiliary subsystems:
- **Hidden Subsystems**: Brave Wallet / Crypto, AI Chat / Leo, Brave VPN, Brave News, Brave Rewards / BAT Ads, Web Discovery Project, P3A Telemetry, Wayback Machine fallback, Sparkle auto-updater.
- **Enforced via Native Policies**:
  To avoid constant build breakages caused by upstream dependency mismatches, Braving for Android does *not* use compile-time GN arguments (`enable_brave_wallet = false`) to strip code. Instead, we compile the modules but strictly lock them down at runtime via Enterprise Policies enforced in `brave_browser_policy_provider.cc` (or similar policy mutators).
  - UI & Policy Mutators: `prune-ui.py` and `enforce-policies.py` remove settings UI elements and enforce native policies so hidden features cannot be reached.

---

## 6. Distributed CI/CD Architecture & GitLab Generic Package Registry

### Why We Use GitLab Generic Package Registry Instead of GitLab Runner `cache:`
Chromium + Brave compilation is massive: over 43,000 compilation steps, requiring 1.5 to 3.5 hours on 32-core runners. This presents critical constraints on GitLab CI:

1. **The 3-Hour SaaS Runner Limit**:
   GitLab CI SaaS runners (`saas-linux-2xlarge-amd64`) enforce a strict job timeout. Running a cold build from checkout to APK in a single job frequently times out.
   - **Solution**: We split compilation into separate pipeline stages:
     - `prepare_source` (lightweight, resolves versions, prepares sources, applies mutators).
     - `prepare_chromium_cache` (compiles heavy common sub-targets: `v8` and `blink`).
     - `build_android` (restores warm cache, finishes remaining targets, and packages APK).
2. **Failure of GitLab CI Native Runner `cache:` for Dynamic Multi-Gigabyte Builds**:
   - **No Dotenv Variable Expansion**: In dynamic version mode, `DYNAMIC_BRAVE_VERSION` is computed at runtime in Stage 1 and exported as a dotenv artifact. GitLab CI evaluates `cache:key` **prior to job execution**, meaning dotenv variables are NOT expanded. A key like `braving-cache-${DYNAMIC_BRAVE_VERSION}` evaluates to `braving-cache-`, causing severe cross-version cache poisoning!
   - **Size and Timeout Bottlenecks**: GitLab runner cache creates a single monolithic `.zip` archive on the runner and uploads it to GitLab object storage. For 5–10 GB compiler trees, zip compression and decompression take 15–20 minutes and often fail or time out.
3. **The Solution: Distributed Generic Package Registry (`upload-cache.sh` & `download-cache.sh`)**:
   - Compresses the `out/Release` directory, splitting into 4.5 GB chunks (`chunk.tar.gz.*`) with SHA256 verification (`checksums.sha256`).
   - Uses GitLab's official Package Registry API authenticated via `CI_JOB_TOKEN`:
     `PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-cache/${CACHE_VERSION}"`
     where `CACHE_VERSION="${DYNAMIC_BRAVE_VERSION}-${TARGET_ARCH}"`.
   - If no package exists (e.g. local builds), it logs `Starting cold build` and exits 0 cleanly.
4. **Siso vs. Ninja Cache State Files (`.siso_deps` vs. `.ninja_deps`)**:
   - Braving enables Siso (`use_siso = true` in `args.gn`) as its primary build executor.
   - Siso uses its own HashFS and dependency database (`.siso_deps` and `.siso_fs_state`) along with `.ninja_log` to track target dependencies and command hashes (`cmdhash`).
   - **Siso never writes or uses Ninja's legacy `.ninja_deps` binary log.** Checking for `.ninja_deps` will produce false-positive warnings.
   - **Rule for Agents**: Never require or verify `.ninja_deps` in cache upload/download routines or validation scripts. The authoritative state files for Siso are `.siso_fs_state`, `.siso_deps`, and `.ninja_log`.
   - **Preventing Manifest Regeneration**: `download-cache.sh` intentionally removes `build.ninja.d` upon restore so Siso does not compare freshly checked-out source timestamps against `build.ninja` inputs, preserving the cached build graph and command hashes.

---

## 7. GitLab CI 4MB Log Limit & Stream Filtering

### The Problem
GitLab CI runner has a hard limit of 4,194,304 bytes (4 MB) for job console logs. Compiling Chromium produces >20 MB of progress lines (`[1/43210]`, `[2/43210]`, ...). When dumped raw to stdout, GitLab truncates the log around step 3,000 (`Job log exceeds limit of 4194304 bytes. Job log was truncated`), hiding all subsequent progress, compiler errors, and failure diagnostic summaries.

### The Solution: `filter-build-log.py`
In `scripts/android/build-android.sh`, build output is piped through `filter-build-log.py`:
- **100% of Raw Output Recorded**: All lines are written unbuffered to `${WORKSPACE_DIR}/build.log` and uploaded as a CI artifact.
- **Console Throttling**: Standard Ninja/Siso progress steps (`^\[\s*(\d+)/(\d+)\]`) are throttled to every 50th step plus the first and final step (`[50/43210 (0.1%)] ...`).
- **Immediate Error Pass-Through**: **100% of non-progress lines** (compiler errors, warnings, tracebacks, notes, linker errors, diagnostic dumps) are passed through immediately to `stdout` with unbuffered flushing.
- **Post-Build Diagnostics**: `after_script` blocks in `.gitlab-ci.yml` dump the tail of `build.log`, `siso_output`, and `siso_failed_commands.sh` in an isolated collapsible section.

---

## 8. Agent Checklist & Verification Rules

Before submitting changes or proposing pull requests:
1. **Never make commits in `brave-core`**: Changes must live in `Braving` as mutators or scripts.
2. **Never create `.patch` files**: Implement modifications as idempotent Python mutators.
3. **Never hardcode versions**: Ensure scripts work with dynamically resolved versions.
4. **Preserve strict error handling**: Shell scripts must run under `set -euo pipefail`.
5. **Run the local verification suite**:
   ```bash
   ./scripts/android/verify-all.sh
   ```
   All 5 verification steps (manifest validation, mutator syntax, patch retirement, branding verification, orchestration dry-run) must pass cleanly.
6. **Never write secrets into files**: API keys, tokens, or keystore passwords must be passed via environment variables.

---
**Summary for Agents:**
Think dynamically. Don't write static patches; write resilient mutators. Don't pin versions; support the flow. Reuse Brave's architecture. Support multi-platform. Test against clean environments.
