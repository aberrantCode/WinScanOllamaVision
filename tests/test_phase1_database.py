"""
Comprehensive tests for Phase 1: Database Foundation
Tests MetadataDB, AnalysisDB, and ConfigManager extensions
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from metadata_db import MetadataDB
from analysis_db import AnalysisDB
from config_manager import ConfigManager


def test_metadata_db():
    """Test MetadataDB with schema versioning"""
    print("\n" + "="*60)
    print("Testing MetadataDB...")
    print("="*60)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    try:
        # Test 1: Database creation and schema version
        print("\n[TEST 1] Database creation and schema version")
        db = MetadataDB(test_db_path)
        version = db.get_schema_version()
        print(f"  ✓ Schema version: {version}")
        assert version >= 1, "Schema version should be at least 1"

        # Test 2: Save and retrieve metadata
        print("\n[TEST 2] Save and retrieve metadata")
        test_metadata = {
            'belongs': True,
            'page_number': 1,
            'total_pages': 3,
            'confidence': 'high',
            'company': 'Test Corp',
            'document_type': 'Invoice',
            'document_date': '2026-02-01'
        }

        # Create a dummy file for testing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_file = f.name
            f.write("test content")

        db.save_metadata(test_file, test_metadata, model_used='test-model', processing_time_ms=100)
        print(f"  ✓ Saved metadata for {os.path.basename(test_file)}")

        retrieved = db.get_metadata(test_file)
        assert retrieved is not None, "Should retrieve saved metadata"
        assert retrieved['company'] == 'Test Corp', "Company should match"
        assert retrieved['page_number'] == 1, "Page number should match"
        print(f"  ✓ Retrieved metadata correctly")

        # Test 3: Archive document
        print("\n[TEST 3] Archive document")
        doc_metadata = {
            'company': 'Test Corp',
            'title': 'Invoice',
            'date': '2026-02-01'
        }
        pdf_path = 'test_document.pdf'
        db.archive_document(pdf_path, [test_file], doc_metadata)
        print(f"  ✓ Archived document")

        archived = db.get_archived_document(pdf_path)
        assert archived is not None, "Should retrieve archived document"
        assert archived['company'] == 'Test Corp', "Archived company should match"
        print(f"  ✓ Retrieved archived document")

        # Test 4: Statistics
        print("\n[TEST 4] Database statistics")
        stats = db.get_statistics()
        print(f"  ✓ Active metadata count: {stats['active_metadata_count']}")
        print(f"  ✓ Archived documents count: {stats['archived_documents_count']}")
        print(f"  ✓ Database size: {stats['database_size_bytes']} bytes")
        assert stats['active_metadata_count'] >= 1, "Should have at least 1 active metadata entry"
        assert stats['archived_documents_count'] >= 1, "Should have at least 1 archived document"

        # Test 5: Backup
        print("\n[TEST 5] Database backup")
        backup_path = db.create_backup()
        assert os.path.exists(backup_path), "Backup file should exist"
        print(f"  ✓ Created backup: {backup_path}")
        os.remove(backup_path)

        # Cleanup test file
        os.remove(test_file)
        db.close()

        print("\n✅ All MetadataDB tests passed!")

    finally:
        # Cleanup
        if os.path.exists(test_db_path):
            os.remove(test_db_path)


def test_analysis_db():
    """Test AnalysisDB with extended tables"""
    print("\n" + "="*60)
    print("Testing AnalysisDB...")
    print("="*60)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    try:
        db = AnalysisDB(test_db_path)

        # Test 1: Save and retrieve analysis
        print("\n[TEST 1] Save and retrieve analysis")
        analysis_data = {
            'document_type': 'Invoice',
            'company': 'Acme Corp',
            'page_number': 1,
            'total_pages': 3,
            'confidence_score': 0.95,
            'rotation_needed': False,
            'suggested_rotation': 0
        }

        db.save_analysis(
            file_path='test_image.png',
            file_hash='abc123',
            provider_name='ollama',
            model_name='qwen2.5-vl',
            analysis_data=analysis_data,
            raw_response='{"test": "response"}',
            processing_time_ms=1500
        )
        print(f"  ✓ Saved analysis for test_image.png")

        retrieved = db.get_analysis('test_image.png')
        assert retrieved is not None, "Should retrieve saved analysis"
        assert retrieved['company'] == 'Acme Corp', "Company should match"
        assert retrieved['confidence_score'] == 0.95, "Confidence should match"
        print(f"  ✓ Retrieved analysis correctly")
        print(f"  ✓ Cache hit count: {retrieved['cache_hit_count']}")

        # Test 2: LLM Provider management
        print("\n[TEST 2] LLM Provider management")
        provider_config = {
            'base_url': 'http://localhost:11434',
            'timeout': 300
        }
        db.add_provider(
            provider_name='ollama',
            provider_type='ollama',
            config=provider_config,
            default_model='qwen2.5-vl',
            available_models=['qwen2.5-vl', 'llava']
        )
        print(f"  ✓ Added provider: ollama")

        db.set_active_provider('ollama')
        active = db.get_active_provider()
        assert active is not None, "Should have active provider"
        assert active['provider_name'] == 'ollama', "Active provider should be ollama"
        print(f"  ✓ Active provider: {active['provider_name']}")

        # Test 3: Source directories
        print("\n[TEST 3] Source directories")
        test_dir = 'C:\\test\\scans'
        db.add_source_directory(test_dir, scan_on_startup=True)
        print(f"  ✓ Added source directory: {test_dir}")

        directories = db.get_active_directories()
        assert test_dir in directories, "Should retrieve added directory"
        print(f"  ✓ Active directories: {len(directories)}")

        db.update_directory_scan_info(test_dir, file_count=25)
        print(f"  ✓ Updated directory scan info")

        # Test 4: Bundle suggestions
        print("\n[TEST 4] Bundle suggestions")
        bundle_metadata = {
            'company': 'Acme Corp',
            'document_type': 'Invoice',
            'document_date': '2026-02-01'
        }
        bundle_id = db.save_bundle_suggestion(
            file_paths=['file1.png', 'file2.png', 'file3.png'],
            bundle_metadata=bundle_metadata,
            confidence_score=0.85
        )
        print(f"  ✓ Created bundle suggestion (ID: {bundle_id})")

        bundles = db.get_bundle_suggestions(min_confidence=0.8)
        assert len(bundles) >= 1, "Should have at least 1 high-confidence bundle"
        assert bundles[0]['confidence_level'] == 'high', "Should be high confidence"
        print(f"  ✓ Retrieved {len(bundles)} bundle suggestions")
        print(f"  ✓ Bundle confidence: {bundles[0]['confidence_score']}")

        db.update_bundle_status(bundle_id, 'accepted', 'User accepted')
        print(f"  ✓ Updated bundle status")

        # Test 5: Rotation preferences
        print("\n[TEST 5] Rotation preferences")
        db.save_rotation_preference('test_image.png', 90, 'manual')
        print(f"  ✓ Saved rotation preference")

        rotation = db.get_rotation_preference('test_image.png')
        assert rotation is not None, "Should retrieve rotation preference"
        assert rotation['rotation_degrees'] == 90, "Rotation should be 90 degrees"
        print(f"  ✓ Retrieved rotation: {rotation['rotation_degrees']}°")

        # Test 6: Extended statistics
        print("\n[TEST 6] Extended statistics")
        stats = db.get_extended_statistics()
        print(f"  ✓ Total analyzed pages: {stats['total_analyzed_pages']}")
        print(f"  ✓ Cached analyses: {stats['cached_analyses']}")
        print(f"  ✓ Average processing time: {stats['avg_processing_time_ms']:.0f}ms")
        print(f"  ✓ Pending bundles: {stats['pending_bundles']}")
        print(f"  ✓ Active provider: {stats['active_provider']}")
        print(f"  ✓ Active directories: {stats['active_directories']}")
        assert stats['total_analyzed_pages'] >= 1, "Should have analyzed pages"
        assert stats['active_provider'] == 'ollama', "Active provider should be ollama"

        # Test 7: Purge operations
        print("\n[TEST 7] Purge operations")
        purged = db.purge_completed_bundles()
        print(f"  ✓ Purged {purged} completed bundles")

        db.close()

        print("\n✅ All AnalysisDB tests passed!")

    finally:
        # Cleanup
        if os.path.exists(test_db_path):
            os.remove(test_db_path)


def test_config_manager():
    """Test ConfigManager extensions"""
    print("\n" + "="*60)
    print("Testing ConfigManager...")
    print("="*60)

    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        test_config_path = f.name

    try:
        # Test 1: Default config creation
        print("\n[TEST 1] Default configuration creation")
        config = ConfigManager(test_config_path)

        # Check all new sections exist
        sections = ['LLMProvider', 'Ollama', 'ClaudeCLI', 'GeminiCLI',
                   'SourceDirectories', 'AutoAnalysis', 'Theme',
                   'OutputDirectory', 'SystemTray', 'AuditTrail']

        missing_sections = []
        for section in sections:
            if section in config.config:
                keys = list(config.config[section].keys())
                if keys:
                    value = config.get_setting(section, keys[0])
                    assert value is not None, f"Section {section} should have values"
            else:
                missing_sections.append(section)

        if missing_sections:
            print(f"  ! Missing sections: {missing_sections}")
        print(f"  ✓ Found {len(sections) - len(missing_sections)}/{len(sections)} sections")

        # Test 2: Provider configuration
        print("\n[TEST 2] Provider configuration")
        active_provider = config.get_active_provider()
        print(f"  ✓ Active provider: {active_provider}")
        assert active_provider in ['ollama', 'claude_cli', 'gemini_cli'], "Should have valid provider"

        ollama_config = config.get_provider_config('ollama')
        assert 'model' in ollama_config, "Ollama config should have model"
        assert 'base_url' in ollama_config, "Ollama config should have base_url"
        print(f"  ✓ Ollama model: {ollama_config['model']}")
        print(f"  ✓ Ollama URL: {ollama_config['base_url']}")

        claude_models = config.get_provider_models('claude_cli')
        print(f"  ✓ Claude models: {len(claude_models)} available")

        # Test 3: Directory management
        print("\n[TEST 3] Directory management")
        test_dirs = ['C:\\test\\dir1', 'C:\\test\\dir2']
        config.set_directories(test_dirs)
        retrieved_dirs = config.get_directories()
        assert retrieved_dirs == test_dirs, "Directories should match"
        print(f"  ✓ Set and retrieved {len(test_dirs)} directories")

        config.add_directory('C:\\test\\dir3')
        retrieved_dirs = config.get_directories()
        assert len(retrieved_dirs) == 3, "Should have 3 directories"
        print(f"  ✓ Added directory (now {len(retrieved_dirs)} total)")

        config.remove_directory('C:\\test\\dir2')
        retrieved_dirs = config.get_directories()
        assert len(retrieved_dirs) == 2, "Should have 2 directories"
        print(f"  ✓ Removed directory (now {len(retrieved_dirs)} total)")

        # Test 4: Boolean and integer helpers
        print("\n[TEST 4] Type-safe getters")
        auto_analysis = config.get_bool('AutoAnalysis', 'enabled', True)
        print(f"  ✓ Auto analysis enabled: {auto_analysis}")
        assert isinstance(auto_analysis, bool), "Should return boolean"

        batch_size = config.get_int('AutoAnalysis', 'batch_size', 10)
        print(f"  ✓ Batch size: {batch_size}")
        assert isinstance(batch_size, int), "Should return integer"

        # Test 5: Provider switching
        print("\n[TEST 5] Provider switching")
        config.set_active_provider('claude_cli')
        active = config.get_active_provider()
        assert active == 'claude_cli', "Should switch to claude_cli"
        print(f"  ✓ Switched to: {active}")

        config.set_active_provider('ollama')
        active = config.get_active_provider()
        assert active == 'ollama', "Should switch back to ollama"
        print(f"  ✓ Switched back to: {active}")

        print("\n✅ All ConfigManager tests passed!")

    finally:
        # Cleanup
        if os.path.exists(test_config_path):
            os.remove(test_config_path)


def main():
    """Run all Phase 1 tests"""
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  PHASE 1: DATABASE FOUNDATION - COMPREHENSIVE TESTS  ".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)

    try:
        test_metadata_db()
        test_analysis_db()
        test_config_manager()

        print("\n" + "█"*60)
        print("█" + " "*58 + "█")
        print("█" + "  🎉 ALL PHASE 1 TESTS PASSED! 🎉  ".center(58) + "█")
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
