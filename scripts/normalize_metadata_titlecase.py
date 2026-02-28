"""
Bulk update existing metadata fields to title case.

Updates company, document_type, and document_category fields
to use consistent title case formatting.
"""

import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from db.metadata_db import MetadataDB
from services.logging_service import LoggingService


def normalize_metadata_to_titlecase(dry_run: bool = True):
    """
    Update all metadata records to use title case for text fields.

    Args:
        dry_run: If True, only report what would be changed without making updates
    """
    db = MetadataDB()
    conn = db.connection.connection
    cursor = conn.cursor()  # type: ignore[attr-defined]

    # Fields to normalize
    title_case_fields = ["company", "document_type", "document_category"]

    print("Checking metadata for title case normalization...")
    print(f"Fields to normalize: {', '.join(title_case_fields)}\n")

    updates_needed = []

    for field in title_case_fields:
        # Get all unique values for this field
        cursor.execute(
            f"SELECT DISTINCT {field} FROM metadata WHERE {field} IS NOT NULL AND {field} != ''"
        )
        values = cursor.fetchall()

        for (original_value,) in values:
            if not original_value:
                continue

            # Check if title case normalization would change it
            normalized = original_value.title()
            if original_value != normalized:
                # Count how many records would be affected
                cursor.execute(
                    f"SELECT COUNT(*) FROM metadata WHERE {field} = ?", (original_value,)
                )
                count = cursor.fetchone()[0]

                updates_needed.append(
                    {
                        "field": field,
                        "original": original_value,
                        "normalized": normalized,
                        "count": count,
                    }
                )

    if not updates_needed:
        print("[OK] All metadata fields are already in title case!")
        db.close()
        return

    print(f"Found {len(updates_needed)} values that need normalization:\n")

    for update in updates_needed:
        print(f"  {update['field']}:")
        print(f"    '{update['original']}' -> '{update['normalized']}'")
        print(f"    ({update['count']} records)\n")

    total_records = sum(u["count"] for u in updates_needed)

    if dry_run:
        print(f"{'='*70}")
        print(f"DRY RUN: Would update {total_records} total records")
        print("Run with --execute to actually perform normalization")
    else:
        print(f"{'='*70}")
        print(f"Updating {total_records} records...")

        for update in updates_needed:
            cursor.execute(
                f"""
                UPDATE metadata
                SET {update['field']} = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE {update['field']} = ?
                """,
                (update["normalized"], update["original"]),
            )

        conn.commit()  # type: ignore[attr-defined]
        print(f"[OK] Successfully normalized {total_records} records!")
        print("\nRestart the application to see the normalized values.")

    db.close()


if __name__ == "__main__":
    import argparse

    # Initialize logging service
    logging_service = LoggingService()
    logging_service.initialize()

    parser = argparse.ArgumentParser(description="Normalize metadata fields to title case")
    parser.add_argument(
        "--execute", action="store_true", help="Actually perform normalization (default is dry-run)"
    )

    args = parser.parse_args()

    normalize_metadata_to_titlecase(dry_run=not args.execute)
