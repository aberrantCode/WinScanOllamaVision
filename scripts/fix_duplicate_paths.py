r"""
Fix duplicate file entries caused by inconsistent path separators.

Windows allows both forward slashes (/) and backslashes (\) in paths,
but SQLite treats them as different strings. This script normalizes
all paths to use backslashes consistently.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db.analysis_db import AnalysisDB
from db.image_status import ImageStatus
from services.logging_service import LoggingService


def normalize_path(path: str) -> str:
    """Normalize path to use consistent separators (backslashes on Windows)."""
    return os.path.normpath(path)


def fix_duplicate_paths(dry_run: bool = True):
    """
    Find and merge duplicate file entries with inconsistent path separators.

    Args:
        dry_run: If True, only report what would be fixed without making changes
    """
    db = AnalysisDB()
    conn = db.connection.connection
    cursor = conn.cursor()  # type: ignore[attr-defined]

    # Get all non-deleted files
    cursor.execute('SELECT id, file_path, status FROM image_files WHERE status != "deleted"')
    all_files = cursor.fetchall()

    print(f"Checking {len(all_files)} files for path inconsistencies...")

    # Group files by normalized path
    normalized_map: dict[
        str, list[tuple[int, str, str]]
    ] = {}  # normalized_path -> list of (id, original_path, status)

    for file_id, file_path, status in all_files:
        normalized = normalize_path(file_path)
        if normalized not in normalized_map:
            normalized_map[normalized] = []
        normalized_map[normalized].append((file_id, file_path, status))

    # Find duplicates
    duplicates_found = 0
    files_to_delete = []

    for normalized_path, file_entries in normalized_map.items():
        if len(file_entries) > 1:
            duplicates_found += 1
            print(f"\nDuplicate found for: {normalized_path}")
            print(f"  {len(file_entries)} entries:")

            # Keep the entry that matches the normalized path, or the first one
            keep_entry = None
            for entry_id, original_path, status in file_entries:
                if original_path == normalized_path:
                    keep_entry = (entry_id, original_path, status)
                    break

            if not keep_entry:
                # None match normalized, keep the first one
                keep_entry = file_entries[0]

            print(f"  KEEP: id={keep_entry[0]}, path={keep_entry[1]}")

            for entry_id, original_path, _ in file_entries:
                if entry_id != keep_entry[0]:
                    print(f"  DELETE: id={entry_id}, path={original_path}")
                    files_to_delete.append(entry_id)

    print(f"\n{'='*70}")
    print("Summary:")
    print(f"  Total files in database: {len(all_files)}")
    print(f"  Unique files (after normalization): {len(normalized_map)}")
    print(f"  Duplicate groups found: {duplicates_found}")
    print(f"  Files to delete: {len(files_to_delete)}")

    if files_to_delete:
        if dry_run:
            print(f"\nDRY RUN: Would mark {len(files_to_delete)} duplicate entries as deleted")
            print("Run with --execute to actually perform cleanup")
        else:
            print(f"\nMarking {len(files_to_delete)} duplicate entries as deleted...")
            for file_id in files_to_delete:
                cursor.execute(
                    "UPDATE image_files SET status = ? WHERE id = ?",
                    (ImageStatus.DELETED.value, file_id),
                )
            conn.commit()  # type: ignore[attr-defined]
            print("Cleanup complete!")
            print("\nRestart the application to see the updated file count.")
    else:
        print("\nNo path duplicates found - database is clean!")

    db.close()


if __name__ == "__main__":
    import argparse

    # Initialize logging service
    logging_service = LoggingService()
    logging_service.initialize()

    parser = argparse.ArgumentParser(
        description="Fix duplicate file entries with inconsistent path separators"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Actually perform cleanup (default is dry-run)"
    )

    args = parser.parse_args()

    fix_duplicate_paths(dry_run=not args.execute)
