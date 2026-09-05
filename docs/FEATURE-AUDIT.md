# Brave Android Feature Audit (Version 1.94.120)

## Overview

This document presents the detailed architectural and feature audit of the Android implementation in `brave-core` at release `1.94.120` (paired with Chromium `152.0.7977.76`).

The goal of this audit is to identify all Brave-specific services, components, proprietary SDKs, and third-party integrations, classifying each according to whether it should be kept, disabled, or removed for Braving.

---

## Classification Summary

| Component / Feature | Category | Rationale |
|---|---|---|
| **Brave Shields (Adblock & Tracking Protection)** | **KEEP** | Essential core privacy functionality. Powered by `adblock-rust-ffi`. |
| **Brave Sync** | **KEEP** | Client-side encrypted sync infrastructure; does not rely on Google Sync. |
| **Brave Search Integration** | **KEEP** | Default search engine provider, clean Web standards integration. |
| **Brave Rewards (BAT / Ads Earning)** | **DISABLE** | Cryptocurrency reward tokens, sponsored backgrounds, user verification. |
| **Brave Ads (Sponsored Notifications / Inline)** | **DISABLE** | Sponsored push ads and promotional placement engines. |
| **Brave Wallet (Web3 / Crypto Wallet)** | **DISABLE** | Built-in cryptocurrency wallet and DApps browser infrastructure. |
| **Brave VPN (WireGuard / Guardian)** | **DISABLE** | Commercial subscription VPN service; tied to Google Play In-App Billing. |
| **Brave Leo (AI Chat)** | **DISABLE** | Cloud LLM conversational assistant. |
| **Brave News (Feed)** | **DISABLE** | Content aggregator feed. |
| **Brave Telemetry / P3A (Privacy-Preserving Analytics)** | **REMOVE** | Telemetry metrics uploaded to Brave analytics endpoints. |
| **Promotional Onboarding & Engagement Callouts** | **REMOVE** | Callouts prompting users to enable Rewards, VPN, Leo, or default browser. |
| **Google Play Billing SDK** | **DISABLE** | Closed-source billing library (`billingclient`). |
| **Google Play Services Vision** | **REMOVE** | Proprietary barcode/QR scanner; replace with bundled open-source ZXing. |
| **Google Play Services SafetyNet & Integrity** | **REMOVE** | Closed-source Google device integrity attestation SDKs. |
| **Google Play Review & App Update SDKs** | **REMOVE** | Closed-source Play Store update/rating dialogs. |
| **Android Install Referrer SDK** | **REMOVE** | Closed-source Play Store campaign attribution library. |
| **Origin Switch Architecture** | **NEEDS INVESTIGATION** | Upstream asserts `!(is_brave_origin_branded && is_android)`. Origin must be adapted. |

---

## Detailed Component Audit for DISABLE / REMOVE Items

### 1. Brave Rewards
- **Classification**: `DISABLE` (Milestone 1) / `REMOVE`
- **1. Source Location**:
  - `src/brave/components/brave_rewards/`
  - `src/brave/android/java/org/chromium/chrome/browser/BraveRewardsHelper.java`
  - `src/brave/android/java/org/chromium/chrome/browser/BraveRewardsNativeWorker.java`
  - `src/brave/android/java/org/chromium/chrome/browser/BraveRewardsObserver.java`
  - `src/brave/android/java/org/chromium/chrome/browser/BraveRewardsPolicy.java`
  - `src/brave/android/java/org/chromium/chrome/browser/BraveRewardsBalance.java`
- **2. Build-System Integration**:
  - `enable_brave_rewards` flag declared in `components/brave_rewards/common/buildflags/buildflags.gni`.
- **3. Java/Kotlin References**:
  - `BraveRewardsNativeWorker.java` provides JNI binding to native rewards engine.
  - Referenced in `BraveActivity.java` for UI icon and balance display.
- **4. Native/C++ References**:
  - `brave/components/brave_rewards/browser/`
  - Registered in `brave_browser_process_impl.cc`.
- **5. Resources**:
  - Drawables: `ic_bat.xml`, `brave_rewards_*.xml` in `android/java/brave-res/`.
- **6. Gradle Dependencies**: None directly (compiled via Chromium GN/ninja).
- **7. GN Dependencies**:
  - `//brave/components/brave_rewards/core/mojom:mojom_java` in `build/android/config.gni`.
  - `brave_jni_headers_sources` entry in `build/android/config.gni`.
- **8. Runtime Registration**:
  - Initialized on profile creation in `BraveRewardsNativeWorker.init()`.
- **9. Transitive Dependencies**:
  - `components/brave_ads`, `bat-native-ledger`, `bat-native-rapidjson`.
- **10. Tests Affected**:
  - `BraveRewardsNativeWorkerTest.java`, `BraveRewardsUnitTest.cc`.

---

### 2. Brave Ads
- **Classification**: `DISABLE`
- **1. Source Location**:
  - `src/brave/components/brave_ads/`
  - `src/brave/browser/brave_ads/android/java_sources.gni`
  - `src/brave/browser/brave_ads/android/java/org/chromium/chrome/browser/BraveAdsNativeHelper.java`
- **2. Build-System Integration**:
  - `enable_brave_ads` GN argument in `components/brave_ads/buildflags/buildflags.gni`.
- **3. Java/Kotlin References**:
  - `BraveAdsNativeHelper.java`, `brave_ads_java_sources`.
- **4. Native/C++ References**:
  - `brave/components/brave_ads/browser/ads_service_factory.cc`.
- **5. Resources**:
  - Notification layouts and icons in `android/java/brave-res/drawable/ic_ad_notification.xml`.
- **6. Gradle Dependencies**: None.
- **7. GN Dependencies**:
  - `//brave/components/brave_ads/core/mojom:mojom_java` in `build/android/config.gni`.
- **8. Runtime Registration**:
  - KeyedService attached to BrowserContext.
- **9. Transitive Dependencies**:
  - Network state observer, notification manager.
- **10. Tests Affected**:
  - `BraveAdsNativeHelperTest.java`.

---

### 3. Brave Crypto Wallet (Web3)
- **Classification**: `DISABLE`
- **1. Source Location**:
  - `src/brave/components/brave_wallet/`
  - `src/brave/android/java/org/chromium/chrome/browser/crypto_wallet/`
  - `src/brave/android/java/org/chromium/chrome/browser/BraveWalletProvider.java`
- **2. Build-System Integration**:
  - `enable_brave_wallet` GN argument in `components/brave_wallet/common/buildflags/buildflags.gni`.
- **3. Java/Kotlin References**:
  - `BraveWalletActivity.java`, `AddAccountActivity.java`, `NetworkSelectorActivity.java`, `AccountSelectorActivity.java`, `AdvanceTxSettingActivity.java`, `BraveWalletDAppsActivity.java`.
- **4. Native/C++ References**:
  - `brave_wallet::BraveWalletServiceFactory`, `brave_wallet::KeyringService`.
- **5. Resources**:
  - Extensive wallet layouts, color selectors, and icons in `android/java/brave-res/` (e.g. `wallet_*.xml`, `crypto_wallet_*.xml`).
- **6. Gradle Dependencies**: None.
- **7. GN Dependencies**:
  - Conditionally loaded in `build/android/config.gni`:
    ```gn
    if (enable_brave_wallet) {
      brave_chrome_java_deps += [ "//brave/components/brave_wallet/common:mojom_java" ]
    }
    ```
- **8. Runtime Registration**:
  - Manifest activities registered in `android/java/AndroidManifest.xml`.
- **9. Transitive Dependencies**:
  - Ethereum / Solana crypto libraries, BIP39, Web3 provider scripts.
- **10. Tests Affected**:
  - `BraveWalletServiceUnitTest.cc`, `BraveWalletActivityTest.java`.

---

### 4. Brave VPN (WireGuard / Guardian)
- **Classification**: `DISABLE`
- **1. Source Location**:
  - `src/brave/components/brave_vpn/`
  - `src/brave/android/java/org/chromium/chrome/browser/vpn/`
- **2. Build-System Integration**:
  - `enable_brave_vpn` in `components/brave_vpn/common/buildflags/buildflags.gni`.
- **3. Java/Kotlin References**:
  - `WireguardService.java`, `BraveVpnNativeWorker.java`, `BraveVpnProfileActivity.java`, `VpnPaywallActivity.java`.
- **4. Native/C++ References**:
  - `brave_vpn::BraveVpnServiceFactory`.
- **5. Resources**:
  - `Theme.Brave.VpnProfile`, VPN status icons and strings.
- **6. Gradle Dependencies**: None.
- **7. GN Dependencies**:
  - `//brave/third_party/android_deps:com_wireguard_android_java` in `brave_java_base_module_deps`.
  - `//brave/components/brave_vpn/common/mojom:mojom_java` in `build/android/config.gni`.
- **8. Runtime Registration**:
  - Android VpnService registered in `android/java/AndroidManifest.xml`: `com.wireguard.android.backend.GoBackend$VpnService`.
- **9. Transitive Dependencies**:
  - WireGuard native library (.so), Google Play Billing (for subscription paywall).
- **10. Tests Affected**:
  - `BraveVpnServiceTest.java`.

---

### 5. Brave Leo (AI Chat)
- **Classification**: `DISABLE`
- **1. Source Location**:
  - `src/brave/components/ai_chat/`
  - `src/brave/android/java/org/chromium/chrome/browser/brave_leo/`
- **2. Build-System Integration**:
  - `enable_ai_chat` in `components/ai_chat/core/common/buildflags/buildflags.gni`.
- **3. Java/Kotlin References**:
  - `BraveLeoPlansActivity.java`, `BraveLeoMojomHelper.java`, `BraveLeoUtils.java`.
- **4. Native/C++ References**:
  - `ai_chat::AIChatServiceFactory`.
- **5. Resources**:
  - Leo theme, chat icons, subscription dialogs.
- **6. Gradle Dependencies**: None.
- **7. GN Dependencies**:
  - `//brave/components/ai_chat/core/common/mojom:mojom_java` in `build/android/config.gni`.
- **8. Runtime Registration**:
  - Activity in `android/java/AndroidManifest.xml`.
- **9. Transitive Dependencies**:
  - In-App Purchase wrapper for Leo Premium subscription.
- **10. Tests Affected**:
  - `BraveLeoUtilsTest.java`.

---

### 6. Google Play SDKs & Proprietary Dependencies

#### 6.1 Google Play In-App Billing Client
- **Source / Dependency**: `//brave/third_party/android_deps:com_android_billingclient_java`
- **Build Integration**: `brave_app_billing_deps` in `build/android/config.gni` and `brave_app_billing_sources`.
- **Java References**: `InAppPurchaseWrapper.java`, `LinkSubscriptionUtils.java`, `PurchaseModel.java`.
- **Action**: REMOVE. Exclude `brave_app_billing_deps` from `build/android/config.gni`, stub Java billing wrapper.

#### 6.2 Google Play Services Vision (Barcode/QR)
- **Source / Dependency**: `//third_party/android_deps:google_play_services_vision_java`
- **Build Integration**: `android/BUILD.gn:qrreader_java`.
- **Java References**: `BarcodeTracker.java`, `QRCodeCameraManager.java`.
- **Action**: REPLACE. Divert barcode reading to open-source ZXing (`//brave/third_party/zxing:zxing_java`).

#### 6.3 Google Play SafetyNet & Integrity
- **Source / Dependency**: `google_play_services_safetynet_java`, `com_google_android_play_integrity_java`.
- **Build Integration**: Included in `brave_chrome_java_deps` in `build/android/config.gni`.
- **Java References**: Safety check utils, attestation bridges.
- **Action**: REMOVE. Exclude from `build/android/config.gni`.

#### 6.4 Google Play In-App Review & Update
- **Source / Dependency**: `com_google_android_play_review_java`, `com_google_android_play_app_update_java`.
- **Build Integration**: Included in `brave_chrome_java_deps`.
- **Java References**: Update dialogs and prompt handlers.
- **Action**: REMOVE. Exclude from `build/android/config.gni`.

#### 6.5 Android Install Referrer
- **Source / Dependency**: `com_android_installreferrer_java`.
- **Build Integration**: Included in `brave_chrome_java_deps` and `AndroidManifest.xml` permission.
- **Action**: REMOVE. Exclude from `build/android/config.gni` and remove `com.google.android.finsky.permission.BIND_GET_INSTALL_REFERRER_SERVICE` from `AndroidManifest.xml`.
