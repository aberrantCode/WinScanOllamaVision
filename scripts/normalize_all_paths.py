"""
Normalize all file paths in the database to use consistent separators.

This fixes mixed-separator paths like C:/Users/.../file.png to C:\\Users\\.../file.png
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db.analysis_db import AnalysisDB
from services.logging_service import LoggingService


def normalize_all_paths(dry_run: bool = True):
    """Normalize all file paths in the database."""
    LoggingService().initialize()

    db = AnalysisDB()
    conn = db.connection.connection
    cursor = conn.cursor()  # type: ignore[attr-defined]

    # Get all files (including deleted for complete cleanup)
    cursor.execute("SELECT id, file_path, directory_path FROM image_files")
    all_files = cursor.fetchall()

    updates_needed = []

    for file_id, file_path, directory_path in all_files:
        normalized_file_path = os.path.normpath(file_path) if file_path else file_path
        normalized_dir_path = os.path.normpath(directory_path) if directory_path else directory_path

        if file_path != normalized_file_path or directory_path != normalized_dir_path:
            updates_needed.append(
                {
                    "id": file_id,
                    "old_file_path": file_path,
                    "new_file_path": normalized_file_path,
                    "old_dir_path": directory_path,
                    "new_dir_path": normalized_dir_path,
                }
            )

    if not updates_needed:
        print("[OK] All paths are already normalized!")
        db.close()
        return

    print(f"Found {len(updates_needed)} paths that need normalization")
    print("=" * 80)

    # Show first 5 examples
    for i, update in enumerate(updates_needed[:5], 1):
        print(f'\n{i}. ID {update["id"]}:')
        if update["old_file_path"] != update["new_file_path"]:
            print(f'   File: {update["old_file_path"]}')
            print(f'      -> {update["new_file_path"]}')
        if update["old_dir_path"] != update["new_dir_path"]:
            print(f'   Dir:  {update["old_dir_path"]}')
            print(f'      -> {update["new_dir_path"]}')

    if len(updates_needed) > 5:
        print(f"\n... and {len(updates_needed) - 5} more")

    print(f'\n{"="*80}')

    if dry_run:
        print(f"DRY RUN: Would normalize {len(updates_needed)} paths")
        print("Run with --execute to actually perform normalization")
    else:
        print(f"Normalizing {len(updates_needed)} paths...")

        # First, delete any rows with status='deleted' that might conflict
        print("Step 1: Removing deleted entries that might conflict...")
        cursor.execute("DELETE FROM image_files WHERE status = ?", ("deleted",))
        deleted_count = cursor.rowcount
        print(f"  Removed {deleted_count} deleted entries")

        # Now normalize the remaining paths
        print("Step 2: Normalizing paths...")
        success_count = 0
        for update in updates_needed:
            try:
                cursor.execute(
                    """
                    UPDATE image_files
                    SET file_path = ?, directory_path = ?
                    WHERE id = ?
                    """,
                    (update["new_file_path"], update["new_dir_path"], update["id"]),
                )
                success_count += 1
            except Exception as e:
                print(f'  Warning: Could not normalize ID {update["id"]}: {e}')

        conn.commit()  # type: ignore[attr-defined]
        print(f"[OK] Successfully normalized {success_count}/{len(updates_needed)} paths!")
        print("\nRestart the application.")

    db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Normalize all file paths in database")
    parser.add_argument(
        "--execute", action="store_true", help="Actually perform normalization (default is dry-run)"
    )

    args = parser.parse_args()

    normalize_all_paths(dry_run=not args.execute)
