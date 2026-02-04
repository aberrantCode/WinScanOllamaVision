"""
Test script for new Analysis DB query methods
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from analysis_db import AnalysisDB
import json

def test_analysis_db_queries():
    """Test all new query methods"""
    print("=" * 80)
    print("Testing Analysis DB Query Methods")
    print("=" * 80)

    # Initialize database (uses AppData location)
    db = AnalysisDB()

    # Test 1: Collection Summary
    print("\n1. Testing get_collection_summary()...")
    summary = db.get_collection_summary()
    print(f"   Files Detected: {summary['files_detected']}")
    print(f"   Files Analyzed: {summary['files_analyzed']}")
    print(f"   High Confidence: {summary['high_confidence_count']}")
    print(f"   Pages Bundled: {summary['pages_bundled']}")
    print(f"   Documents Archived: {summary['documents_archived']}")
    print(f"   Processing Speed: {summary['processing_speed']:.2f} pages/min")
    print(f"   ETA: {summary['eta_minutes']:.2f} minutes")
    print(f"   Avg Confidence: {summary['avg_confidence']:.2%}")
    print(f"   Error Rate: {summary['error_rate']:.2f}%")
    print(f"   Cache Hit Rate: {summary['cache_hit_rate']:.2f}%")
    print(f"   Metadata Completeness:")
    for field, percentage in summary['metadata_completeness'].items():
        print(f"     - {field}: {percentage:.1f}%")

    # Test 2: Action Items
    print("\n2. Testing get_action_items()...")
    action_items = db.get_action_items()
    print(f"   Pending Analysis: {action_items['pending_analysis']}")
    print(f"   Pending Bundles: {action_items['pending_bundles']}")
    print(f"   Failed Files: {action_items['failed_files']}")
    print(f"   Unbundled Files: {action_items['unbundled_files']}")

    # Test 3: Document Insights
    print("\n3. Testing get_document_insights()...")
    insights = db.get_document_insights()
    print(f"   Total Documents: {insights['total_documents']}")
    print(f"   Total Archived Pages: {insights['total_archived_pages']}")
    print(f"   Avg Pages per Doc: {insights['avg_pages_per_doc']:.2f}")
    print(f"   Bundle Acceptance Rate: {insights['bundle_acceptance_rate']:.2f}%")
    print(f"   Pending Bundle Count: {insights['pending_bundle_count']}")
    print(f"   Type Distribution:")
    for doc_type, count in list(insights['type_distribution'].items())[:5]:
        print(f"     - {doc_type}: {count}")
    print(f"   Company Distribution:")
    for company, count in list(insights['company_distribution'].items())[:5]:
        print(f"     - {company}: {count}")

    # Test 4: Analyzed Pages Detailed (without filters)
    print("\n4. Testing get_analyzed_pages_detailed() - No Filters...")
    pages = db.get_analyzed_pages_detailed()
    print(f"   Total Pages Retrieved: {len(pages)}")
    if pages:
        print(f"   Sample Page (first):")
        sample = pages[0]
        print(f"     - File: {sample.get('file_path', 'N/A')}")
        print(f"     - Company: {sample.get('company', 'N/A')}")
        print(f"     - Type: {sample.get('document_type', 'N/A')}")
        print(f"     - Confidence: {sample.get('confidence_score', 'N/A')}")
        print(f"     - Cached: {sample.get('is_cached', False)}")
        print(f"     - Analyzed At: {sample.get('analyzed_at', 'N/A')}")

    # Test 5: Analyzed Pages with Filters
    print("\n5. Testing get_analyzed_pages_detailed() - With Filters...")
    filters = {
        'confidence_min': 0.7,
        'status': 'analyzed'
    }
    filtered_pages = db.get_analyzed_pages_detailed(filters=filters)
    print(f"   Pages with confidence >= 0.7: {len(filtered_pages)}")

    # Test 6: Helper Methods
    print("\n6. Testing helper methods...")
    print(f"   _count_detected_files(): {db._count_detected_files()}")
    print(f"   _count_high_confidence(): {db._count_high_confidence()}")
    print(f"   _count_bundled_pages(): {db._count_bundled_pages()}")
    print(f"   _calculate_processing_speed(): {db._calculate_processing_speed():.2f} pages/min")
    print(f"   _count_pending_bundles(): {db._count_pending_bundles()}")
    print(f"   _calc_bundle_acceptance_rate(): {db._calc_bundle_acceptance_rate():.2f}%")

    # Test 7: Check Indices
    print("\n7. Verifying database indices...")
    cursor = db.connection.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY name
    """)
    indices = cursor.fetchall()
    print(f"   Total Indices: {len(indices)}")
    for idx in indices:
        print(f"     - {idx['name']}")

    db.close()

    print("\n" + "=" * 80)
    print("All tests completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_analysis_db_queries()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
