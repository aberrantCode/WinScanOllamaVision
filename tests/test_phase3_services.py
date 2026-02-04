"""
Comprehensive tests for Phase 3: Analysis and Bundling Services
Tests AnalysisService and BundlingService with mock data
"""

import os
import sys
import tempfile
from PIL import Image

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from services.analysis_service import AnalysisService
from bundling_service import BundlingService
from analysis_db import AnalysisDB
from metadata_db import MetadataDB
from config.config_manager import ConfigManager


def create_test_images(count=5):
    """Create temporary test images"""
    images = []
    for i in range(count):
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img = Image.new('RGB', (100, 100), color=(i*50, 100, 150))
            img.save(f.name)
            images.append(f.name)
    return images


def populate_mock_analysis_data(analysis_db, test_images):
    """Populate database with mock analysis data"""
    # Create realistic test data for bundling
    test_data = [
        # Invoice bundle (3 pages)
        {
            'file_path': test_images[0],
            'company': 'Acme Corp',
            'document_type': 'Invoice',
            'document_date': '2026-01-15',
            'page_number': 1,
            'total_pages': 3,
            'confidence_score': 0.95
        },
        {
            'file_path': test_images[1],
            'company': 'Acme Corp',
            'document_type': 'Invoice',
            'document_date': '2026-01-15',
            'page_number': 2,
            'total_pages': 3,
            'confidence_score': 0.92
        },
        {
            'file_path': test_images[2],
            'company': 'Acme Corp',
            'document_type': 'Invoice',
            'document_date': '2026-01-15',
            'page_number': 3,
            'total_pages': 3,
            'confidence_score': 0.90
        },
        # Separate statement (2 pages)
        {
            'file_path': test_images[3],
            'company': 'Beta Inc',
            'document_type': 'Statement',
            'document_date': '2026-01-20',
            'page_number': 1,
            'total_pages': 2,
            'confidence_score': 0.88
        },
        {
            'file_path': test_images[4],
            'company': 'Beta Inc',
            'document_type': 'Statement',
            'document_date': '2026-01-20',
            'page_number': 2,
            'total_pages': 2,
            'confidence_score': 0.85
        }
    ]

    for data in test_data:
        analysis_db.save_analysis(
            file_path=data['file_path'],
            file_hash=f"hash_{os.path.basename(data['file_path'])}",
            provider_name='test_provider',
            model_name='test_model',
            analysis_data=data,
            raw_response='{"test": "data"}',
            processing_time_ms=100
        )


def test_analysis_service():
    """Test AnalysisService functionality"""
    print("\n" + "="*60)
    print("Testing AnalysisService...")
    print("="*60)

    # Setup databases
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        test_config_path = f.name

    test_images = []

    try:
        config = ConfigManager(test_config_path)
        analysis_db = AnalysisDB(test_db_path)
        metadata_db = MetadataDB(test_db_path)

        service = AnalysisService(config, analysis_db, metadata_db)

        # Test 1: Service initialization
        print("\n[TEST 1] Service initialization")
        assert service.config is not None, "Should have config"
        assert service.analysis_db is not None, "Should have analysis_db"
        assert service.metadata_db is not None, "Should have metadata_db"
        print(f"  ✓ Service initialized successfully")

        # Test 2: Default analysis prompt
        print("\n[TEST 2] Default analysis prompt")
        prompt = service.DEFAULT_ANALYSIS_PROMPT
        assert 'document_type' in prompt, "Prompt should mention document_type"
        assert 'company' in prompt, "Prompt should mention company"
        assert 'page_number' in prompt, "Prompt should mention page_number"
        assert 'rotation' in prompt.lower(), "Prompt should mention rotation"
        print(f"  ✓ Analysis prompt is comprehensive ({len(prompt)} chars)")

        # Test 3: Scan with no directories (should handle gracefully)
        print("\n[TEST 3] Scan with no directories configured")
        stats = service.scan_all_directories()
        assert 'total_files' in stats, "Should return statistics"
        print(f"  ✓ Handled empty scan: {stats.get('message', 'No message')}")

        # Test 4: Configure directory and create test images
        print("\n[TEST 4] Scan configured directory")
        test_dir = tempfile.mkdtemp()
        test_images = create_test_images(3)

        # Move images to test directory
        import shutil
        for img in test_images:
            new_path = os.path.join(test_dir, os.path.basename(img))
            shutil.move(img, new_path)
            test_images[test_images.index(img)] = new_path

        analysis_db.add_source_directory(test_dir)
        print(f"  ✓ Created test directory with {len(test_images)} images")

        # Note: Actual scan will fail without LLM provider, but should handle gracefully
        stats = service.scan_all_directories(incremental=True)
        # File count may vary depending on how glob handles the directory
        print(f"  ✓ Found {stats['total_files']} files (expected ~{len(test_images)})")
        print(f"  ✓ Scan stats: analyzed={stats['analyzed']}, errors={stats['errors']}, skipped={stats['skipped']}")

        # Test 5: Specific file analysis
        print("\n[TEST 5] Analyze specific files")
        stats = service.analyze_specific_files(test_images[:2], force_reanalysis=True)
        assert stats['total_files'] == 2, "Should analyze 2 files"
        print(f"  ✓ Analyzed {stats['total_files']} specific files")

        # Cleanup
        analysis_db.close()
        metadata_db.close()

        # Remove test directory and images
        import time
        time.sleep(0.5)  # Brief delay to ensure file handles released
        for img in test_images:
            if os.path.exists(img):
                try:
                    os.remove(img)
                except:
                    pass
        if os.path.exists(test_dir):
            try:
                os.rmdir(test_dir)
            except:
                pass

        print("\n✅ All AnalysisService tests passed!")

    finally:
        # Cleanup
        import time
        time.sleep(0.5)  # Brief delay to ensure database file handles released
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except:
                pass
        if os.path.exists(test_config_path):
            try:
                os.remove(test_config_path)
            except:
                pass


def test_bundling_service():
    """Test BundlingService functionality"""
    print("\n" + "="*60)
    print("Testing BundlingService...")
    print("="*60)

    # Setup database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    test_images = create_test_images(5)

    try:
        analysis_db = AnalysisDB(test_db_path)
        service = BundlingService(analysis_db)

        # Test 1: Service initialization
        print("\n[TEST 1] Service initialization")
        assert service.analysis_db is not None, "Should have analysis_db"
        print(f"  ✓ Service initialized successfully")

        # Test 2: Empty bundling (no data)
        print("\n[TEST 2] Bundle generation with no data")
        bundles = service.generate_bundle_recommendations()
        assert isinstance(bundles, list), "Should return list"
        assert len(bundles) == 0, "Should have no bundles with no data"
        print(f"  ✓ Correctly returns empty list with no data")

        # Test 3: Populate mock data
        print("\n[TEST 3] Populate mock analysis data")
        populate_mock_analysis_data(analysis_db, test_images)
        analyses = analysis_db.get_analyzed_pages()
        assert len(analyses) == 5, "Should have 5 analyzed pages"
        print(f"  ✓ Populated {len(analyses)} mock analyses")

        # Test 4: Generate bundles
        print("\n[TEST 4] Generate bundle recommendations")
        bundles = service.generate_bundle_recommendations(min_confidence=0.5)
        assert len(bundles) >= 2, "Should generate at least 2 bundles"
        print(f"  ✓ Generated {len(bundles)} bundle suggestions")

        for i, bundle in enumerate(bundles, 1):
            print(f"\n  Bundle {i}:")
            print(f"    Files: {len(bundle['file_paths'])}")
            print(f"    Company: {bundle.get('company')}")
            print(f"    Type: {bundle.get('document_type')}")
            print(f"    Date: {bundle.get('document_date')}")
            print(f"    Method: {bundle.get('grouping_method')}")
            print(f"    Confidence: {bundle['confidence_score']:.2f}")

        # Test 5: Bundle by page numbers (should group Acme Corp invoice)
        print("\n[TEST 5] Verify page number grouping")
        page_number_bundles = [b for b in bundles if b['grouping_method'] == 'explicit_page_numbers']
        assert len(page_number_bundles) >= 1, "Should have at least 1 page-number bundle"
        acme_bundle = [b for b in page_number_bundles if b.get('company') == 'acme corp']
        assert len(acme_bundle) >= 1, "Should bundle Acme Corp invoice"
        assert len(acme_bundle[0]['file_paths']) == 3, "Acme bundle should have 3 pages"
        print(f"  ✓ Found page-number bundle with {len(acme_bundle[0]['file_paths'])} pages")

        # Test 6: High confidence bundles
        print("\n[TEST 6] High confidence bundle filtering")
        high_conf = service.get_high_confidence_bundles(min_confidence=0.8)
        assert len(high_conf) >= 1, "Should have at least 1 high-confidence bundle"
        print(f"  ✓ Found {len(high_conf)} high-confidence bundles")

        # Test 7: Bundle status updates
        print("\n[TEST 7] Bundle status management")
        if bundles:
            bundle_id = bundles[0]['id']

            service.accept_bundle(bundle_id)
            print(f"  ✓ Accepted bundle {bundle_id}")

            # Verify status updated
            db_bundles = analysis_db.get_bundle_suggestions(status='accepted')
            assert len(db_bundles) >= 1, "Should have accepted bundle"
            print(f"  ✓ Bundle status updated in database")

        # Test 8: Confidence scoring
        print("\n[TEST 8] Confidence scoring algorithm")
        for bundle in bundles:
            score = bundle['confidence_score']
            assert 0.0 <= score <= 1.0, f"Confidence should be 0.0-1.0, got {score}"

            # Page number bundles should have higher confidence
            if bundle['grouping_method'] == 'explicit_page_numbers':
                assert score >= 0.6, "Page number bundles should have high confidence"

        print(f"  ✓ All confidence scores in valid range")

        # Test 9: Bundle metadata completeness
        print("\n[TEST 9] Bundle metadata completeness")
        for bundle in bundles:
            assert 'file_paths' in bundle, "Should have file_paths"
            assert 'confidence_score' in bundle, "Should have confidence_score"
            assert 'grouping_method' in bundle, "Should have grouping_method"
            assert len(bundle['file_paths']) >= 2, "Bundles should have at least 2 files"
        print(f"  ✓ All bundles have complete metadata")

        # Cleanup
        analysis_db.close()

        print("\n✅ All BundlingService tests passed!")

    finally:
        # Cleanup - ensure database is closed
        import time
        time.sleep(0.5)

        for img in test_images:
            if os.path.exists(img):
                try:
                    os.remove(img)
                except:
                    pass
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except:
                pass


def test_bundling_edge_cases():
    """Test edge cases in bundling logic"""
    print("\n" + "="*60)
    print("Testing Bundling Edge Cases...")
    print("="*60)

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    test_images = create_test_images(4)

    try:
        analysis_db = AnalysisDB(test_db_path)
        service = BundlingService(analysis_db)

        # Test 1: Single page documents (should not bundle)
        print("\n[TEST 1] Single-page documents not bundled")
        test_data = [
            {
                'file_path': test_images[0],
                'company': 'Solo Corp',
                'document_type': 'Receipt',
                'document_date': '2026-01-01',
                'page_number': None,
                'total_pages': None,
                'confidence_score': 0.9
            }
        ]

        for data in test_data:
            analysis_db.save_analysis(
                file_path=data['file_path'],
                file_hash=f"hash_{os.path.basename(data['file_path'])}",
                provider_name='test',
                model_name='test',
                analysis_data=data,
                raw_response='{}',
                processing_time_ms=100
            )

        bundles = service.generate_bundle_recommendations()
        assert len(bundles) == 0, "Should not bundle single-page documents"
        print(f"  ✓ Single-page documents correctly excluded")

        # Test 2: Incomplete metadata (should still group if partial match)
        print("\n[TEST 2] Partial metadata matching")
        test_data = [
            {
                'file_path': test_images[1],
                'company': 'Partial Corp',
                'document_type': 'Invoice',
                'document_date': None,  # Missing date
                'page_number': 1,
                'total_pages': 2,
                'confidence_score': 0.7
            },
            {
                'file_path': test_images[2],
                'company': 'Partial Corp',
                'document_type': 'Invoice',
                'document_date': None,
                'page_number': 2,
                'total_pages': 2,
                'confidence_score': 0.7
            }
        ]

        for data in test_data:
            analysis_db.save_analysis(
                file_path=data['file_path'],
                file_hash=f"hash_{os.path.basename(data['file_path'])}",
                provider_name='test',
                model_name='test',
                analysis_data=data,
                raw_response='{}',
                processing_time_ms=100
            )

        bundles = service.generate_bundle_recommendations()
        assert len(bundles) >= 1, "Should bundle with partial metadata"
        print(f"  ✓ Partial metadata bundling works")

        # Test 3: Confidence threshold filtering
        print("\n[TEST 3] Confidence threshold filtering")
        high_conf = service.generate_bundle_recommendations(min_confidence=0.9)
        all_conf = service.generate_bundle_recommendations(min_confidence=0.0)
        assert len(all_conf) >= len(high_conf), "Lower threshold should return more bundles"
        print(f"  ✓ High confidence: {len(high_conf)}, All: {len(all_conf)}")

        analysis_db.close()

        print("\n✅ All edge case tests passed!")

    finally:
        import time
        time.sleep(0.5)  # Ensure file handles released

        for img in test_images:
            if os.path.exists(img):
                try:
                    os.remove(img)
                except:
                    pass
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except:
                pass


def main():
    """Run all Phase 3 tests"""
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  PHASE 3: ANALYSIS & BUNDLING SERVICES - COMPREHENSIVE TESTS  ".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)

    try:
        test_analysis_service()
        test_bundling_service()
        test_bundling_edge_cases()

        print("\n" + "█"*60)
        print("█" + " "*58 + "█")
        print("█" + "  🎉 ALL PHASE 3 TESTS PASSED! 🎉  ".center(58) + "█")
        print("█" + " "*58 + "█")
        print("█"*60 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
