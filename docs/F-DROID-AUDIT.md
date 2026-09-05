# F-Droid Compatibility & Reproducible Build Audit

## Executive Summary

This document evaluates the compatibility of the Brave Android codebase (v1.94.120 / Chromium 152.0.7977.76) against the current **F-Droid Inclusion Policy** and **Reproducible Builds Policy**.

F-Droid has strict requirements:
1. **Free/Libre Open Source**: All source code, libraries, build tools, and assets must be under an OSI/FSF approved free software license.
2. **Zero Proprietary Blobs / SDKs**: No Google Play Services, Firebase, proprietary analytics, closed tracking SDKs, or binary-only libraries.
3. **Offline Build Pipeline**: Builds must compile completely offline without network access during the build phase.
4. **Reproducibility**: Artifacts produced by independent clean builders must be bit-for-bit identical.

---

## Detailed Issue Classification

| Issue / Component | Upstream Source Location | Classification | Description & Resolution Strategy |
|---|---|---|---|
| **Google Play Billing SDK** | `build/android/config.gni`, `android/.../billing/` | **BLOCKER** | Proprietary library `com.android.billingclient:billing`. Used for Brave VPN & Leo subscriptions. Must be removed from GN deps and stubbed in Java. |
| **Google Play SafetyNet & Play Integrity** | `build/android/config.gni` (`google_play_services_safetynet_java`, `play_integrity_java`) | **BLOCKER** | Proprietary Google attestation APIs. Must be excised from build dependencies. |
| **Google Play Review & App Update** | `build/android/config.gni` (`play_review_java`, `play_app_update_java`) | **BLOCKER** | Proprietary Google Play Store in-app update/review APIs. Must be excised. |
| **Google Play Install Referrer** | `build/android/config.gni` (`com_android_installreferrer_java`), `AndroidManifest.xml` | **BLOCKER** | Proprietary campaign tracking SDK. Must be excised along with its manifest permission. |
| **Play Services Vision (QR Scanner)** | `android/BUILD.gn` (`qrreader_java`) | **BLOCKER** | Closed-source Google Play barcode scanner. Must be replaced with the existing open-source ZXing library. |
| **Network Downloads during Build (CIPD, depot_tools)** | `depot_tools`, `gclient sync`, `pnpm run init` | **BLOCKER (Official Core Repo)** / **SOLVABLE (Custom Repo)** | Chromium build infrastructure downloads precompiled clang, rustc, NDK, and Java dependencies via CIPD/gclient. Main F-Droid core builders cannot build standard Chromium trees. Cromite/Bromite solved this via custom F-Droid repositories and pinned pre-synced build containers. |
| **Brave Telemetry / P3A Endpoints** | `components/p3a/`, `components/misc_metrics/` | **SOLVABLE** | Violates F-Droid anti-feature guidelines (`Tracking`). Must be hard-disabled by default, endpoints nullified. |
| **Application ID & Trademark Branding** | Package name, app icons, strings | **SOLVABLE** | Must rebrand from `com.brave.browser` to `org.braving.browser` and replace all Brave logos/marks to prevent trademark infringement. |
| **Firebase / GCM / FCM Push Services** | `AndroidManifest.xml` (`c2dm.permission.RECEIVE`) | **SOLVABLE** | Brave uses its own background websocket sync and notification infrastructure; Google GCM permissions can be removed or stubbed. |
| **WireGuard Android Library** | `brave/third_party/android_deps` (`com_wireguard_android_java`) | **NO ISSUE** | Open source (Apache 2.0). However, the VPN feature itself will be disabled to reduce bloat and eliminate billing dependencies. |
| **Rust Adblock Engine (`adblock-rust`)** | `components/adblock_rust_ffi` | **NO ISSUE** | Fully open source (MPL-2.0). Compiles via standard rust toolchain. |
| **Prebuilt Jars / AARs in Chromium** | `third_party/android_deps` | **POSSIBLE BLOCKER** | Chromium vendors dozens of prebuilt Maven artifacts. Official F-Droid policy requires either building all jars from source or whitelisting approved Maven artifacts. |

---

## F-Droid Core vs. Dedicated Repository Strategy

Building modern Chromium on Android is recognized as one of the most resource-intensive compilation tasks in open source:
- Source tree footprint exceeds **80 GB**.
- RAM requirements reach **32+ GB** during linking.
- Build time can take **3 to 8 hours** on standard builder VMs.

Because the official main F-Droid build server limits worker execution time and disk limits, modern Chromium-based browsers (such as **Cromite** and **Bromite**) are distributed through **official dedicated F-Droid third-party repositories** powered by `fdroidserver`, with signed metadata and full reproducible build verification.

### Braving F-Droid Inclusion Roadmap:
1. **Milestone 1**: Clean, independent build producing an APK with zero proprietary Google Play dependencies and independent branding (`org.braving.browser`).
2. **Milestone 2**: F-Droid metadata recipe and automated `fdroid build` verification in an isolated Docker container with zero network access during the compile phase.
3. **Milestone 3**: Publication via Braving's official F-Droid repository index, followed by RFC submission to F-Droid core.
