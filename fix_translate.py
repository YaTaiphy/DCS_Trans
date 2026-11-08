#!/usr/bin/env python3
"""
Translation Fix Tool

After manually editing _translateRef.json files to correct translations,
run this tool to merge the corrections into the consolidated cache.

The consolidated cache (./cache/translated.json) can be used as a reference
for future translation runs to avoid repeating the same mistakes.

Usage:
    python fix_translate.py /path/to/missions
"""

import os
import sys
import json


# ---------------------------------------------------------------------------
# Path resolution (mirrors util/config.py — avoids circular import)
# ---------------------------------------------------------------------------
def _is_bundled():
    if getattr(sys, 'frozen', False):
        return True
    exe_name = os.path.basename(sys.executable).lower()
    return not exe_name.startswith('python')


def _get_app_root():
    if _is_bundled():
        return os.path.dirname(sys.executable)
    return os.getcwd()


def _get_cache_dir():
    return os.path.join(_get_app_root(), "cache")


def find_translate_ref_files(folder_path):
    """Find all _translateRef.json files in the given directory tree."""
    ref_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith("_translateRef.json"):
                ref_files.append(os.path.join(root, file))
    return ref_files


def merge_translations(ref_files, output_path=None):
    """
    Merge all translation reference files into a consolidated cache.
    For conflicting keys, the value from the reference file takes precedence.
    """
    if output_path is None:
        output_path = os.path.join(_get_cache_dir(), "translated.json")
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Load existing consolidated cache
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            consolidated = json.load(f)
    else:
        consolidated = {}

    # Track which keys have been updated in this run
    updated_keys = set()

    # Merge each reference file
    for ref_file in ref_files:
        with open(ref_file, "r", encoding="utf-8") as f:
            current = json.load(f)
            for key, value in current.items():
                if key in consolidated and value != consolidated[key] and key not in updated_keys:
                    consolidated[key] = value
                    updated_keys.add(key)
                elif key not in consolidated:
                    consolidated[key] = value

    # Write back
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, ensure_ascii=False, indent=4)

    print(f"Merged {len(ref_files)} reference file(s) into {output_path}")
    print(f"Total entries: {len(consolidated)}, Updated: {len(updated_keys)}")
    return consolidated


def fix_translate(folder_path):
    """Main entry point for the fix-translate workflow."""
    if not os.path.isdir(folder_path):
        print(f"Error: Path does not exist or is not a directory: {folder_path}")
        sys.exit(1)

    ref_files = find_translate_ref_files(folder_path)
    print(f"Found {len(ref_files)} _translateRef.json file(s):")
    for f in ref_files:
        print(f"  {f}")

    if not ref_files:
        print("No translation reference files found. Nothing to do.")
        return

    merge_translations(ref_files)
    print("Translation fix complete!")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = input("Enter mission folder path: ").strip()

    fix_translate(folder_path)
