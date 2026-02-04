"""
Phase 6 Tests: Enhanced Settings Window
Tests the 5-tab settings interface and configuration management
"""

import sys
import os
import tempfile
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from PyQt6.QtWidgets import QApplication
from config.config_manager import ConfigManager
from metadata_db import MetadataDB
from analysis_db import AnalysisDB


def test_imports():
    """Test that all Phase 6 components can be imported"""
    print("\n[TEST] Phase 6 imports")
    try:
        from settings_window_enhanced import EnhancedSettingsWindow
        print("  [OK] EnhancedSettingsWindow imports successfully")
        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        return False


def test_settings_window_creation():
    """Test that EnhancedSettingsWindow can be instantiated"""
    print("\n[TEST] Settings window creation")

    # Create temporary config and database
    with tempfile.NamedTemporaryFile(suffix='.ini', delete=False) as f:
        test_config = f.name
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        # Create QApplication (required for Qt widgets)
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # Import after QApplication is created
        from settings_window_enhanced import EnhancedSettingsWindow

        # Create window
        window = EnhancedSettingsWindow()

        # Verify window properties
        assert window.windowTitle().endswith("Settings"), "Window title should end with 'Settings'"
        assert window.minimumWidth() >= 750, "Window should have minimum width of 750"
        assert window.minimumHeight() >= 600, "Window should have minimum height of 600"

        # Verify tabs exist
        assert window.tabs.count() == 5, f"Should have 5 tabs, found {window.tabs.count()}"

        tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        expected_tabs = ["General", "LLM Provider", "Directories", "Database", "Appearance"]
        assert tab_names == expected_tabs, f"Tab names mismatch: {tab_names}"

        print(f"  [OK] Window created with 5 tabs: {', '.join(tab_names)}")

        # Close window
        window.close()

        return True

    except Exception as e:
        print(f"  [FAIL] Window creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        time.sleep(0.1)
        if os.path.exists(test_config):
            try:
                os.remove(test_config)
            except:
                pass
        if os.path.exists(test_db):
            try:
                os.remove(test_db)
            except:
                pass


def test_general_tab_controls():
    """Test that General tab has all required controls"""
    print("\n[TEST] General tab controls")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from settings_window_enhanced import EnhancedSettingsWindow

        window = EnhancedSettingsWindow()

        # Check for required controls
        assert hasattr(window, 'scan_folder_edit'), "Should have scan_folder_edit"
        assert hasattr(window, 'auto_approval_checkbox'), "Should have auto_approval_checkbox"
        assert hasattr(window, 'approval_delay_spinbox'), "Should have approval_delay_spinbox"
        assert hasattr(window, 'audit_trail_checkbox'), "Should have audit_trail_checkbox"

        # Verify spinbox range
        assert window.approval_delay_spinbox.minimum() == 3, "Delay minimum should be 3"
        assert window.approval_delay_spinbox.maximum() == 60, "Delay maximum should be 60"

        print("  [OK] General tab has all required controls")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] General tab controls test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_llm_provider_tab_controls():
    """Test that LLM Provider tab has all required controls"""
    print("\n[TEST] LLM Provider tab controls")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from settings_window_enhanced import EnhancedSettingsWindow

        window = EnhancedSettingsWindow()

        # Check for provider selector
        assert hasattr(window, 'provider_combo'), "Should have provider_combo"
        assert window.provider_combo.count() == 3, "Should have 3 providers"

        # Check for provider-specific settings
        assert hasattr(window, 'ollama_settings_widget'), "Should have ollama_settings_widget"
        assert hasattr(window, 'claude_settings_widget'), "Should have claude_settings_widget"
        assert hasattr(window, 'gemini_settings_widget'), "Should have gemini_settings_widget"

        # Check for prompt editors
        assert hasattr(window, 'pages_prompt_edit'), "Should have pages_prompt_edit"
        assert hasattr(window, 'metadata_prompt_edit'), "Should have metadata_prompt_edit"

        # Verify provider combo items
        providers = [window.provider_combo.itemData(i) for i in range(window.provider_combo.count())]
        expected_providers = ['ollama', 'claude_cli', 'gemini_cli']
        assert providers == expected_providers, f"Providers mismatch: {providers}"

        print(f"  [OK] LLM Provider tab has all required controls ({len(providers)} providers)")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] LLM Provider tab controls test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_directories_tab_controls():
    """Test that Directories tab has all required controls"""
    print("\n[TEST] Directories tab controls")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from settings_window_enhanced import EnhancedSettingsWindow

        window = EnhancedSettingsWindow()

        # Check for directory list
        assert hasattr(window, 'directories_list'), "Should have directories_list"
        assert hasattr(window, 'scan_on_startup_checkbox'), "Should have scan_on_startup_checkbox"

        # Verify list is initialized
        assert window.directories_list.count() >= 0, "Directories list should be initialized"

        print(f"  [OK] Directories tab has all required controls")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] Directories tab controls test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_tab_controls():
    """Test that Database tab has all required controls"""
    print("\n[TEST] Database tab controls")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from settings_window_enhanced import EnhancedSettingsWindow

        window = EnhancedSettingsWindow()

        # Check for statistics display
        assert hasattr(window, 'stats_text'), "Should have stats_text"

        # Verify stats text is populated (should show database statistics)
        stats_content = window.stats_text.toPlainText()
        assert len(stats_content) > 0, "Statistics should be displayed"
        assert "Database Statistics" in stats_content, "Should show database statistics header"

        print("  [OK] Database tab has all required controls and displays statistics")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] Database tab controls test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_appearance_tab_controls():
    """Test that Appearance tab has all required controls"""
    print("\n[TEST] Appearance tab controls")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from settings_window_enhanced import EnhancedSettingsWindow

        window = EnhancedSettingsWindow()

        # Check for theme controls
        assert hasattr(window, 'theme_combo'), "Should have theme_combo"
        assert window.theme_combo.count() == 2, "Should have 2 themes (Light/Dark)"

        # Check for zoom controls
        assert hasattr(window, 'png_zoom_combo'), "Should have png_zoom_combo"
        assert hasattr(window, 'pdf_zoom_combo'), "Should have pdf_zoom_combo"
        assert hasattr(window, 'png_zoom_percent'), "Should have png_zoom_percent"
        assert hasattr(window, 'pdf_zoom_percent'), "Should have pdf_zoom_percent"

        # Check for system tray controls
        assert hasattr(window, 'minimize_to_tray_checkbox'), "Should have minimize_to_tray_checkbox"
        assert hasattr(window, 'close_to_tray_checkbox'), "Should have close_to_tray_checkbox"

        # Verify zoom percent ranges
        assert window.png_zoom_percent.minimum() == 25, "PNG zoom minimum should be 25%"
        assert window.png_zoom_percent.maximum() == 400, "PNG zoom maximum should be 400%"

        print("  [OK] Appearance tab has all required controls")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] Appearance tab controls test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_provider_switching():
    """Test that provider panels switch correctly"""
    print("\n[TEST] Provider switching functionality")

    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        from settings_window_enhanced import EnhancedSettingsWindow

        window = EnhancedSettingsWindow()
        # Show window so widgets report visibility correctly
        window.show()

        # Test switching to each provider
        for i in range(window.provider_combo.count()):
            provider_name = window.provider_combo.itemText(i)
            provider_data = window.provider_combo.itemData(i)

            window.provider_combo.setCurrentIndex(i)
            window._on_provider_changed()

            # Process events to update UI
            app.processEvents()

            # Verify correct panel is current in stacked widget
            if provider_data == 'ollama':
                assert window.provider_stack.currentWidget() == window.ollama_settings_widget, \
                    f"Ollama panel should be current"
            elif provider_data == 'claude_cli':
                assert window.provider_stack.currentWidget() == window.claude_settings_widget, \
                    f"Claude panel should be current"
            elif provider_data == 'gemini_cli':
                assert window.provider_stack.currentWidget() == window.gemini_settings_widget, \
                    f"Gemini panel should be current"

        print("  [OK] Provider switching works correctly for all 3 providers")

        window.close()
        return True

    except Exception as e:
        print(f"  [FAIL] Provider switching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 6 tests"""
    print("\n" + "="*70)
    print("PHASE 6 TESTS: Enhanced Settings Window")
    print("="*70)

    tests = [
        ("Import Test", test_imports),
        ("Window Creation", test_settings_window_creation),
        ("General Tab", test_general_tab_controls),
        ("LLM Provider Tab", test_llm_provider_tab_controls),
        ("Directories Tab", test_directories_tab_controls),
        ("Database Tab", test_database_tab_controls),
        ("Appearance Tab", test_appearance_tab_controls),
        ("Provider Switching", test_provider_switching),
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
    print(f"PHASE 6 RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*70 + "\n")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
