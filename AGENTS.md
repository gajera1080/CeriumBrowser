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
  - Modular platform build entry points reside in `scripts/platforms/{android,windows}/` alongside shared core scripts in `scripts/core/`.
- **Rule for Agents**: Never assume a feature or mutator is only for Android unless it specifically modifies Android-only paths (e.g. `android/java/` or Android XML drawables). Keep core C++ and build logic cleanly reusable across all target operating systems.

---

## 2. Ephemeral Upstream & The Dynamic Flow

### CRITICAL RULE: Do NOT make permanent direct commits in `brave-core` or `chromium`.
- The `build-workspace/src/brave` and `build-workspace/src` directories are treated as **ephemeral, dynamic build artifacts**. They are fetched and constructed dynamically at build time.
- If you make a manual change in `brave-core` for local testing, you **MUST** extract that change into an automated programmatic Python mutator script stored in the **Braving** repository. The CI pipeline clones a fresh upstream repository and will never see local `brave-core` Git commits.
- **The build flow MUST be version-independent & always target the latest upstream version:**
  - **Always Target Latest Upstream Version**: Braving is engineered to continuously roll forward with upstream Brave and Chromium releases. All mutators, patches, branding assets, and verification workflows must always be tested and maintained to work against the latest stable upstream release tag. Never pin or regress to older releases to bypass issues.
  - If `BRAVE_VERSION` is empty in CI/CD, the build system automatically resolves the latest stable release from the GitHub API and Google Gitiles API.
  - **Never hardcode versions** (e.g., `<version>`) in CI configs or scripts to "fix" a build. The pipeline is engineered to roll forward continuously with upstream Brave and Chromium tags.
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

### CRITICAL SUB-RULE: Minimalist & Essential Code (Zero Bloat & Anti-Overengineering)
- **Strict Minimalism**: Agents must ALWAYS introduce the absolute minimum code necessary to solve the issue or implement the requirement.
- **No Speculative or Superfluous Checks**: Never add defensive checks, boilerplate layers, speculative fallbacks, hypothetical error handlers, or unrequested features that are not strictly demanded by the task.
- **Why**: Agents frequently add excessive checks and boilerplate that the codebase does not need. In a downstream distribution tracking fast-moving upstream releases, superfluous code adds maintenance debt, pollutes the repository, and creates unnecessary breakages across upstream version bumps (such as Chromium Clang `-Werror` unused variable/parameter failures).
- **Surgical & Structured**: Focus directly on the root cause. Every line added must serve a verified, essential purpose. Keep code as minimalist, cleanly structured, and maintainable as possible.

---

## 4. Architectural Reuse: No Parallel Engines

### Do NOT reinvent the wheel.
- If Brave or Chromium provides an existing system (e.g., `AdBlockComponentServiceManager`, `AdBlockEngine`, `SubresourceFilter`), **reuse it**.
- If custom behavior is required (such as offline ad-block rules when the network is down or before first update), **hook into the existing system's fallback/failure paths** rather than constructing a parallel engine.
- Modifications must remain asynchronous, non-blocking to the main browser thread, and preserve native Blink/V8 performance characteristics.

### Component Updates & Shields Protection
- Braving routes component updates through our secure GitLab Pages static endpoint (`https://braving.gitlab.io/braving-updater/components`) via `patches/common/0002-custom-updater-endpoint.patch`.
- Enforces Braving publisher key verification (`kBravingPublisherKeyHash`), batches component requests, and appends `disable-pings`.
- Initializes `ad_block_service()` on demand with full profile integration to ensure stable browser startup without race conditions.

---

## 5. De-Branding & Debloating

### 1. Complete De-Branding
- Eliminate all visible Brave Lion branding across the browser:
  - App icons, launcher icons (legacy and adaptive foreground/background).
  - Splash screens, First Run Experience (FRE) graphics.
  - Themed icons (Android 13+ monochrome / themed drawables).
  - Browser toolbar shields vector drawables (`shields_drawables`).
  - Strings: "Brave" $\to$ "Braving", package ID `com.brave.browser` $\to$ `org.braving.browser`.
- Brand assets are tracked in `branding/` and applied deterministically via `scripts/core/apply-assets.sh` and `scripts/core/apply-branding.py`.

### 2. Radical Debloating (Enterprise Policy Approach)
Braving strips all unneeded promotional, cryptocurrency, and auxiliary subsystems:
- **Hidden Subsystems**: Brave Wallet / Crypto, AI Chat / Leo, Brave VPN, Brave News, Brave Rewards / BAT Ads, Web Discovery Project, P3A Telemetry, Wayback Machine fallback, Sparkle auto-updater.
- **Enforced via Native Policies**:
  To avoid constant build breakages caused by upstream dependency mismatches, Braving does *not* use compile-time GN arguments (`enable_brave_wallet = false`) to strip code. Instead, we compile the modules but strictly lock them down at runtime via Enterprise Policies enforced in `brave_browser_policy_provider.cc` via `patches/common/debloat/0004-enforce-enterprise-policies.patch`.
  - Debloat Patches: `patches/common/debloat/` (0001, 0002, 0004) and `patches/android/debloat/` (0003, 0005, 0006) disable promotional flags, unlock backend policy state, remove rating prompts, disable Play in-app updates, and enforce mandatory privacy policies so hidden features cannot be reached or leak data.

---

## 6. Distributed CI/CD Architecture & Multi-Tier Caching

### 1. The 3-Hour SaaS Runner Limit & Pipeline Stage Separation
Chromium + Brave compilation is massive: over 43,000 compilation steps, requiring 1.5 to 3.5 hours on 32-core runners. GitLab CI SaaS runners (`saas-linux-2xlarge-amd64`) enforce a strict job timeout. Running a cold build from checkout to APK/distribution in a single job frequently times out.

To guarantee that no runner exceeds the 3-hour limit, Braving splits compilation into a strictly structured 4-stage pipeline:
1. **Stage 1: `prepare_source`**: Lightweight stage. Resolves upstream versions dynamically, fetches exact `brave-core`, executes all patches/mutators/branding, and uploads the Tier 1 Source Cache.
2. **Stage 2: `cache_prep` (`prepare_android_cache` & `prepare_windows_cache`)**: Pulls the pre-patched source cache, syncs Chromium for the target OS, compiles heavy common sub-targets (`v8` and `blink`), and uploads the Tier 2 Compiler Cache to the Package Registry.
3. **Stage 3: `build` (`build_android` & `build_windows`)**: Pulls the pre-patched source cache, restores the Tier 2 warm compiler cache from the Package Registry, completes the remaining targets incrementally, and packages official distributions (APK/AAB/ZIP).
4. **Stage 4: `publish` (`publish_release`)**: Gathers all multi-platform binary packages and publishes an official GitLab Release with checksums.

---

### 2. The Two-Tier Caching Architecture

#### Tier 1: Reliable brave-core Source Transport via Pipeline Job Artifacts
- **Stage 1 (`prepare_source`) prepares ONLY `brave-core`**:
  - Shallow checkout of exact `brave-core` release commit.
  - Applying all git patches in `patches/`.
  - Applying cross-platform GN mutators via `apply-features.py --strict`.
  - Applying Braving branding overlay and vector assets via `apply-assets.sh`.
  - Applying UI strings remapping via `apply-branding.py --strict`.
  - Packaging prepared `brave-core` into a pipeline job artifact: `build-workspace/brave-src-${DYNAMIC_BRAVE_VERSION}.tar.gz` (~380 MB compressed, well within GitLab SaaS 1 GB artifact limit).
  - Eliminates reliance on best-effort, opportunistic GitLab Runner `cache:`, guaranteeing deterministic delivery to downstream stages (`cache_prep` and `build`).
  - Automatically unpacked into `build-workspace/src/brave` in downstream jobs (`.build_environment_setup`) and verified with fallback unpacking in platform build scripts.

#### Tier 1.5: Base Chromium & Toolchain Cache via GitLab Generic Package Registry
- **Managed via `scripts/core/sync-chromium-source.sh`**:
  - Base Chromium (`chromium-src-${CHROMIUM_VERSION}.tar.xz`) and `depot_tools` (`depot-tools.tar.xz`) are stored in the Generic Package Registry under package `braving-chromium-source` and version `${CHROMIUM_VERSION}`.
  - Shared across all platforms (Android, Windows, etc.) and branches targeting the same Chromium milestone.
  - On registry cache hit: restored in ~25–30 seconds.
  - On registry cache miss: fetched, pre-synced with host Clang, Rust, and GN, packaged, and idempotently uploaded during Stage 2 (`cache_prep`).
  - Temporary `.tar.xz` archives are deleted immediately after upload/extraction to free disk space before Chromium compilation begins.
  - Stage 2 (`cache_prep`) pre-compiles heavy Chromium targets unchanged by Brave (`v8`, `third_party/blink/public:blink`, `skia`, `gpu`, `third_party/angle`, `third_party/webrtc`) into the Tier 2 warm compiler cache.
- **CRITICAL RULE FOR AGENTS**: Downstream build runners MUST NEVER re-patch, re-brand, or re-run mutators on `brave-core`. `brave-core` is guaranteed to be completely prepared by Stage 1.

#### Tier 2: Compiler Object Cache (`out/Release/`) via GitLab Generic Package Registry
- **Why We Cannot Use GitLab Runner `cache:` for Compiler Output**:
  - **No Dotenv Variable Expansion**: In dynamic version mode, `DYNAMIC_BRAVE_VERSION` is computed at runtime in Stage 1 and exported as a dotenv artifact. GitLab CI evaluates `cache:key` **prior to job execution**, meaning dotenv variables are NOT expanded. A key like `braving-cache-${DYNAMIC_BRAVE_VERSION}` evaluates to `braving-cache-`, causing severe cross-version cache poisoning!
  - **Size and Timeout Bottlenecks**: GitLab runner cache creates a monolithic `.zip` archive on the runner and uploads it to GitLab object storage. For 5–10 GB compiler trees, zip compression and decompression take 15–20 minutes and often fail or time out.
- **The Solution: Distributed Generic Package Registry (`upload-cache.sh` & `download-cache.sh`)**:
  - Compresses the `out/Release` directory, splitting into 4.5 GB chunks (`chunk.tar.gz.*`) with SHA256 verification (`checksums.sha256`).
  - Uses GitLab's official Package Registry API authenticated via `CI_JOB_TOKEN`:
    `PKG_URL="${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/generic/braving-cache/${CACHE_VERSION}"`
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
In platform build scripts (`scripts/platforms/android/build.sh` and `scripts/platforms/windows/build.sh`), build output is piped through `filter-build-log.py`:
- **100% of Raw Output Recorded**: All lines are written unbuffered to `${WORKSPACE_DIR}/build.log` and uploaded as a CI artifact.
- **Console Throttling**: Standard Ninja/Siso progress steps (`^\[\s*(\d+)/(\d+)\]`) are throttled to every 50th step plus the first and final step (`[50/43210 (0.1%)] ...`).
- **Immediate Error Pass-Through**: **100% of non-progress lines** (compiler errors, warnings, tracebacks, notes, linker errors, diagnostic dumps) are passed through immediately to `stdout` with unbuffered flushing.
- **Post-Build Diagnostics**: `after_script` blocks in `.gitlab-ci.yml` dump the tail of `build.log`, `siso_output`, and `siso_failed_commands.sh` in an isolated collapsible section.

---

## 8. Agent Checklist & Verification Rules

Before submitting changes or proposing pull requests:
1. **Always target and validate the latest upstream release**: Develop, test, and maintain all patches, mutators, and build configs against the latest stable upstream Brave tag. Fix any upstream code shifts or patch conflicts immediately.
2. **Never make commits in `brave-core`**: Changes must live in `Braving` as mutators or scripts.
3. **Never create brittle patches**: Prefer resilient programmatic Python mutators with semantic anchors. When unified `.patch` files are used, ensure they apply cleanly without fuzz across versions.
4. **Never hardcode versions**: Ensure scripts work dynamically with auto-resolved versions.
5. **Preserve strict error handling**: Shell scripts must run under `set -euo pipefail`.
6. **Run the mandatory two-step verification suite**:
   - **Step A: Run the master verification suite**:
     ```bash
     ./scripts/core/verify-all.sh
     ```
     All 6 verification steps (manifest validation, mutator syntax & unit tests, CI automation scripts, patch retirement across trees, branding verification, orchestration dry-run) must pass cleanly.
   - **Step B: ALWAYS validate using `prepare-source.sh`**:
     ```bash
     # Auto-resolve latest upstream stable release (default):
     ./scripts/core/prepare-source.sh

     # Or validate against an explicit target version:
     ./scripts/core/prepare-source.sh "<version>"
     ```
     This executes the complete end-to-end source preparation pipeline against real upstream sources: resolving commit hashes, fetching/resetting `brave-core`, applying all git patches in `patches/`, and running all programmatic mutators (`apply-features.py --strict`, `apply-assets.sh`, and `apply-branding.py --strict`). Both verification steps must exit 0 before changes can be accepted or committed.
7. **Never write secrets into files**: API keys, tokens, or keystore passwords must be passed via environment variables.
8. **Branch Model (`release` vs `main`)**:
   - The `release` branch is the production release branch (official releases, signed APK artifacts, and release tags). It compiles all target architectures (`COMPILE_TARGET="all"`) and publishes official releases. Its GitLab Web UI prompt only requests `brave_version`.
   - The `main` branch (and other topic branches) is for active testing, integration, and development. When triggered manually in the GitLab Web UI, it provides an interactive `compile_target` input dropdown (`all`, `android`, `windows`, `windows_x64`, `windows_arm64`, no default) allowing developers to choose target compilation on demand without publishing official releases. All merge requests and development topic branches must target `main`.
9. **Enforce strict minimalism**: Keep all edits minimal, surgical, and structured. Do not introduce speculative checks, unnecessary wrapper boilerplate, or dead code. Every edit must be strictly essential.

---
**Summary for Agents:**
Think dynamically. Don't write static patches; write resilient mutators. Don't pin versions; support the flow. Reuse Brave's architecture. Support multi-platform. Keep code strictly minimalist and structured. Test against clean environments.
