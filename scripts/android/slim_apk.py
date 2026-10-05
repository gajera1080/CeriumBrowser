#!/usr/bin/env python3
# Copyright (c) 2026 The Braving Contributors. All rights reserved.
# Use of this source code is governed by the Mozilla Public License 2.0.
"""
Ultra-Slim APK Optimizer for Braving Browser.

Prunes secondary language pak files from universal standalone APKs to minimize
final download size for single-architecture releases (arm64-v8a). Retains core global
languages and the mandatory fallback locale (en-US).
"""

import argparse
import os
import re
import sys
import zipfile

# Core world languages retained in Ultra-Slim mode
DEFAULT_KEEP_LOCALES = {
    "en-US",
    "en-GB",
    "es",
    "es-419",
    "fr",
    "de",
    "hi",
    "zh-CN",
    "zh-TW",
    "ja",
    "pt-BR",
    "ru",
    "ar",
    "id",
}


def parse_locale_from_path(filename: str):
    """
    Extract the locale name if filename points to a language .pak file in assets.
    Returns (is_locale, locale_name, is_mandatory_fallback).
    """
    # Mandatory fallback locale must NEVER be pruned
    if filename == "assets/fallback-locales/en-US.pak":
        return True, "en-US", True

    # Pattern for Chromium / Brave locale pak files:
    # 1. assets/locales#lang_<locale>/<locale>.pak (bundletool universal output)
    # 2. assets/locales/<locale>.pak (standard APK output)
    m = re.match(r"^assets/locales#lang_([^/]+)/.*\.pak$", filename)
    if m:
        return True, m.group(1), False

    m = re.match(r"^assets/locales/([^/]+)\.pak$", filename)
    if m:
        return True, m.group(1), False

    return False, None, False


def slim_apk(input_apk: str, output_apk: str, keep_locales: set = None, prune_locales: bool = True):
    """
    Reads input_apk, prunes non-essential locale packs, and writes output_apk.
    """
    if keep_locales is None:
        keep_locales = DEFAULT_KEEP_LOCALES

    if not os.path.isfile(input_apk):
        raise FileNotFoundError(f"Input APK not found: {input_apk}")

    in_size = os.path.getsize(input_apk)
    pruned_count = 0
    pruned_bytes = 0
    total_files = 0

    temp_output = output_apk + ".tmp"
    if os.path.isfile(temp_output):
        os.remove(temp_output)

    with zipfile.ZipFile(input_apk, "r") as zin:
        with zipfile.ZipFile(temp_output, "w") as zout:
            for item in zin.infolist():
                total_files += 1
                if prune_locales:
                    is_locale, lang, is_fallback = parse_locale_from_path(item.filename)
                    if is_locale and not is_fallback:
                        if lang not in keep_locales:
                            pruned_count += 1
                            pruned_bytes += item.file_size
                            continue

                # Copy file data and preserve compression mode
                data = zin.read(item.filename)
                zout.writestr(item, data)

    if os.path.isfile(output_apk):
        os.remove(output_apk)
    os.rename(temp_output, output_apk)

    out_size = os.path.getsize(output_apk)
    saved_bytes = in_size - out_size
    saved_mb = saved_bytes / (1024 * 1024)

    print("========================================================")
    print(" Braving Ultra-Slim APK Optimization Summary")
    print("========================================================")
    print(f" Input APK     : {input_apk} ({in_size / (1024 * 1024):.2f} MB)")
    print(f" Output APK    : {output_apk} ({out_size / (1024 * 1024):.2f} MB)")
    print(f" Total files   : {total_files}")
    print(f" Pruned locales: {pruned_count} files ({pruned_bytes / (1024 * 1024):.2f} MB uncompressed)")
    print(f" Net reduction : {saved_mb:.2f} MB ({((saved_bytes / in_size) * 100):.1f}%)")
    print("========================================================")
    return saved_bytes


def main():
    parser = argparse.ArgumentParser(description="Prunes secondary language pak files to minimize APK size.")
    parser.add_argument("input_apk", help="Path to input APK file")
    parser.add_argument("output_apk", help="Path to output slimmed APK file")
    parser.add_argument(
        "--keep-locales",
        help="Comma-separated list of locale codes to keep (default: 14 core world languages)",
        default=None,
    )
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="Disable locale pruning (repackage without modification)",
    )

    args = parser.parse_args()

    keep = DEFAULT_KEEP_LOCALES
    if args.keep_locales:
        keep = set(l.strip() for l in args.keep_locales.split(",") if l.strip())

    try:
        slim_apk(args.input_apk, args.output_apk, keep_locales=keep, prune_locales=not args.no_prune)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
