"""
Test edge cases for Analysis DB query methods
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from analysis_db import AnalysisDB
from metadata_db import MetadataDB
import tempfile
import json

def test_edge_cases():
    """Test edge cases with sample data"""
    print("=" * 80)
    print("Testing Analysis DB Edge Cases")
    print("=" * 80)

    # Create temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        test_db_path = tmp.name

    try:
        db = AnalysisDB(db_path=test_db_path)

        # Test 1: Empty database
        print("\n1. Testing with empty database...")
        summary = db.get_collection_summary()
        assert summary['files_analyzed'] == 0, "Expected 0 files analyzed"
        assert summary['avg_confidence'] == 0.0, "Expected 0 confidence"
        assert summary['cache_hit_rate'] == 0.0, "Expected 0% cache rate"
        print("   OK Empty database handled correctly")

        # Test 2: Add sample analysis data with various confidence levels
        print("\n2. Adding sample data with various confidence levels...")
        test_files = [
            ('file1.png', 0.95, 'Company A', 'Invoice', True),
            ('file2.png', 0.85, 'Company A', 'Invoice', True),
            ('file3.png', 0.75, 'Company B', 'Statement', False),
            ('file4.png', 0.65, 'Company B', 'Statement', False),
            ('file5.png', 0.45, 'Company C', 'Receipt', False),
            ('file6.png', None, 'Company C', None, False),  # Missing confidence
            ('file7.png', 0.90, None, 'Letter', True),  # Missing company
            ('file8.png', 0.88, 'Company A', None, False),  # Missing doc type
        ]

        for i, (file_path, confidence, company, doc_type, cached) in enumerate(test_files, 1):
            analysis_data = {
                'document_type': doc_type,
                'company': company,
                'document_date': '2026-02-01' if confidence else None,
                'page_number': 1,
                'total_pages': 3,
                'belongs_to_same_doc': True,
                'confidence_score': confidence,
                'rotation_needed': False
            }
            db.save_analysis(
                file_path=file_path,
                file_hash=f'hash{i}',
                provider_name='ollama',
                model_name='qwen2.5-vl',
                analysis_data=analysis_data,
                raw_response='{"test": "response"}',
                processing_time_ms=2500
            )
            if cached:
                # Mark as cached by calling get_analysis
                db.get_analysis(file_path)

        print(f"   OK Added {len(test_files)} sample analysis records")

        # Test 3: Test high confidence count
        print("\n3. Testing high confidence count (>= 0.8)...")
        high_conf = db._count_high_confidence()
        assert high_conf == 4, f"Expected 4 high confidence, got {high_conf}"
        print(f"   OK High confidence count: {high_conf}")

        # Test 4: Test metadata completeness with missing values
        print("\n4. Testing metadata completeness with missing values...")
        completeness = db._get_metadata_completeness()
        print(f"   Company completeness: {completeness['company']:.1f}%")
        print(f"   Document Type completeness: {completeness['document_type']:.1f}%")
        print(f"   Document Date completeness: {completeness['document_date']:.1f}%")
        assert completeness['company'] < 100.0, "Expected company to be incomplete"
        assert completeness['document_type'] < 100.0, "Expected doc type to be incomplete"
        print("   OK Metadata completeness calculated correctly")

        # Test 5: Test cache hit rate
        print("\n5. Testing cache hit rate...")
        summary = db.get_collection_summary()
        expected_cache_rate = (3 / 8) * 100  # 3 cached out of 8
        print(f"   Cache hit rate: {summary['cache_hit_rate']:.2f}%")
        print(f"   Expected: ~{expected_cache_rate:.2f}%")
        assert abs(summary['cache_hit_rate'] - expected_cache_rate) < 0.1, "Cache rate mismatch"
        print("   OK Cache hit rate calculated correctly")

        # Test 6: Test document type distribution
        print("\n6. Testing document type distribution...")
        type_dist = db._get_type_distribution()
        print(f"   Type distribution: {type_dist}")
        assert type_dist.get('Invoice', 0) == 2, "Expected 2 invoices"
        assert type_dist.get('Statement', 0) == 2, "Expected 2 statements"
        assert 'Unknown' in type_dist, "Expected Unknown category"
        print("   OK Type distribution correct")

        # Test 7: Test company distribution
        print("\n7. Testing company distribution...")
        company_dist = db._get_company_distribution()
        print(f"   Company distribution: {company_dist}")
        assert company_dist.get('Company A', 0) == 3, "Expected 3 from Company A"
        assert company_dist.get('Company B', 0) == 2, "Expected 2 from Company B"
        assert 'Unknown' in company_dist, "Expected Unknown category"
        print("   OK Company distribution correct")

        # Test 8: Test filtered queries
        print("\n8. Testing filtered queries...")

        # Filter by company
        pages = db.get_analyzed_pages_detailed(filters={'company': 'Company A'})
        assert len(pages) == 3, f"Expected 3 pages from Company A, got {len(pages)}"
        print(f"   OK Company filter: {len(pages)} pages")

        # Filter by confidence
        pages = db.get_analyzed_pages_detailed(filters={'confidence_min': 0.8})
        assert len(pages) == 4, f"Expected 4 pages with confidence >= 0.8, got {len(pages)}"
        print(f"   OK Confidence filter: {len(pages)} pages")

        # Filter by status (cached)
        pages = db.get_analyzed_pages_detailed(filters={'status': 'cached'})
        assert len(pages) == 3, f"Expected 3 cached pages, got {len(pages)}"
        print(f"   OK Status filter (cached): {len(pages)} pages")

        # Filter by document type
        pages = db.get_analyzed_pages_detailed(filters={'document_type': 'Invoice'})
        assert len(pages) == 2, f"Expected 2 invoices, got {len(pages)}"
        print(f"   OK Document type filter: {len(pages)} pages")

        # Test 9: Test bundles
        print("\n9. Testing bundle calculations...")

        # Add some test bundles
        bundle_id1 = db.save_bundle_suggestion(
            file_paths=['file1.png', 'file2.png', 'file3.png'],
            bundle_metadata={
                'company': 'Company A',
                'document_type': 'Invoice',
                'document_date': '2026-02-01'
            },
            confidence_score=0.92
        )

        bundle_id2 = db.save_bundle_suggestion(
            file_paths=['file4.png', 'file5.png'],
            bundle_metadata={
                'company': 'Company B',
                'document_type': 'Statement',
                'document_date': '2026-02-02'
            },
            confidence_score=0.55
        )

        # Accept first bundle
        db.update_bundle_status(bundle_id1, 'accepted', 'User accepted')

        bundled_count = db._count_bundled_pages()
        assert bundled_count == 5, f"Expected 5 bundled pages, got {bundled_count}"
        print(f"   OK Bundled pages: {bundled_count}")

        pending_bundles = db._count_pending_bundles()
        assert pending_bundles == 1, f"Expected 1 pending bundle, got {pending_bundles}"
        print(f"   OK Pending bundles: {pending_bundles}")

        acceptance_rate = db._calc_bundle_acceptance_rate()
        assert acceptance_rate == 50.0, f"Expected 50% acceptance, got {acceptance_rate}%"
        print(f"   OK Bundle acceptance rate: {acceptance_rate}%")

        # Test 10: Test action items
        print("\n10. Testing action items...")
        action_items = db.get_action_items()
        print(f"   Pending analysis: {action_items['pending_analysis']}")
        print(f"   Pending bundles: {action_items['pending_bundles']}")
        print(f"   Failed files: {action_items['failed_files']}")
        print(f"   Unbundled files: {action_items['unbundled_files']}")
        assert action_items['pending_bundles'] == 1, "Expected 1 pending bundle"
        assert action_items['unbundled_files'] == 3, "Expected 3 unbundled files (8 - 5 bundled)"
        print("   OK Action items calculated correctly")

        # Test 11: Test processing speed and ETA
        print("\n11. Testing processing speed and ETA...")
        speed = db._calculate_processing_speed()
        print(f"   Processing speed: {speed:.2f} pages/min")
        assert speed > 0, "Expected positive processing speed"

        eta = db._calculate_eta(files_detected=20, files_analyzed=8, processing_speed=speed)
        print(f"   ETA for 12 remaining files: {eta:.2f} minutes")
        assert eta > 0, "Expected positive ETA"
        print("   OK Speed and ETA calculated correctly")

        # Test 12: Test document insights
        print("\n12. Testing document insights...")
        insights = db.get_document_insights()
        print(f"   Total documents: {insights['total_documents']}")
        print(f"   Pending bundles: {insights['pending_bundle_count']}")
        print(f"   Bundle acceptance rate: {insights['bundle_acceptance_rate']:.1f}%")
        assert insights['pending_bundle_count'] == 1, "Expected 1 pending bundle"
        assert insights['bundle_acceptance_rate'] == 50.0, "Expected 50% acceptance rate"
        print("   OK Document insights correct")

        # Test 13: Verify all indices were created
        print("\n13. Verifying indices...")
        cursor = db.connection.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name IN (
                'idx_analysis_confidence',
                'idx_analysis_company_type',
                'idx_analysis_date',
                'idx_bundle_status'
            )
        """)
        indices = [row['name'] for row in cursor.fetchall()]
        assert len(indices) == 4, f"Expected 4 new indices, found {len(indices)}"
        print(f"   All 4 required indices created: {indices}")

        db.close()

        print("\n" + "=" * 80)
        print("All edge case tests passed!")
        print("=" * 80)

    finally:
        # Cleanup
        try:
            if os.path.exists(test_db_path):
                os.remove(test_db_path)
                print(f"\nCleaned up test database: {test_db_path}")
        except PermissionError:
            print(f"\nWarning: Could not delete test database (file in use): {test_db_path}")


if __name__ == "__main__":
    try:
        test_edge_cases()
    except AssertionError as e:
        print(f"\nASSERTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
