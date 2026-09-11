#!/bin/bash
sed -i '/enable_brave_wallet = false/d' scripts/build-android.sh
sed -i '/enable_brave_vpn_v1 = false/d' scripts/build-android.sh
sed -i '/enable_brave_vpn_v2 = false/d' scripts/build-android.sh
sed -i '/enable_ai_chat = false/d' scripts/build-android.sh
sed -i '/enable_brave_news = false/d' scripts/build-android.sh
sed -i '/enable_brave_rewards = false/d' scripts/build-android.sh
sed -i '/enable_brave_ads = false/d' scripts/build-android.sh
sed -i '/enable_brave_talk = false/d' scripts/build-android.sh
sed -i '/enable_brave_stats_updater = false/d' scripts/build-android.sh
sed -i '/enable_web_discovery = false/d' scripts/build-android.sh
sed -i '/enable_web_discovery_native = false/d' scripts/build-android.sh
