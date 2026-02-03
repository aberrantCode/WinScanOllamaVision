"""
Phase 10 Tests: Integration & End-to-End Testing
Comprehensive tests covering complete workflows, performance, and error handling
"""

import sys
import os
import tempfile
import time
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication
from PIL import Image


def test_imports_all_modules():
    """Test that all application modules can be imported"""
    print("\n[TEST] Complete module imports")

    try:
        # Core modules
        from config_manager import ConfigManager
        from metadata_db import MetadataDB
        from analysis_db import AnalysisDB

        # Services
        from ollama_service import OllamaService
        from file_processor import FileProcessor
        from bundling_service import BundlingService
        from analysis_service import AnalysisService

        # Providers
        from llm_providers.base_provider import BaseLLMProvider
        from llm_providers.provider_factory import ProviderFactory
        from llm_providers.ollama_provider import OllamaProvider
        from llm_providers.claude_cli_provider import ClaudeCliProvider
        from llm_providers.gemini_cli_provider import GeminiCliProvider

        # UI
        from gui import StartupWindow, ConvertImagesWindow, WorkflowStep
        from settings_window_enhanced import EnhancedSettingsWindow
        from bundle_widgets import BundleSuggestionCard, BundleSuggestionsView

        # Styles
        from styles import Colors, get_primary_button_style

        print("  [OK] All modules imported successfully")
        return True

    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_integration():
    """Test database creation, migration, and operations"""
    print("\n[TEST] Database integration")

    try:
        from metadata_db import MetadataDB
        from analysis_db import AnalysisDB

        # Create temporary databases
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            metadata_db_path = f.name
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            analysis_db_path = f.name

        # Test MetadataDB
        metadata_db = MetadataDB(metadata_db_path)
        schema_version = metadata_db.get_schema_version()
        assert schema_version >= 2, f"Schema version should be >= 2 (Phase 8 migration), got {schema_version}"

        # Test rotation functionality (Phase 8) - Create actual temp image file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            test_file = f.name

        # Create a real image file
        img = Image.new('RGB', (100, 100), color='red')
        img.save(test_file)

        metadata_db.save_rotation(test_file, 90)
        rotation = metadata_db.get_rotation(test_file)
        assert rotation == 90, f"Rotation should be 90°, got {rotation}°"

        # Clean up test image
        os.remove(test_file)

        metadata_db.close()

        # Test AnalysisDB
        analysis_db = AnalysisDB(analysis_db_path)

        # Test provider management - First add a provider, then set it active
        analysis_db.add_provider(
            provider_name='ollama',
            provider_type='ollama',
            config={'base_url': 'http://localhost:11434'},
            default_model='qwen3-vl:latest'
        )
        analysis_db.set_active_provider('ollama')
        active = analysis_db.get_active_provider()
        assert active is not None, "Should have an active provider"
        assert active['provider_name'] == 'ollama', f"Active provider should be 'ollama', got {active.get('provider_name')}"

        # Test directory management
        analysis_db.add_source_directory('C:\\test\\scans')
        dirs = analysis_db.get_active_directories()
        assert len(dirs) > 0, "Should have at least one directory"

        analysis_db.close()

        # Cleanup
        os.remove(metadata_db_path)
        os.remove(analysis_db_path)

        print("  [OK] Database integration working correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Database integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_persistence():
    """Test configuration saving and loading"""
    print("\n[TEST] Configuration persistence")

    try:
        from config_manager import ConfigManager

        # Create temporary config
        with tempfile.NamedTemporaryFile(suffix='.ini', delete=False, mode='w') as f:
            config_path = f.name

        # Create config manager and set values
        config = ConfigManager(config_path)
        config.set_setting('TestSection', 'test_key', 'test_value')
        config.set_setting('LLMProvider', 'active_provider', 'ollama')

        # Create new instance and verify persistence
        config2 = ConfigManager(config_path)
        value = config2.get_setting('TestSection', 'test_key')
        assert value == 'test_value', f"Config should persist, expected 'test_value', got '{value}'"

        provider = config2.get_setting('LLMProvider', 'active_provider')
        assert provider == 'ollama', f"Provider should persist, expected 'ollama', got '{provider}'"

        # Cleanup
        os.remove(config_path)

        print("  [OK] Configuration persists correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Configuration persistence test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_provider_factory():
    """Test LLM provider factory and switching"""
    print("\n[TEST] Provider factory and switching")

    try:
        from llm_providers.provider_factory import ProviderFactory
        from config_manager import ConfigManager

        # Create temporary config
        with tempfile.NamedTemporaryFile(suffix='.ini', delete=False, mode='w') as f:
            config_path = f.name

        config = ConfigManager(config_path)

        # Test provider types
        available = ProviderFactory.get_available_provider_types()
        assert 'ollama' in available, "Should have ollama provider"
        assert 'claude_cli' in available, "Should have claude_cli provider"
        assert 'gemini_cli' in available, "Should have gemini_cli provider"

        # Test provider creation with config dicts (not ConfigManager)
        ollama_config = {
            'base_url': 'http://localhost:11434',
            'timeout': 300,
            'model': 'qwen3-vl:latest'
        }
        ollama = ProviderFactory.create_provider('ollama', ollama_config)
        assert ollama is not None, "Should create ollama provider"

        claude_config = {
            'command_template': 'claude --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%',
            'timeout': 300,
            'default_model': 'claude-3-5-sonnet-20241022'
        }
        claude = ProviderFactory.create_provider('claude_cli', claude_config)
        assert claude is not None, "Should create claude_cli provider"

        gemini_config = {
            'command_template': 'gemini --model %MODEL% --image %IMAGE_PATHS% --prompt %PROMPT%',
            'timeout': 300,
            'default_model': 'gemini-2.0-flash-exp'
        }
        gemini = ProviderFactory.create_provider('gemini_cli', gemini_config)
        assert gemini is not None, "Should create gemini_cli provider"

        # Cleanup
        os.remove(config_path)

        print("  [OK] Provider factory working correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Provider factory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_window_creation():
    """Test that all UI windows can be created"""
    print("\n[TEST] UI window creation")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from gui import StartupWindow, ConvertImagesWindow
        from settings_window_enhanced import EnhancedSettingsWindow

        # Test StartupWindow
        startup = StartupWindow()
        assert startup.windowTitle() == "WinScanLLM", "StartupWindow should have correct title"
        startup.close()

        # Test ConvertImagesWindow
        convert = ConvertImagesWindow()
        assert "WinScanLLM" in convert.windowTitle(), "ConvertImagesWindow should have app name in title"
        convert.close()

        # Test EnhancedSettingsWindow
        settings = EnhancedSettingsWindow()
        assert "Settings" in settings.windowTitle(), "Settings window should have 'Settings' in title"
        assert settings.tabs.count() == 5, f"Settings should have 5 tabs, got {settings.tabs.count()}"
        settings.close()

        print("  [OK] All UI windows created successfully")
        return True

    except Exception as e:
        print(f"  [FAIL] UI window creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workflow_step_progression():
    """Test workflow step enum and progression"""
    print("\n[TEST] Workflow step progression")

    try:
        from gui import WorkflowStep

        # Verify all workflow steps exist (Phase 7 added bundle suggestions)
        assert hasattr(WorkflowStep, 'BUNDLE_SUGGESTIONS'), "Should have BUNDLE_SUGGESTIONS step"
        assert hasattr(WorkflowStep, 'STITCHING'), "Should have STITCHING step"
        assert hasattr(WorkflowStep, 'ANALYSIS'), "Should have ANALYSIS step"
        assert hasattr(WorkflowStep, 'ORDERING'), "Should have ORDERING step"
        assert hasattr(WorkflowStep, 'FINALIZATION'), "Should have FINALIZATION step"

        # Verify step values (0-4)
        assert WorkflowStep.BUNDLE_SUGGESTIONS.value == 0, "BUNDLE_SUGGESTIONS should be step 0"
        assert WorkflowStep.STITCHING.value == 1, "STITCHING should be step 1"
        assert WorkflowStep.ANALYSIS.value == 2, "ANALYSIS should be step 2"
        assert WorkflowStep.ORDERING.value == 3, "ORDERING should be step 3"
        assert WorkflowStep.FINALIZATION.value == 4, "FINALIZATION should be step 4"

        print("  [OK] Workflow steps correctly defined")
        return True

    except Exception as e:
        print(f"  [FAIL] Workflow step test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_processor_pdf_creation():
    """Test PDF creation with rotation support"""
    print("\n[TEST] File processor PDF creation")

    try:
        from file_processor import FileProcessor
        from config_manager import ConfigManager

        # Create temporary config and directories
        with tempfile.TemporaryDirectory() as temp_dir:
            scan_folder = os.path.join(temp_dir, 'scans')
            organized_folder = os.path.join(temp_dir, 'ORGANIZED')
            os.makedirs(scan_folder)
            os.makedirs(organized_folder)

            with tempfile.NamedTemporaryFile(suffix='.ini', delete=False, mode='w') as f:
                config_path = f.name

            config = ConfigManager(config_path)
            config.set_setting('DocumentProcessing', 'scan_folder', scan_folder)
            config.set_setting('DocumentProcessing', 'organized_subfolder', 'ORGANIZED')

            # Create test images
            test_images = []
            for i in range(3):
                img_path = os.path.join(scan_folder, f'test_{i}.png')
                img = Image.new('RGB', (100, 150), color=['red', 'green', 'blue'][i])
                img.save(img_path)
                test_images.append(img_path)

            # Create file processor
            processor = FileProcessor(config)

            # Test PDF creation without rotation
            pdf_path = processor.create_searchable_pdf(
                test_images,
                'test_document.pdf',
                {},
                is_searchable=False
            )

            assert pdf_path is not None, "PDF should be created"
            assert os.path.exists(pdf_path), "PDF file should exist"

            # Test PDF creation with rotation (Phase 8)
            rotation_map = {
                test_images[0]: 90,
                test_images[2]: 180
            }

            pdf_path2 = processor.create_searchable_pdf(
                test_images,
                'test_document_rotated.pdf',
                {},
                is_searchable=False,
                rotation_map=rotation_map
            )

            assert pdf_path2 is not None, "PDF with rotation should be created"
            assert os.path.exists(pdf_path2), "Rotated PDF file should exist"

            # Verify source images unchanged (Phase 8 fix)
            for img_path in test_images:
                with Image.open(img_path) as img:
                    assert img.size[0] == 100, "Source image width should be unchanged"
                    assert img.size[1] == 150, "Source image height should be unchanged"

            # Cleanup
            os.remove(config_path)

        print("  [OK] File processor creates PDFs correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] File processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_styles_loading():
    """Test that styles module loads correctly"""
    print("\n[TEST] Styles module loading")

    try:
        from styles import Colors, get_primary_button_style, get_main_app_stylesheet

        # Test color palette
        assert Colors.PRIMARY == "#2563EB", "Primary color should be modern blue"
        assert Colors.SUCCESS == "#059669", "Success color should be emerald"
        assert Colors.DANGER == "#DC2626", "Danger color should be red"
        assert Colors.WARNING == "#F59E0B", "Warning color should be amber"

        # Test style functions
        primary_style = get_primary_button_style()
        assert "#2563EB" in primary_style, "Primary button should use primary color"
        assert "border-radius" in primary_style, "Should have rounded corners"

        app_style = get_main_app_stylesheet()
        assert len(app_style) > 0, "Main stylesheet should not be empty"
        assert "#F9FAFB" in app_style, "Should use light background"

        print("  [OK] Styles module loads correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Styles loading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_handling_database():
    """Test error handling for database operations"""
    print("\n[TEST] Error handling - database")

    try:
        from metadata_db import MetadataDB

        # Test with invalid path (should handle gracefully)
        try:
            # This might fail on some systems, but should be caught
            invalid_db = MetadataDB("/invalid/path/database.db")
            invalid_db.close()
        except Exception as e:
            # Expected to fail, but should not crash
            pass

        # Test with valid but empty database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = MetadataDB(db_path)

        # Test querying non-existent data (should return None/defaults)
        rotation = db.get_rotation("nonexistent_file.png")
        assert rotation == 0, "Should return 0 for non-existent file rotation"

        metadata = db.get_metadata("nonexistent_file.png")
        assert metadata is None, "Should return None for non-existent metadata"

        db.close()
        os.remove(db_path)

        print("  [OK] Database error handling working correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Database error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_database_operations():
    """Test database operation performance"""
    print("\n[TEST] Performance - database operations")

    try:
        from metadata_db import MetadataDB

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        db = MetadataDB(db_path)

        # Create temporary directory for test images
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create 100 test images
            test_images = []
            for i in range(100):
                img_path = os.path.join(temp_dir, f"image_{i}.png")
                img = Image.new('RGB', (50, 50), color='blue')
                img.save(img_path)
                test_images.append(img_path)

            # Test bulk rotation saves (simulating 100 images)
            start_time = time.time()
            for i, img_path in enumerate(test_images):
                db.save_rotation(img_path, (i * 90) % 360)
            save_time = time.time() - start_time

            # Test bulk rotation reads
            start_time = time.time()
            for img_path in test_images:
                rotation = db.get_rotation(img_path)
            read_time = time.time() - start_time

        db.close()
        os.remove(db_path)

        # Performance assertions (should be very fast)
        assert save_time < 1.0, f"Saving 100 rotations should take < 1s, took {save_time:.2f}s"
        assert read_time < 0.5, f"Reading 100 rotations should take < 0.5s, took {read_time:.2f}s"

        print(f"  [OK] Database performance acceptable (save: {save_time:.3f}s, read: {read_time:.3f}s)")
        return True

    except Exception as e:
        print(f"  [FAIL] Database performance test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 10 integration tests"""
    print("\n" + "="*70)
    print("PHASE 10 TESTS: Integration & End-to-End Testing")
    print("="*70)

    tests = [
        ("Module Imports", test_imports_all_modules),
        ("Database Integration", test_database_integration),
        ("Configuration Persistence", test_config_persistence),
        ("Provider Factory", test_provider_factory),
        ("UI Window Creation", test_ui_window_creation),
        ("Workflow Steps", test_workflow_step_progression),
        ("File Processor PDF", test_file_processor_pdf_creation),
        ("Styles Loading", test_styles_loading),
        ("Error Handling - Database", test_error_handling_database),
        ("Performance - Database", test_performance_database_operations),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n[FAIL] {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "="*70)
    print(f"PHASE 10 RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*70 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
