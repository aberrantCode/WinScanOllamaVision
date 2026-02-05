# Bundle Review Window - Integration Guide

## Overview

This guide shows how to integrate `BundleReviewWindow` into the main application UI.

## Quick Integration Example

### From Bundle Management UI

```python
from PyQt6.QtWidgets import QPushButton
from ui.bundle_review_window import BundleReviewWindow

class BundleManagementPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        # ... other UI setup ...

        # Add "Review Bundle" button
        review_btn = QPushButton("Review Bundle")
        review_btn.clicked.connect(self.on_review_bundle)

    def on_review_bundle(self):
        """Open Bundle Review Window for selected bundle."""
        # Get selected bundle
        bundle_id = self.get_selected_bundle_id()
        if not bundle_id:
            QMessageBox.warning(self, "No Selection", "Please select a bundle to review.")
            return

        # Load bundle data (prototype mode)
        bundle_data = self.load_bundle_data(bundle_id)

        # Create and show window
        window = BundleReviewWindow(
            bundle_data=bundle_data,
            prototype_mode=True,  # Set False when backend ready
            parent=self
        )

        # Connect signals
        window.bundle_confirmed.connect(self.on_bundle_confirmed)
        window.bundle_rejected.connect(self.on_bundle_rejected)

        # Show window (non-modal)
        window.show()

    def on_bundle_confirmed(self, result):
        """Handle bundle confirmation."""
        bundle_id = result['bundle_id']
        file_paths = result['file_paths']
        user_edits = result['user_edits']

        print(f"Bundle {bundle_id} confirmed with {len(file_paths)} pages")
        print(f"Removed pages: {user_edits['removed_pages']}")
        print(f"Confirmed pages: {user_edits['confirmed_pages']}")

        # Refresh bundle list
        self.refresh_bundles()

        # Show success message
        QMessageBox.information(
            self,
            "Success",
            f"Bundle saved with {len(file_paths)} pages!"
        )

    def on_bundle_rejected(self, bundle_data):
        """Handle bundle rejection."""
        bundle_id = bundle_data['bundle_id']
        print(f"Bundle {bundle_id} review cancelled")

        # No changes needed
```

## Backend Integration (Production)

### Step 1: Load Real Bundle Data

```python
from services.bundling_service import BundlingService
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB

class BundleManagementPanel(QWidget):
    def __init__(self):
        super().__init__()

        # Initialize services
        self.analysis_db = AnalysisDB()
        self.metadata_db = MetadataDB()
        self.bundling_service = BundlingService(self.analysis_db)

    def load_bundle_data(self, bundle_id):
        """Load bundle data from database."""
        # Get bundle from database
        bundle = self.bundling_service.get_bundle(bundle_id)

        # Format for BundleReviewWindow
        return {
            'bundle_id': bundle.bundle_id,
            'file_paths': bundle.file_paths,
            'company': bundle.company,
            'document_type': bundle.document_type,
            'document_date': bundle.document_date,
            'confidence_score': bundle.confidence_score,
            'total_pages': len(bundle.file_paths),
            'analyses': [
                self.analysis_db.get_analysis(fp)
                for fp in bundle.file_paths
            ]
        }
```

### Step 2: Save Bundle Changes

```python
def on_bundle_confirmed(self, result):
    """Save bundle changes to database."""
    bundle_id = result['bundle_id']
    file_paths = result['file_paths']
    user_edits = result['user_edits']

    try:
        # Update bundle in database
        self.bundling_service.update_bundle(
            bundle_id=bundle_id,
            file_paths=file_paths,
            user_confirmed=True
        )

        # Mark confirmed pages
        for page_idx in user_edits['confirmed_pages']:
            file_path = file_paths[page_idx]
            self.analysis_db.mark_page_confirmed(file_path)

        # Handle removed pages (unassign from bundle)
        for page_idx in user_edits['removed_pages']:
            # Note: These are NOT in file_paths anymore
            # Need to track original bundle to unassign
            pass  # Implement based on your data model

        # Refresh UI
        self.refresh_bundles()

        # Show success
        QMessageBox.information(
            self,
            "Success",
            f"Bundle updated with {len(file_paths)} pages!"
        )

    except Exception as e:
        QMessageBox.critical(
            self,
            "Error",
            f"Failed to save bundle: {str(e)}"
        )
```

### Step 3: Wire Re-Analyze Action

To enable re-analysis in production mode, modify `BundleReviewWindow`:

```python
# In bundle_review_window.py

class BundleReviewWindow(QDialog):
    def __init__(self, bundle_data=None, prototype_mode=True,
                 analysis_service=None, parent=None):
        # ...
        self.analysis_service = analysis_service
        # ...

    def _on_reanalyze_page(self):
        """Re-analyze current page."""
        if self.prototype_mode:
            # Show prototype message
            QMessageBox.information(
                self,
                "Prototype Mode",
                "Re-analysis will be available when connected to backend."
            )
            return

        if not self.analysis_service:
            QMessageBox.warning(
                self,
                "Not Available",
                "Analysis service not configured."
            )
            return

        # Get current file path
        file_path = self.bundle_data['file_paths'][self.current_page_index]

        # Show progress
        progress = QProgressDialog("Re-analyzing page...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:
            # Re-analyze
            result = self.analysis_service.analyze_specific_files([file_path])

            if result and result[0].get('success'):
                # Update bundle data
                self.bundle_data['analyses'][self.current_page_index] = result[0]
                self._update_page_info(self.current_page_index)

                QMessageBox.information(
                    self,
                    "Success",
                    "Page re-analyzed successfully!"
                )
            else:
                error_msg = result[0].get('error', 'Unknown error') if result else 'No result'
                QMessageBox.warning(
                    self,
                    "Analysis Failed",
                    f"Failed to analyze page: {error_msg}"
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Re-analysis error: {str(e)}"
            )

        finally:
            progress.close()
```

### Step 4: Wire Delete Action

```python
# In bundle_review_window.py

class BundleReviewWindow(QDialog):
    def __init__(self, bundle_data=None, prototype_mode=True,
                 analysis_service=None, analysis_db=None, parent=None):
        # ...
        self.analysis_db = analysis_db
        # ...

    def _on_delete_page(self):
        """Delete page permanently."""
        reply = QMessageBox.question(
            self,
            "Delete Page",
            f"Permanently delete page {self.current_page_index + 1}?\n\n"
            "This will remove the analysis from the database.\n"
            "The original file will NOT be deleted.\n\n"
            "This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.prototype_mode:
            # Prototype: just remove
            self._on_remove_page()
            return

        if not self.analysis_db:
            QMessageBox.warning(self, "Not Available", "Database not configured.")
            return

        # Get file path
        file_path = self.bundle_data['file_paths'][self.current_page_index]

        try:
            # Delete from database
            self.analysis_db.delete_analysis(file_path)

            # Remove from bundle
            self._on_remove_page()

            QMessageBox.information(
                self,
                "Deleted",
                "Page analysis deleted from database."
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to delete page: {str(e)}"
            )
```

### Step 5: Wire Unassigned Pages

```python
# In bundle_review_window.py

class UnassignedPagesDialog(QDialog):
    def __init__(self, analysis_db=None, prototype_mode=True, parent=None):
        super().__init__(parent)
        self.analysis_db = analysis_db
        self.prototype_mode = prototype_mode
        # ...

    def _load_unassigned_pages(self):
        """Load unassigned pages from database."""
        if self.prototype_mode:
            self._create_mock_pages()
            return

        if not self.analysis_db:
            QMessageBox.warning(self, "Error", "Database not configured.")
            self.reject()
            return

        try:
            # Get unbundled pages from database
            pages = self.analysis_db.get_unbundled_pages()

            # Create thumbnails
            for idx, page in enumerate(pages):
                self._create_thumbnail_for_page(page, idx)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load unassigned pages: {str(e)}"
            )
            self.reject()
```

## Production Usage Example

```python
from ui.bundle_review_window import BundleReviewWindow
from services.analysis_service import AnalysisService
from services.bundling_service import BundlingService
from db.analysis_db import AnalysisDB

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize services
        self.analysis_db = AnalysisDB()
        self.bundling_service = BundlingService(self.analysis_db)
        self.analysis_service = AnalysisService(
            config_manager,
            self.analysis_db,
            metadata_db
        )

    def open_bundle_review(self, bundle_id):
        """Open bundle review window with full backend integration."""

        # Load bundle data
        bundle_data = self.bundling_service.get_bundle(bundle_id)

        # Create window with backend services
        window = BundleReviewWindow(
            bundle_data=bundle_data,
            prototype_mode=False,  # Production mode
            analysis_service=self.analysis_service,
            analysis_db=self.analysis_db,
            parent=self
        )

        # Connect signals
        window.bundle_confirmed.connect(self.save_bundle_changes)
        window.bundle_rejected.connect(self.on_bundle_cancelled)

        # Show window
        window.show()

    def save_bundle_changes(self, result):
        """Save bundle changes to database."""
        try:
            self.bundling_service.update_bundle(
                bundle_id=result['bundle_id'],
                file_paths=result['file_paths'],
                user_confirmed=True
            )

            # Mark confirmed pages
            for idx in result['user_edits']['confirmed_pages']:
                if idx < len(result['file_paths']):
                    file_path = result['file_paths'][idx]
                    self.analysis_db.mark_page_confirmed(file_path)

            # Refresh UI
            self.refresh_bundle_list()

            # Show success
            QMessageBox.information(
                self,
                "Success",
                f"Bundle saved successfully!"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save bundle: {str(e)}"
            )
```

## Context Menu Integration

```python
class BundleListWidget(QListWidget):
    """Bundle list with context menu."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, position):
        """Show context menu for bundle."""
        item = self.itemAt(position)
        if not item:
            return

        bundle_id = item.data(Qt.ItemDataRole.UserRole)

        menu = QMenu(self)

        # Review action
        review_action = menu.addAction("Review Bundle")
        review_action.triggered.connect(
            lambda: self.main_window.open_bundle_review(bundle_id)
        )

        # Export action
        export_action = menu.addAction("Export Bundle")
        export_action.triggered.connect(
            lambda: self.main_window.export_bundle(bundle_id)
        )

        # Delete action
        menu.addSeparator()
        delete_action = menu.addAction("Delete Bundle")
        delete_action.triggered.connect(
            lambda: self.main_window.delete_bundle(bundle_id)
        )

        menu.exec(self.mapToGlobal(position))
```

## Keyboard Shortcuts

Add keyboard shortcuts for quick access:

```python
from PyQt6.QtGui import QShortcut, QKeySequence

class MainWindow(QMainWindow):
    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""

        # Ctrl+R - Review selected bundle
        review_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        review_shortcut.activated.connect(self.review_selected_bundle)

    def review_selected_bundle(self):
        """Review currently selected bundle."""
        selected = self.bundle_list.currentItem()
        if not selected:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a bundle to review."
            )
            return

        bundle_id = selected.data(Qt.ItemDataRole.UserRole)
        self.open_bundle_review(bundle_id)
```

## Toolbar Button Integration

```python
class MainWindow(QMainWindow):
    def setup_toolbar(self):
        """Setup main toolbar."""
        toolbar = self.addToolBar("Main")

        # Review bundle button
        review_action = toolbar.addAction("Review Bundle")
        review_action.setShortcut("Ctrl+R")
        review_action.triggered.connect(self.review_selected_bundle)

        # Other actions...
```

## Status Bar Updates

```python
class MainWindow(QMainWindow):
    def open_bundle_review(self, bundle_id):
        """Open bundle review with status updates."""

        # Show loading status
        self.statusBar().showMessage(f"Loading bundle {bundle_id}...")

        try:
            bundle_data = self.bundling_service.get_bundle(bundle_id)

            window = BundleReviewWindow(
                bundle_data=bundle_data,
                prototype_mode=False,
                parent=self
            )

            window.bundle_confirmed.connect(self.save_bundle_changes)
            window.bundle_rejected.connect(
                lambda: self.statusBar().showMessage("Bundle review cancelled", 3000)
            )

            window.show()

            self.statusBar().showMessage(
                f"Reviewing bundle: {bundle_data['document_type']} - {bundle_data['company']}",
                5000
            )

        except Exception as e:
            self.statusBar().showMessage(f"Error loading bundle: {str(e)}", 5000)
            QMessageBox.critical(self, "Error", f"Failed to load bundle: {str(e)}")
```

## Multi-Window Management

Track multiple review windows:

```python
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.review_windows = {}  # bundle_id -> window

    def open_bundle_review(self, bundle_id):
        """Open bundle review (or focus if already open)."""

        # Check if already open
        if bundle_id in self.review_windows:
            window = self.review_windows[bundle_id]
            if window.isVisible():
                window.activateWindow()
                window.raise_()
                return

        # Load and create new window
        bundle_data = self.bundling_service.get_bundle(bundle_id)

        window = BundleReviewWindow(
            bundle_data=bundle_data,
            prototype_mode=False,
            parent=self
        )

        # Track window
        self.review_windows[bundle_id] = window

        # Remove from tracking when closed
        window.finished.connect(
            lambda: self.review_windows.pop(bundle_id, None)
        )

        # Connect signals
        window.bundle_confirmed.connect(self.save_bundle_changes)

        window.show()
```

## Error Handling

```python
class MainWindow(QMainWindow):
    def open_bundle_review(self, bundle_id):
        """Open bundle review with comprehensive error handling."""

        try:
            # Validate bundle exists
            if not self.bundling_service.bundle_exists(bundle_id):
                raise ValueError(f"Bundle {bundle_id} not found")

            # Load bundle data
            bundle_data = self.bundling_service.get_bundle(bundle_id)

            # Validate bundle data
            if not bundle_data.get('file_paths'):
                raise ValueError("Bundle has no pages")

            # Create window
            window = BundleReviewWindow(
                bundle_data=bundle_data,
                prototype_mode=False,
                analysis_service=self.analysis_service,
                analysis_db=self.analysis_db,
                parent=self
            )

            # Connect with error handling
            window.bundle_confirmed.connect(
                lambda result: self.save_bundle_changes_safe(result)
            )

            window.show()

        except FileNotFoundError as e:
            QMessageBox.critical(
                self,
                "Bundle Not Found",
                f"Could not find bundle: {str(e)}"
            )

        except ValueError as e:
            QMessageBox.warning(
                self,
                "Invalid Bundle",
                str(e)
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Unexpected error: {str(e)}"
            )

    def save_bundle_changes_safe(self, result):
        """Save bundle with error handling."""
        try:
            self.save_bundle_changes(result)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save bundle: {str(e)}"
            )
```

## Testing Integration

```python
# tests/integration/test_bundle_review_integration.py

import pytest
from PyQt6.QtCore import Qt
from ui.bundle_review_window import BundleReviewWindow

def test_open_from_main_window(qtbot, main_window, mock_bundle_service):
    """Test opening review window from main window."""

    # Mock bundle data
    mock_bundle_service.get_bundle.return_value = {
        'bundle_id': 'test_001',
        'file_paths': ['page1.png', 'page2.png'],
        'company': 'Test Corp',
        'document_type': 'Invoice',
        'confidence_score': 0.9,
        'total_pages': 2,
        'analyses': [...]
    }

    # Open review window
    main_window.open_bundle_review('test_001')

    # Verify window opened
    assert 'test_001' in main_window.review_windows
    window = main_window.review_windows['test_001']
    assert window.isVisible()

def test_save_bundle_updates_list(qtbot, main_window, mock_bundle_service):
    """Test saving bundle updates the list."""

    # Open window
    main_window.open_bundle_review('test_001')
    window = main_window.review_windows['test_001']

    # Trigger save
    result = {
        'bundle_id': 'test_001',
        'file_paths': ['page1.png'],
        'user_edits': {
            'removed_pages': [1],
            'confirmed_pages': [0]
        }
    }

    window.bundle_confirmed.emit(result)

    # Verify service called
    mock_bundle_service.update_bundle.assert_called_once()

    # Verify list refreshed
    # (depends on your refresh implementation)
```

## Summary

The Bundle Review Window integrates easily with:

1. **Prototype mode** - Use `prototype_mode=True` for UI testing
2. **Production mode** - Pass services for full backend integration
3. **Context menus** - Right-click actions on bundle lists
4. **Keyboard shortcuts** - Quick access (Ctrl+R)
5. **Toolbar buttons** - Main window toolbar
6. **Multi-window** - Track multiple review windows
7. **Error handling** - Comprehensive try/except blocks

Choose the integration approach that fits your application architecture!
