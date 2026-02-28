"""
Final comprehensive cleanup:
1. Delete all "registered" entries where an "analyzed/error" entry exists for same filename
2. Delete all entries with status='deleted'
3. Normalize all remaining paths
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db.analysis_db import AnalysisDB
from services.logging_service import LoggingService


def final_cleanup():
    """Perform final cleanup of database."""
    LoggingService().initialize()

    db = AnalysisDB()
    conn = db.connection.connection
    cursor = conn.cursor()

    print("Step 1: Removing 'registered' duplicates...")
    cursor.execute("""
        DELETE FROM image_files
        WHERE id IN (
            SELECT i1.id
            FROM image_files i1
            WHERE i1.status = 'registered'
            AND EXISTS (
                SELECT 1 FROM image_files i2
                WHERE i2.filename = i1.filename
                AND i2.status IN ('analyzed', 'analyzing', 'error')
                AND i2.id != i1.id
            )
        )
    """)
    deleted_registered = cursor.rowcount
    print(f"  Deleted {deleted_registered} 'registered' duplicates")

    print("\nStep 2: Removing entries with status='deleted'...")
    cursor.execute("DELETE FROM image_files WHERE status = 'deleted'")
    deleted_marked = cursor.rowcount
    print(f"  Deleted {deleted_marked} marked-as-deleted entries")

    print("\nStep 3: Normalizing all remaining paths...")
    cursor.execute("SELECT id, file_path, directory_path FROM image_files")
    all_files = cursor.fetchall()

    normalized_count = 0
    for file_id, file_path, directory_path in all_files:
        normalized_file_path = os.path.normpath(file_path) if file_path else file_path
        normalized_dir_path = os.path.normpath(directory_path) if directory_path else directory_path

        if file_path != normalized_file_path or directory_path != normalized_dir_path:
            cursor.execute(
                "UPDATE image_files SET file_path = ?, directory_path = ? WHERE id = ?",
                (normalized_file_path, normalized_dir_path, file_id),
            )
            normalized_count += 1

    conn.commit()
    print(f"  Normalized {normalized_count} paths")

    # Final check
    print("\nStep 4: Verifying cleanup...")
    cursor.execute("SELECT COUNT(*) FROM image_files WHERE status != 'deleted'")
    final_count = cursor.fetchone()[0]
    print(f"  Final file count: {final_count}")

    cursor.execute("""
        SELECT COUNT(DISTINCT filename)
        FROM image_files
        WHERE status != 'deleted'
    """)
    unique_count = cursor.fetchone()[0]
    print(f"  Unique filenames: {unique_count}")

    if final_count == unique_count:
        print("\n[OK] Database is clean! No duplicates found.")
    else:
        print(f"\n[WARNING] Still {final_count - unique_count} duplicates remain")

    db.close()
    print("\nRestart the application to see the cleaned database.")


if __name__ == "__main__":
    final_cleanup()
