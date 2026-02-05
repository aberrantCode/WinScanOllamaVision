# GUI Test Infrastructure

This directory contains test infrastructure and placeholder test files for PyQt6 UI components.

## Status

**Test files created:** 6 placeholder test files
**Actual tests implemented:** 0
**Coverage target:** 60-70% for critical UI workflows

## Test Infrastructure

### conftest.py

Provides shared fixtures for all GUI tests:

- **`qapp`** - Session-scoped QApplication instance (required for all Qt widgets)
- **`mock_config_manager`** - Mock ConfigManager with common settings
- **`mock_analysis_db`** - Mock AnalysisDB
- **`mock_metadata_db`** - Mock MetadataDB
- **`mock_analysis_service`** - Mock AnalysisService with typical responses
- **`mock_bundling_service`** - Mock BundlingService
- **`mock_file_service`** - Mock FileService
- **`sample_analysis_data`** - Sample analysis data for testing
- **`sample_bundle_data`** - Sample bundle data for testing

## Test Files

### test_gui.py
Tests for main `StartupWindow`:
- Window initialization and layout
- Directory management (add, remove, edit)
- Analysis triggering
- Settings and analysis status window opening
- Auto-analysis on startup
- Theme application

### test_analysis_status_window.py
Tests for `AnalysisStatusWindow`:
- Tab switching (Collection Status, File Analysis Grid)
- Auto-start analysis functionality
- Retry failed analysis
- Theme switching
- Data refresh
- Analysis worker thread handling

### test_bundle_widgets.py
Tests for bundle management widgets:
- Bundle list display
- Bundle creation/editing/deletion
- PDF export
- Filtering and sorting
- Signal connections

### test_settings_window.py
Tests for `SettingsWindowEnhanced`:
- Provider configuration (Ollama, Claude CLI, Gemini CLI)
- Provider switching and validation
- Connection testing
- Model selection
- Prompt configuration
- Theme settings

### test_file_details_grid.py
Tests for `FileDetailsGrid`:
- Grid data loading and display
- Sorting and filtering
- Row selection
- Image preview
- Metadata editing
- Context menu actions

### test_theme_manager.py
Tests for `ThemeManager`:
- Theme initialization
- Theme switching
- Stylesheet generation
- Color palette retrieval
- Signal emission

## Implementation Guidelines

### 1. Basic Widget Test Pattern

```python
def test_widget_initialization(qapp, mock_config_manager, mock_analysis_db):
    """Test widget initializes correctly with dependencies."""
    # Arrange - all setup done by fixtures

    # Act
    widget = MyWidget(
        config_manager=mock_config_manager,
        analysis_db=mock_analysis_db
    )

    # Assert
    assert widget is not None
    assert widget.isVisible() or not widget.isVisible()  # Check state
```

### 2. Signal/Slot Testing

```python
def test_button_click_emits_signal(qapp, mock_config_manager):
    """Test button click emits expected signal."""
    # Arrange
    widget = MyWidget(config_manager=mock_config_manager)
    signal_received = []
    widget.my_signal.connect(lambda: signal_received.append(True))

    # Act
    widget.my_button.click()

    # Assert
    assert len(signal_received) == 1
```

### 3. Thread/Worker Testing

```python
def test_worker_thread_execution(qapp, mock_analysis_service):
    """Test worker thread executes and emits completion signal."""
    # Arrange
    window = MyWindow(analysis_service=mock_analysis_service)
    completed = []
    window.worker_finished.connect(lambda: completed.append(True))

    # Act
    window.start_worker()
    QTest.qWait(100)  # Wait for thread execution

    # Assert
    assert len(completed) == 1
    assert mock_analysis_service.some_method.called
```

### 4. User Interaction Testing

```python
from PyQt6.QtTest import QTest
from PyQt6.QtCore import Qt

def test_user_input_interaction(qapp):
    """Test user can interact with input widget."""
    # Arrange
    widget = MyWidget()

    # Act
    QTest.keyClicks(widget.input_field, "test input")
    QTest.keyClick(widget.input_field, Qt.Key.Key_Return)

    # Assert
    assert widget.input_field.text() == "test input"
```

### 5. Mock Database Interaction

```python
def test_widget_loads_data_from_database(qapp, mock_analysis_db):
    """Test widget loads and displays database data."""
    # Arrange
    mock_analysis_db.get_all_analyses.return_value = [
        {"file_path": "test.png", "company": "TestCo"}
    ]

    # Act
    widget = MyWidget(analysis_db=mock_analysis_db)

    # Assert
    mock_analysis_db.get_all_analyses.assert_called_once()
    assert widget.row_count() == 1
```

## Running GUI Tests

```bash
# Run all GUI tests
python -m pytest tests/gui/ -v

# Run specific test file
python -m pytest tests/gui/test_gui.py -v

# Run with Qt event loop debugging
python -m pytest tests/gui/ -v --qt-api=pyqt6

# Run with coverage
python -m pytest tests/gui/ --cov=src/ui --cov-report=term
```

## Common Issues and Solutions

### Issue: QApplication already exists
**Solution:** Use the session-scoped `qapp` fixture - it handles singleton QApplication.

### Issue: Widget not visible in tests
**Solution:** Call `widget.show()` and `QTest.qWait(10)` to process events.

### Issue: Signal not received in test
**Solution:** Call `QApplication.processEvents()` or `QTest.qWait()` to process event loop.

### Issue: Thread tests are flaky
**Solution:** Use longer `QTest.qWait()` delays and explicit thread join/wait mechanisms.

### Issue: Mock not being called
**Solution:** Ensure widget has reference to mock (not creating new instance internally).

## Next Steps

1. **Implement critical path tests first:**
   - StartupWindow initialization
   - Analysis triggering and status display
   - Bundle creation and export

2. **Add widget interaction tests:**
   - Button clicks
   - Menu selections
   - Input field validation

3. **Add integration tests:**
   - Full workflow: scan → analyze → bundle → export
   - Settings changes affecting main window
   - Theme switching across all widgets

4. **Target 60-70% coverage** for UI modules as initial goal

## Resources

- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [Qt Test Framework](https://doc.qt.io/qt-6/qtest-overview.html)
- [pytest-qt plugin](https://pytest-qt.readthedocs.io/)
