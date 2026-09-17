# Braving Android — System Architecture

## Architecture Diagram

```
User selects BRAVE_VERSION (e.g. <BRAVE_VERSION>)
              ↓
  Resolve matching brave-core release
      (tag: refs/tags/v<BRAVE_VERSION> / commit: 449b91b1c032bd6c94aacd054757a97e128635b5)
              ↓
  Resolve exact Chromium revision
      (tag: 152.0.7977.76 / commit: 0d89dfa2dd7c1ec4b8a14b9f303f887bb63b6174)
              ↓
  Apply Braving Mutators
      ├── branding/ (app name, launcher label, package ID: org.braving.browser)
      ├── build/    (android_defaults.gni feature exclusions)
      └── telemetry/ (disable P3A analytics and metrics reporting)
              ↓
  Braving Android Source Tree
              ↓
  Hermetic / Reproducible Build Engine (GN + Ninja)
              ↓
  Braving APK (Target: arm64-v8a / monobuild)
```

---

## Component Separation

1. **Braving Repository (`<BRAVING_DIR>`)**:
   - Contains zero giant upstream source blobs.
   - Hosts metadata, python mutators (e.g. apply-branding.py), build scripts, tests, CI pipelines, and branding resources.
   - Keeps git history small, auditable, and fast to clone.

2. **brave-core (`src/brave`)**:
   - Upstream Brave Core customizations and native modules.
   - Checked out at exact pinned commit.
   - Mutated in-place by Braving preparation scripts before compilation.

3. **Chromium (`src`)**:
   - The Chromium upstream browser engine checked out at the exact milestone and commit referenced in brave-core's `package.json`.

4. **Mutators (`programmatic mutators (e.g. apply-branding.py)`)**:
   - Python mutators (e.g. apply-branding.py) modify code programmatically.
   - Fail loudly if upstream shifts unexpectedly, ensuring build integrity.
