#!/usr/bin/env python3
"""
Purge Database Script

Clears the analysis database to start fresh.
This removes all cached analysis results and metadata.
"""

import os
import sys


def purge_database():
    """Delete the metadata database file."""
    appdata = os.getenv("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
    db_path = os.path.join(appdata, "WinScanLLM", "metadata.db")

    if not os.path.exists(db_path):
        print(f"Database does not exist: {db_path}")
        print("  Nothing to purge.")
        return

    print(f"Found database: {db_path}")
    print(f"Size: {os.path.getsize(db_path):,} bytes")

    # Confirm deletion
    response = input("\nWARNING: Delete database and start fresh? (yes/no): ")
    if response.lower() != "yes":
        print("Cancelled.")
        return

    try:
        # Delete main database
        os.remove(db_path)
        print(f"Deleted: {db_path}")

        # Delete journal files if they exist
        for ext in ["-journal", "-wal", "-shm"]:
            journal_path = db_path + ext
            if os.path.exists(journal_path):
                os.remove(journal_path)
                print(f"Deleted: {journal_path}")

        print("\nSUCCESS: Database purged successfully!")
        print("   The database will be recreated on next application start.")

    except PermissionError as e:
        print("\nERROR: Database is locked - application may be running", file=sys.stderr)
        print(f"  {e}", file=sys.stderr)
        print("\nPlease close the WinScanLLM application and try again.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR deleting database: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    purge_database()
