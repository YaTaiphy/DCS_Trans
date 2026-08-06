"""
Translation Rollback

Removes translated l10n/CN/dictionary entries from .miz archives,
restoring missions to their original English-only state.
Also cleans up intermediate files created during translation.
"""

import os
import zipfile
import shutil


def _remove_entry_from_zip(zip_path, entry_name):
    """
    Remove a single entry from a ZIP file by rebuilding it.
    Returns True if the entry was found and removed.
    """
    if not os.path.exists(zip_path):
        return False

    # Check if entry exists
    with zipfile.ZipFile(zip_path, 'r') as zf:
        if entry_name not in zf.namelist():
            return False
        # Read all entries except the one to remove
        entries = [
            (info.filename, zf.read(info.filename))
            for info in zf.infolist()
            if info.filename != entry_name and not info.is_dir()
        ]

    if not entries:
        return False  # Nothing left — should not happen

    # Rebuild ZIP without the entry
    tmp_path = zip_path + ".tmp"
    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf_out:
            for name, data in entries:
                zf_out.writestr(name, data)
        # Atomic replace
        shutil.move(tmp_path, zip_path)
        return True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def rollback_miz(miz_path):
    """
    Rollback translations for all .miz files in a directory.

    For each .miz:
      1. Remove l10n/CN/dictionary from the archive
      2. Delete intermediate .miz.json and _translateRef.json files

    Args:
        miz_path: Directory containing .miz files

    Returns:
        (rolled_back: int, skipped: int) counts
    """
    # Find .miz files (reuse extract_miz helper)
    from util.extract_miz import get_files

    file_list = get_files(miz_path)

    if not file_list:
        print(f"No .miz files found in: {miz_path}")
        return 0, 0

    cn_entry = "l10n/CN/dictionary"
    rolled_back = 0
    skipped = 0

    for miz_file in file_list:
        basename = os.path.basename(miz_file)

        # Remove CN dictionary from .miz
        if _remove_entry_from_zip(miz_file, cn_entry):
            print(f"  Rolled back: {basename}")
            rolled_back += 1
        else:
            print(f"  No CN translation found: {basename}")
            skipped += 1

        # Clean up intermediate files
        json_file = miz_file + ".json"
        ref_file = os.path.splitext(miz_file)[0] + "_translateRef.json"

        for cleanup in [json_file, ref_file]:
            if os.path.exists(cleanup):
                os.remove(cleanup)
                print(f"    Cleaned: {os.path.basename(cleanup)}")

    print(f"\nRollback complete: {rolled_back} restored, {skipped} skipped")
    return rolled_back, skipped
