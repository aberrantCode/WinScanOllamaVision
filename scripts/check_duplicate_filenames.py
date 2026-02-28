"""
Check for duplicate filenames that might be registered/analyzed duplicates.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db.analysis_db import AnalysisDB
from services.logging_service import LoggingService


def check_duplicate_filenames():
    """Find files with same filename but different paths or statuses."""
    LoggingService().initialize()

    db = AnalysisDB()
    conn = db.connection.connection
    cursor = conn.cursor()

    # Check for duplicate filenames
    cursor.execute("""
        SELECT
            filename,
            COUNT(*) as count,
            GROUP_CONCAT(file_path, ' | ') as paths,
            GROUP_CONCAT(status, ' | ') as statuses,
            GROUP_CONCAT(id, ',') as ids
        FROM image_files
        GROUP BY filename
        HAVING count > 1
        ORDER BY count DESC
        LIMIT 20
    """)

    duplicates = cursor.fetchall()

    if not duplicates:
        print("No duplicate filenames found!")
        db.close()
        return

    print(f"Found {len(duplicates)} filenames with multiple entries:")
    print("=" * 80)

    registered_duplicates = []

    for filename, count, paths, statuses, ids in duplicates:
        print(f"\nFilename: {filename}")
        print(f"Entries: {count}")

        paths_list = paths.split(" | ")
        statuses_list = statuses.split(" | ")
        ids_list = ids.split(",")

        # Check if one is registered and one is analyzed (same file)
        has_registered = "registered" in statuses_list
        has_analyzed = "analyzed" in statuses_list or "analyzing" in statuses_list

        if has_registered and has_analyzed:
            # Likely duplicates - same file registered twice
            registered_duplicates.append(
                {
                    "filename": filename,
                    "ids": ids_list,
                    "paths": paths_list,
                    "statuses": statuses_list,
                }
            )
            print("  ** LIKELY DUPLICATE (registered + analyzed) **")

        for i, (path, status, file_id) in enumerate(
            zip(paths_list, statuses_list, ids_list, strict=False), 1
        ):
            print(f"  {i}. [{status:12s}] ID={file_id:4s} - {path}")

    if registered_duplicates:
        print(f'\n{"="*80}')
        print(f"Found {len(registered_duplicates)} likely duplicate registrations")
        print("These files are registered but match already analyzed files.")
        print('\nTo fix: Delete the "registered" entries and keep the "analyzed" ones.')

        # Show IDs to delete
        ids_to_delete = []
        for dup in registered_duplicates:
            for status, file_id in zip(dup["statuses"], dup["ids"], strict=False):
                if status == "registered":
                    ids_to_delete.append(file_id)

        if ids_to_delete:
            print(f'\nIDs to mark as deleted: {", ".join(ids_to_delete)}')
            print(f"Total: {len(ids_to_delete)} entries")

    db.close()


if __name__ == "__main__":
    check_duplicate_filenames()
