# Braving Project: Canonical Agent Instructions

Welcome, agent. This document outlines the architectural vision, constraints, and core principles of the **Braving** project. Read this carefully before making any modifications, proposing plans, or writing code.

## 1. Project Overview
Braving is a customized, de-branded, and modified downstream distribution of the Brave Browser. It is designed to be built dynamically against upstream Brave releases, without maintaining a massive hard-forked Git repository.

## 2. Ephemeral Upstream & The Dynamic Flow
**CRITICAL RULE: Do NOT make permanent direct commits in the `brave-core` repository.**
- The `brave-core` and `chromium` directories are treated as **ephemeral, dynamic build artifacts**. They are fetched at build time.
- If you make a manual change in `brave-core` for testing, you MUST extract that change into a programmatic mutator script stored in the **Braving** repository. The CI will clone a fresh upstream and will not see your local `brave-core` commits.
- **The build flow MUST be version-independent.**
- If `BRAVE_VERSION` is empty in CI/CD, the build system automatically fetches the latest stable release from the GitHub API.
- **Do not hardcode versions** (e.g., `1.94.120`) in CI configs or ignore files to "fix" a build. The pipeline is designed to roll forward with upstream.
- Metadata (`metadata/releases/` and `metadata/upstream/`) is generated dynamically by the preparation scripts and should not be tracked in git as static files.

## 3. Modification Strategy: Programmatic Mutations
**CRITICAL RULE: Avoid standard `git diff` `.patch` files.**
- Standard unified diffs are brittle. They rely on exact line numbers and context. When upstream Brave bumps a version (e.g., `1.94` $\to$ `1.95`), lines shift, and `git apply` fails, breaking the dynamic CI flow.
- **Use Programmatic Python Mutators** instead (e.g., `scripts/apply-branding.py`, `enforce-policies.py`). These scripts read files, find semantic anchors (e.g., method signatures, class names, specific variable declarations), and perform string replacement or AST-like injections.
- If you need to introduce a new modification to upstream code, write a script in the Braving repo that injects the logic resiliently, rather than committing directly to `brave-core` or creating a `.patch` file.

## 4. Resource Management & Offline Assets
- Braving includes custom static assets (like branding in `branding/`). These must be tracked in the Braving Git repository.
- **Offline Adblock Rules:** Do not track static adblock lists in Git. The CI pipeline (`prepare-source.sh`) dynamically downloads the latest uBlock Origin default lists (EasyList, EasyPrivacy, Peter Lowe, etc.) at build time.
- During `prepare-source.sh` and `apply-assets.sh`, resources are copied into the dynamically generated `build-workspace/src/brave/` tree. Always use `mkdir -p` to ensure target directories exist before copying.

## 5. Architectural Reuse (No Parallel Engines)
- **Do not reinvent the wheel.** If Brave has an existing system (e.g., `AdBlockComponentServiceManager`, `AdBlockEngine`), reuse it. 
- If you need custom behavior (like offline adblock fallback), hook into the existing system's fallback/failure paths rather than building a parallel custom engine.
- Keep modifications asynchronous and non-blocking to the main browser thread.

## 6. Branding & Bloat Removal
- **De-branding:** Completely eliminate Brave Lion branding across the app (launcher, splash screens, adaptive icons, themed XMLs, and UI strings). Braving uses its own branding generated via `generate-icons.sh`.
- **Debloating:** Prune unnecessary UI elements, VPN upsells, Crypto wallets, and telemetry via the Python mutation scripts (`prune-ui.py`, `enforce-policies.py`).

## 7. CI/CD Environment
- The GitLab CI pipeline runs in a clean Debian container. 
- Scripts run with `set -euo pipefail`. Any missing file, undefined variable, or failed command (like `git apply`) will instantly crash the pipeline. Ensure all references point to files actually committed in the Git repository.

---
**Summary for Agents:** 
Think dynamically. Don't write static patches; write resilient mutators. Don't pin versions; support the flow. Reuse Brave's architecture. Test your assumptions against a clean, untracked environment.
