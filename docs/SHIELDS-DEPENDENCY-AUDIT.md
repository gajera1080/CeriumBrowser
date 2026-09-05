# Brave Shields Minimal Dependency Audit & Proof of Necessity

## 1. Release Mode & Version Determinism

Braving operates strictly in **RELEASE MODE**:
$$\text{BRAVE\_VERSION} \longrightarrow \text{exact matching brave-core release} \longrightarrow \text{exact Chromium revision}$$

- **No arbitrary overrides**: An arbitrary commit hash cannot be mixed with a mismatched Chromium tree.
- Selecting `BRAVE_VERSION` (e.g. `1.94.120`) deterministically resolves:
  1. `brave-core` release tag: `refs/tags/v${BRAVE_VERSION}` (commit `449b91b1c032bd6c94aacd054757a97e128635b5` for 1.94.120)
  2. Chromium release tag pinned in `package.json` (`config.projects.chrome.tag`): `152.0.7977.76` (commit `0d89dfa2dd7c1ec4b8a14b9f303f887bb63b6174` for 1.94.120)
  3. `depot_tools` pinned commit in `package.json`: `81577f19a8497ba7e41afac322e8f03553a863ec`

---

## 2. Minimal Dependency Tree

The conceptual target is strictly:
```
Chromium Android Browser
   │
   ├── [Minimum Brave Code Strictly Required for Shields]
   │       ├── Adblock Engine (Rust adblock-rust + CXX bindings)
   │       ├── Filter List Infrastructure & Component Updates
   │       ├── Network Interception & Domain Throttling
   │       ├── Cosmetic Filtering & Scriptlet Injection
   │       ├── Shields Content Settings (JNI Bridge)
   │       └── Shields Android UI (Unified Panel Handler)
   │
   └── [Braving Branding & Build Code]
           ├── Package ID: org.braving.browser
           ├── Application Label: Braving
           └── Logo Assets: branding/logo.png (No Lion)
```

No Brave component is retained merely because it is a "Brave privacy feature". It must be proven necessary for Shields or Chromium.

---

## 3. Proof of Necessity for Retained Brave Components

For every retained Brave component, the exact technical justification and impact of removal is documented below:

### 3.1 Ad-Block Engine (`components/brave_shields/core/common/adblock`)
- **Source Location**: `brave/components/brave_shields/core/common/adblock`
- **Build Target**: `//brave/components/brave_shields/core/common/adblock:adblock`
- **Dependency Relationship**: Public dependency of `//brave/components/brave_shields/core/browser` and `//brave/components/brave_shields/content/browser`.
- **Why Shields Requires It**: Embeds the native Rust `adblock-rust` library via `cxx` bridges (`rs:rust_lib`, `rs:rust_lib_cxx_generated_gen`). Performs high-speed rule parsing, regex matching, cosmetic rule compilation, and network request matching against EasyList/uBlock rules.
- **What Breaks If Removed**: The ad-blocking engine fails to compile. No URLs can be matched against blocklists, and no cosmetic selectors can be computed. Shields functionality drops to zero.

### 3.2 Shields Core Common & Mojom (`components/brave_shields/core/common`)
- **Source Location**: `brave/components/brave_shields/core/common`
- **Build Target**: `//brave/components/brave_shields/core/common:common`, `//brave/components/brave_shields/core/common:mojom`
- **Dependency Relationship**: Required by `brave_shields/core/browser`, `brave_shields/content/browser`, and Chromium renderer bindings.
- **Why Shields Requires It**: Defines core Shields data structures and Mojo IPC interfaces (`ShieldsSettings`, `AdBlockMode`, `FarblingLevel`, `CookieBlockMode`, `AutoShredMode`).
- **What Breaks If Removed**: Mojo bindings between browser and renderer processes cannot generate; compilation fails in renderer content settings delegates.

### 3.3 Shields Core Browser Logic (`components/brave_shields/core/browser`)
- **Source Location**: `brave/components/brave_shields/core/browser`
- **Build Target**: `//brave/components/brave_shields/core/browser:browser`
- **Dependency Relationship**: Required by `brave_shields/content/browser` and `browser/brave_shields`.
- **Why Shields Requires It**: Implements `BraveShieldsSettingsService` (persisting user shield preferences in `PrefService`), `brave_shields_utils.cc` (per-site settings resolution and farbling calculation), and filter list catalog models.
- **What Breaks If Removed**: Per-site Shield toggles fail to persist; Shields settings cannot be resolved for active URLs; compilation fails across browser hooks.

### 3.4 Shields Content Browser & Throttles (`components/brave_shields/content/browser`)
- **Source Location**: `brave/components/brave_shields/content/browser`
- **Build Target**: `//brave/components/brave_shields/content/browser:browser`
- **Dependency Relationship**: Consumed by Chromium network interception hooks (`BraveProxyingURLLoaderFactory`) and download/navigation managers.
- **Why Shields Requires It**: Houses `AdBlockService` (runs engine matching instances), `FilterListService` (manages regional lists), `AdBlockSubscriptionServiceManager` (downloads/updates subscription lists), and `DomainBlockNavigationThrottle` (blocks full scam/malware domains).
- **What Breaks If Removed**: Outgoing network requests cannot be intercepted or blocked; filter list files cannot be loaded from disk or updated.

### 3.5 Cosmetic Filtering (`components/cosmetic_filters`)
- **Source Location**: `brave/components/cosmetic_filters`
- **Build Target**: `//brave/components/cosmetic_filters/browser:browser`, `//brave/components/cosmetic_filters/common:mojom`
- **Dependency Relationship**: Required by `BraveUnifiedPanelHandler.java` (element picker) and `BraveShieldsTabHelper`.
- **Why Shields Requires It**: Injects CSS element hiding rules to collapse blocked ad frames and prevent page layout breakage. Provides scriptlet injection to defuse anti-adblock detection scripts.
- **What Breaks If Removed**: Blocked advertisements leave broken white rectangles and empty iframe boxes across websites; anti-adblock banners lock users out of sites.

### 3.6 Brave Component Updater Bridge (`components/brave_component_updater/browser`)
- **Source Location**: `brave/components/brave_component_updater/browser`
- **Build Target**: `//brave/components/brave_component_updater/browser:browser`
- **Dependency Relationship**: Direct dependency in `components/brave_shields/core/browser/BUILD.gn` (line 45) and `components/brave_shields/content/browser/BUILD.gn` (line 51).
- **Why Shields Requires It**: Connects Brave's DAT-based filter lists and component installers to Chromium's native `component_updater`.
- **What Breaks If Removed**: Compilation fails (`#include "brave/components/brave_component_updater/browser/dat_file_util.h"` missing). Adblock DAT lists cannot be unpacked or updated.

### 3.7 Content Settings Type Extension (`components/content_settings/core/common`)
- **Source Location**: `brave/components/content_settings/core/common`
- **Build Target**: `//brave/components/content_settings/core/common:common`
- **Dependency Relationship**: Direct dependency in `components/brave_shields/core/browser/BUILD.gn` (line 49) and `components/brave_shields/content/browser/BUILD.gn` (line 57).
- **Why Shields Requires It**: Extends Chromium's native `ContentSettingsType` enum with Brave Shields content setting types (`BRAVE_SHIELDS`, `BRAVE_ADS`, `BRAVE_TRACKERS`, `BRAVE_HTTP_UPGRADABLE_RESOURCES`, `BRAVE_FINGERPRINTING_V2`, `BRAVE_SHRED`).
- **What Breaks If Removed**: Compilation fails; Chromium's `HostContentSettingsMap` cannot store or query site-specific Shields settings.

### 3.8 Webcompat Compatibility Exceptions (`components/webcompat/core/common`)
- **Source Location**: `brave/components/webcompat/core/common`
- **Build Target**: `//brave/components/webcompat/core/common:common`
- **Dependency Relationship**: Direct dependency in `components/brave_shields/core/browser/BUILD.gn` (line 53).
- **Why Shields Requires It**: Defines content setting types for site compatibility exceptions (`brave_shields_utils.cc` line 386 & 750) ensuring adblocking does not break authentication or payment gateways.
- **What Breaks If Removed**: Compilation fails in `components/brave_shields/core/browser/brave_shields_utils.cc`.

### 3.9 Blocked Domain Lifetime Tracker (`components/ephemeral_storage`)
- **Source Location**: `brave/components/ephemeral_storage`
- **Build Target**: `//brave/components/ephemeral_storage:ephemeral_storage`
- **Dependency Relationship**: Direct dependency in `components/brave_shields/content/browser/BUILD.gn` (line 58).
- **Why Shields Requires It**: `blocked_domain_1pes_lifetime.cc` in `brave_shields/content/browser` directly calls `ephemeral_storage::ClearKeepAliveForDomain()` to immediately flush storage when a domain is blocked by Shields.
- **What Breaks If Removed**: Compilation fails in `components/brave_shields/content/browser/blocked_domain_1pes_lifetime.cc`.

### 3.10 HTTPS Upgrade Exceptions (`components/https_upgrade_exceptions/browser`)
- **Source Location**: `brave/components/https_upgrade_exceptions/browser`
- **Build Target**: `//brave/components/https_upgrade_exceptions/browser:browser`
- **Dependency Relationship**: Direct dependency in `components/brave_shields/core/browser/BUILD.gn` (line 50) and `components/brave_shields/content/browser/BUILD.gn` (line 59).
- **Why Shields Requires It**: Manages host exception lists for HTTP sites when the Shields "Upgrade connections to HTTPS" toggle is enabled.
- **What Breaks If Removed**: Compilation fails in `components/brave_shields/core/browser/ad_block_service_helper.cc` and `components/brave_shields/content/browser/ad_block_service.cc`.

### 3.11 Android JNI Bridge & Event Observer (`browser/brave_shields` & `browser/android`)
- **Source Location**: `brave/browser/brave_shields` & `brave/browser/android/brave_shields_content_settings.cc`
- **Build Target**: `//brave/browser:browser` (Android target)
- **Dependency Relationship**: Bridges Chromium WebContents and Android Java layer.
- **Why Shields Requires It**:
  - `brave_shields_web_contents_observer_android.cc`: Listens to URL request blocking events in Chromium WebContents and sends `DispatchBlockedEvent` to Android Java.
  - `brave_shields_content_settings.cc`: Implements native JNI entry points for `BraveShieldsContentSettings.java`.
- **What Breaks If Removed**: Android Java Shields panel cannot read or write site shields settings; live tracker/ad blocked badge counts remain 0.

### 3.12 Android Shields Java UI (`android/java/org/chromium/chrome/browser/shields`)
- **Source Location**: `brave/android/java/org/chromium/chrome/browser/shields`
- **Build Target**: `//brave/android:brave_java`
- **Dependency Relationship**: Included in `brave_chrome_java_deps` in `build/android/config.gni`.
- **Why Shields Requires It**: Provides the user interface: `BraveUnifiedPanelHandler.java` (the shields bottom sheet popup), `BraveShieldsContentSettings.java`, and filter list settings fragments.
- **What Breaks If Removed**: User has no UI on Android to toggle Shields, change aggressiveness, view blocked trackers, or manage filter lists.

---

## 4. Components Formally Proven NOT Required by Shields (Disabled/Removed)

The following Brave components are **strictly excluded** because they have zero technical relationship to Brave Shields:

| Component | Status | Proof / Technical Rationale |
|---|---|---|
| **brave_wallet / brave_wallet_ui / filecoin** | **REMOVED** | Zero symbols referenced in `brave_shields`. Crypto Web3 Ethereum/Solana wallet. |
| **brave_rewards** | **REMOVED** | Zero symbols referenced in `brave_shields`. BAT tipping, user ledger, and custodial wallets. |
| **brave_ads** | **REMOVED** | Zero symbols referenced in `brave_shields`. Commercial ad server and system notifications. |
| **brave_vpn** | **REMOVED** | Zero symbols referenced in `brave_shields`. WireGuard tunnel client and payment gate. |
| **ai_chat (Leo) / local_ai** | **REMOVED** | Zero symbols referenced in `brave_shields`. LLM conversational UI and on-device models. |
| **brave_news** | **REMOVED** | Zero symbols referenced in `brave_shields`. Today RSS feed and publisher ranking. |
| **brave_talk** | **REMOVED** | Zero symbols referenced in `brave_shields`. WebRTC 8x8 video meeting integration. |
| **brave_stats** | **REMOVED** | Pings usage telemetry to `usage-ping.brave.com`. Excluded via `enable_brave_stats_updater=false`. |
| **p3a / p3a_utils** | **REMOVED** | Product telemetry. Disabled via `kP3AEnabled=false` pref patch. |
| **web_discovery** | **REMOVED** | Search indexing telemetry. Excluded via `enable_web_discovery=false`. |
| **webcompat_reporter** | **REMOVED** | Telemetry issue submission endpoint. Disabled. |
| **de_amp** | **REMOVED** | Independent AMP rewrite. Not required by Shields. |
| **debounce** | **REMOVED** | Independent bounce tracking un-shortener. Not required by Shields. |
| **query_filter** | **REMOVED** | Independent query stripper. Not required by Shields. |
| **global_privacy_control** | **REMOVED** | Independent header injector. Not required by Shields. |
| **brave_account** | **REMOVED** | Brave sync/cloud authentication. Not required by Shields. |
| **skus** | **REMOVED** | Subscription payments client for VPN/Leo. Not required by Shields. |
| **ntp_background_images** | **REMOVED** | Sponsored New Tab wallpaper ads. Not required by Shields. |
