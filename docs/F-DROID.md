# F-Droid Integration Guide & Recipe

## 1. Compatibility Status

Braving is architected to achieve complete compatibility with F-Droid's Free Software policies:
- **Application ID**: `org.braving.browser`
- **Branding**: Independently owned assets and trademarks ("Braving")
- **License**: Mozilla Public License 2.0 (MPL-2.0) for Braving and Brave Core modifications; BSD-3-Clause for Chromium.
- **Proprietary SDKs**: Excised via Braving patches (`patches/f-droid/0001-gate-google-play-dependencies.patch`).

---

## 2. Known Blockers & Resolutions

| Issue | Severity | Status in Braving |
|---|---|---|
| **Google Play Billing** | Blocker | Removed via `enable_play_services = false`. |
| **Play Integrity / SafetyNet** | Blocker | Excised from GN dependencies. |
| **Play App Update & Review** | Blocker | Excised from GN dependencies. |
| **Play Services Vision** | Blocker | Replaced with bundled open-source ZXing engine. |
| **Network access during compile** | Blocker for main F-Droid VMs | Solved via dedicated F-Droid third-party repository and pre-synced Docker build container (standard model used by Cromite and Bromite). |

---

## 3. F-Droid Build Recipe

The following metadata recipe is structured for `fdroidserver`:

```yaml
Categories:
  - Internet
License: MPL-2.0
SourceCode: https://gitlab.com/braving/braving
IssueTracker: https://gitlab.com/braving/braving/-/issues

AutoUpdateMode: None
UpdateCheckMode: Tags

Builds:
  - versionName: 1.94.120
    versionCode: 194120
    commit: v1.94.120
    subdir: Braving
    target: arm64
    build:
      - ./scripts/prepare-source.sh 1.94.120
      - ./scripts/build-android.sh --manifest=metadata/releases/1.94.120.yaml --arch=arm64 --release
    output: out/apks/Braving-1.94.120-arm64.apk

AutoName: Braving
Summary: Privacy-respecting Android browser based on Brave without telemetry or proprietary SDKs
Description: |-
  Braving is an independent, community-driven fork of the Brave Android browser.
  It preserves powerful tracking and ad blocking (Shields) while completely
  stripping all proprietary Google Play dependencies, cryptocurrency wallet
  modules, advertising rewards, and telemetry.
```

---

## 4. Reproducibility Status

Braving enforces deterministic build parameters:
- `disable_fieldtrial_testing_config = true`
- Fixed timestamps and pinned source revisions
- Normalized build output paths
- Comparative verification script: `scripts/verify-reproducibility.sh`
