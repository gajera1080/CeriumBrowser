#!/usr/bin/env bash
# Cerium — Patch Application & Verification Engine
# Applies or validates the Cerium patch set against a target repository.
# Applies cross-platform patches (patches/common) first, followed by platform patches.
# Supports clean forward application, strict idempotency (reverse-check),
# and -C1 fuzzy context fallback across upstream version bumps.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PATCH_DIR="${REPO_ROOT}/patches"

TARGET_DIR=""
CHECK_ONLY=false

for arg in "$@"; do
  case "${arg}" in
    --check)
      CHECK_ONLY=true
      ;;
    --*)
      echo "ERROR: Unknown option: ${arg}" >&2
      exit 1
      ;;
    *)
      if [[ -n "${TARGET_DIR}" ]]; then
        echo "ERROR: Only one target git directory may be specified." >&2
        exit 1
      fi
      TARGET_DIR="${arg}"
      ;;
  esac
done

if [[ -z "${TARGET_DIR}" ]]; then
  echo "Usage: $0 <target-git-directory> [--check]" >&2
  exit 1
fi

if [[ ! -d "${TARGET_DIR}/.git" ]]; then
  echo "ERROR: Target directory is not a git repository: ${TARGET_DIR}" >&2
  exit 1
fi

if [[ ! -d "${PATCH_DIR}" ]]; then
  echo "No patches directory found at ${PATCH_DIR}."
  exit 0
fi

PATCHES=()

# 1. Common core patches first
if [[ -d "${PATCH_DIR}/common" ]]; then
  while IFS= read -r -d $'\0' file; do
    PATCHES+=("$file")
  done < <(find "${PATCH_DIR}/common" -name "*.patch" -print0 | sort -z)
fi

# 2. Platform-specific patches
while IFS= read -r -d $'\0' file; do
  [[ "$file" == "${PATCH_DIR}/common/"* ]] && continue
  PATCHES+=("$file")
done < <(find "${PATCH_DIR}" -name "*.patch" -print0 | sort -z)

if [[ ${#PATCHES[@]} -eq 0 ]]; then
  echo "No patches found in ${PATCH_DIR} (all modifications handled via mutators)."
  exit 0
fi

for patch in "${PATCHES[@]}"; do
  pname="${patch#${PATCH_DIR}/}"

  if [[ "${CHECK_ONLY}" == "true" ]]; then
    if git -C "${TARGET_DIR}" apply --check "$patch" 2>/dev/null || \
       git -C "${TARGET_DIR}" apply --check --reverse "$patch" 2>/dev/null || \
       git -C "${TARGET_DIR}" apply -C1 --check "$patch" 2>/dev/null || \
       git -C "${TARGET_DIR}" apply -C1 --check --reverse "$patch" 2>/dev/null; then
      echo "      [PASS] ${pname} applies cleanly"
    else
      echo "      [FAIL] ${pname} failed to apply to ${TARGET_DIR}" >&2
      git -C "${TARGET_DIR}" apply --check -v "$patch" >&2 || true
      exit 1
    fi
  else
    echo " - Applying ${pname}..."
    if git -C "${TARGET_DIR}" apply --check --reverse "$patch" 2>/dev/null || \
       git -C "${TARGET_DIR}" apply -C1 --check --reverse "$patch" 2>/dev/null; then
      echo "   [OK] Patch ${pname} already applied."
    elif git -C "${TARGET_DIR}" apply --check "$patch" 2>/dev/null; then
      git -C "${TARGET_DIR}" apply "$patch"
      echo "   [OK] Patch ${pname} successfully applied."
    elif git -C "${TARGET_DIR}" apply -C1 --check "$patch" 2>/dev/null; then
      git -C "${TARGET_DIR}" apply -C1 "$patch"
      echo "   [OK] Patch ${pname} successfully applied (with -C1 context)."
    else
      echo "ERROR: Patch ${pname} failed to apply and is not already applied. Aborting to fail closed." >&2
      git -C "${TARGET_DIR}" apply --check -v "$patch" >&2 || true
      exit 1
    fi
  fi
done
