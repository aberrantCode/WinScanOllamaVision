"""
Cleanup script to remove stale file entries from the database.

This script identifies files in the database that no longer exist on disk
and marks them as deleted or removes them.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db.analysis_db import AnalysisDB
from db.image_status import ImageStatus
from services.logging_service import LoggingService


def cleanup_stale_files(dry_run: bool = True):
    """
    Find and clean up files in database that no longer exist on disk.

    Args:
        dry_run: If True, only report what would be deleted without making changes
    """
    db = AnalysisDB()

    # Get all non-deleted files from database
    all_files = db.get_analyzed_pages()

    missing_files: list[str] = []
    existing_files: list[str] = []
    directory_counts: dict[str, int] = {}

    print(f"Checking {len(all_files)} files in database...")

    for file_data in all_files:
        file_path = file_data.get("file_path", "")
        if file_path and not os.path.exists(file_path):
            missing_files.append(file_path)
        else:
            existing_files.append(file_path)
            # Track directory distribution
            directory = os.path.dirname(file_path)
            directory_counts[directory] = directory_counts.get(directory, 0) + 1

    print("\nResults:")
    print(f"  Files that exist on disk: {len(existing_files)}")
    print(f"  Files missing from disk: {len(missing_files)}")

    if directory_counts:
        print("\nFiles by directory:")
        for directory, count in sorted(directory_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {count:4d} files - {directory}")

    if missing_files:
        print("\nMissing files (first 10):")
        for path in missing_files[:10]:
            print(f"  - {path}")

        if len(missing_files) > 10:
            print(f"  ... and {len(missing_files) - 10} more")

        if dry_run:
            print(f"\nDRY RUN: Would mark {len(missing_files)} files as deleted")
            print("Run with --execute to actually perform cleanup")
        else:
            print(f"\nMarking {len(missing_files)} files as deleted...")
            for file_path in missing_files:
                db.update_image_status(file_path, ImageStatus.DELETED.value)
            print("Cleanup complete!")
    else:
        print("\nNo stale files found - database is clean!")

    db.close()


if __name__ == "__main__":
    import argparse

    # Initialize logging service
    logging_service = LoggingService()
    logging_service.initialize()

    parser = argparse.ArgumentParser(description="Clean up stale file entries from database")
    parser.add_argument(
        "--execute", action="store_true", help="Actually perform cleanup (default is dry-run)"
    )

    args = parser.parse_args()

    cleanup_stale_files(dry_run=not args.execute)
