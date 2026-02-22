"""Orchestrator widget: navigation state machine for the bundle review workflow.

Composes BundleThumbnailPanel, BundlePreviewPanel, and BundleMetadataPanel
into a QWidget (not QDialog) that can be embedded in a parent layout.
"""

from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_action_bar import BundleActionBar
from ui.bundle.bundle_header import BundleHeaderWidget
from ui.bundle.bundle_metadata_panel import BundleMetadataPanel
from ui.bundle.bundle_pdf_converter import BundlePdfConverter
from ui.bundle.bundle_preview_panel import BundlePreviewPanel
from ui.bundle.bundle_review_helpers import (
    complete_pdf_conversion,
    show_completion_summary,
    show_pdf_conversion,
)
from ui.bundle.bundle_stylesheet import build_bundle_stylesheet
from ui.bundle.bundle_thumbnail_panel import BundleThumbnailPanel


def _create_mock_bundles() -> list:
    """Create mock bundle data with complete metadata."""
    bundles = []
    companies = [
        "Acme Corporation",
        "TechCorp Industries",
        "Global Shipping LLC",
        "ABC Manufacturing",
    ]
    doc_types = ["Invoice", "Receipt", "Statement", "Contract"]

    for i in range(1, 8):
        # Make first bundle have 12 pages for demo
        num_pages = 12 if i == 1 else (i % 5) + 2

        company = companies[i % 4]
        doc_type = doc_types[i % 4]

        # Create analyses for each page
        analyses = []
        for p in range(num_pages):
            analyses.append(
                {
                    "document_type": doc_type,
                    "company": company,
                    "page_number": str(p + 1),
                    "total_pages": str(num_pages),
                    "rotation_needed": "none",
                    "confidence_score": 0.85 + (p * 0.01),
                    "tax_related": i % 3 == 0,
                    "analysis_id": f"analysis_{i:03d}_{p:03d}",
                    "provider": "Ollama",
                    "model": "qwen2.5-vl",
                    "processing_time": f"{1200 + (p * 100)}ms",
                    "analysis_date": f"2024-03-{15 + i:02d} 10:{30 + p:02d}:00",
                }
            )

        bundles.append(
            {
                "bundle_id": f"bundle_{i:03d}",
                "company": company,
                "document_type": doc_type,
                "document_date": f"2024-0{(i % 9) + 1}-15",
                "confidence_score": 0.95 - (i * 0.05),
                "file_paths": [f"mock_bundle_{i}_page_{p}.png" for p in range(1, num_pages + 1)],
                "analyses": analyses,
            }
        )
    return bundles


class BundleReviewWidget(QWidget):
    """Orchestrator widget composing the three bundle-review panels.

    Owns the navigation state machine and wires cross-panel interactions.
    Emits ``workflow_completed``, ``bundle_accepted``, and ``bundle_rejected``.
    """

    workflow_completed = pyqtSignal(dict)  # stats
    bundle_accepted = pyqtSignal(dict)  # bundle data
    bundle_rejected = pyqtSignal(dict)  # bundle data

    def __init__(
        self,
        bundles=None,
        start_index=0,
        prototype_mode=True,
        analysis_db=None,
        metadata_db=None,
        config_manager=None,
        parent=None,
        embedded_mode=False,
    ):
        super().__init__(parent)

        # Services
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.config_manager = config_manager
        self._pdf_converter: BundlePdfConverter = BundlePdfConverter(config_manager, analysis_db)

        # Embedded mode: run as child widget inside another layout (no dialog chrome/close)
        self.embedded_mode = embedded_mode

        # State
        self.prototype_mode = prototype_mode
        self.bundles = bundles or _create_mock_bundles()
        self.current_bundle_index = start_index
        self.current_page_index = 0

        # Workflow tracking
        self.accepted_bundles = []
        self.rejected_bundles = []
        self.skipped_bundles = []

        # Current bundle state
        self.pan_offset = QPoint(0, 0)
        self.is_panning = False
        self.pan_start_pos = QPoint(0, 0)

        # Read default zoom settings from config
        if self.config_manager:
            self.default_zoom_mode = (
                self.config_manager.get_setting("Theme", "default_zoom_mode_png", "fit_to_width")
                .lower()
                .replace(" ", "_")
            )
            self.default_zoom_percent = int(
                self.config_manager.get_setting("Theme", "default_zoom_percent_png", "100")
            )
        else:
            self.default_zoom_mode = "fit_to_width"
            self.default_zoom_percent = 100

        # Page reordering tracking
        self.page_order = []  # Will be initialized when loading bundle

        # Track first show
        self._first_show = True

        # Theme state - read from config (same key as settings window)
        if config_manager:
            theme = config_manager.get_setting("Theme", "theme", "light")
            self.dark_mode = theme == "dark"
        else:
            self.dark_mode = False

        self._init_ui()

        self._load_current_bundle()

        # Force update of all component styles to ensure theme is fully applied
        self._update_all_component_styles()

    def _init_ui(self):
        """Initialize the guided workflow UI."""
        self.setWindowTitle("Verify Documents")
        if self.embedded_mode:
            # Don't constrain size — let the parent layout decide
            self.setMinimumSize(600, 400)
        else:
            self.setMinimumSize(1400, 900)
            self.resize(1400, 900)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header with progress
        bundle = self.bundles[self.current_bundle_index]
        self._header_widget = BundleHeaderWidget(
            self.dark_mode,
            bundle,
            self.current_bundle_index,
            len(self.bundles),
            len(self.accepted_bundles),
            len(self.rejected_bundles),
            len(self.skipped_bundles),
            parent=self,
        )
        main_layout.addWidget(self._header_widget)

        # Three-panel layout (static widths, no splitter)
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Left panel - Thumbnails with reordering (fixed width)
        self.thumbnail_panel = BundleThumbnailPanel(dark_mode=self.dark_mode, parent=self)
        self.thumbnail_panel.setFixedWidth(150)
        self.thumbnail_panel.page_selected.connect(self._on_thumbnail_clicked)
        self.thumbnail_panel.page_reorder_requested.connect(self._on_drop_requested)
        self.thumbnail_panel.page_move_up_requested.connect(self._move_page_up)
        self.thumbnail_panel.page_move_down_requested.connect(self._move_page_down)
        self.thumbnail_panel.page_remove_requested.connect(self._on_remove_page)
        self.thumbnail_panel.reanalyze_requested.connect(self._on_reanalyze_page)
        self.thumbnail_panel.add_page_requested.connect(self._on_add_page)
        content_layout.addWidget(self.thumbnail_panel)

        # Center panel - Large preview (takes remaining space)
        self.preview_panel = BundlePreviewPanel(dark_mode=self.dark_mode, parent=self)
        content_layout.addWidget(self.preview_panel, stretch=1)

        # Right panel - Metadata (fixed width)
        self.metadata_panel = BundleMetadataPanel(dark_mode=self.dark_mode, parent=self)
        self.metadata_panel.setFixedWidth(380)
        self.metadata_panel.metadata_changed.connect(self._on_metadata_changed)
        self.metadata_panel.save_requested.connect(self._on_metadata_save)
        self.metadata_panel.cancel_requested.connect(self._on_metadata_cancel)
        content_layout.addWidget(self.metadata_panel)

        main_layout.addWidget(content_container)

        # Bottom action bar
        _callbacks = {
            "on_previous": self._on_previous_bundle,
            "on_next": self._on_next_bundle,
            "on_skip": self._on_skip_bundle,
            "on_reject": self._on_reject_bundle,
            "on_accept": self._on_accept_bundle,
            "on_zoom_in": self._on_zoom_in,
            "on_zoom_out": self._on_zoom_out,
            "on_zoom_changed": self._on_zoom_changed,
            "on_fit_width": self._on_fit_width,
            "on_fit_height": self._on_fit_height,
            "on_fit_window": self._on_fit_window,
            "on_rotate_ccw": self._on_rotate_ccw,
            "on_rotate_cw": self._on_rotate_cw,
        }
        self._action_bar = BundleActionBar(
            self.dark_mode,
            _callbacks,
            self.current_bundle_index,
            len(self.bundles),
            parent=self,
        )
        main_layout.addWidget(self._action_bar)

    def _load_current_bundle(self):
        """Load the current bundle data."""
        bundle = self.bundles[self.current_bundle_index]
        self.page_order = list(range(len(bundle.get("file_paths", []))))
        self.current_page_index = 0
        self.preview_panel.reset_rotation()

        # Apply default zoom from config instead of hardcoded 100
        if self.default_zoom_mode == "custom_%":
            self.preview_panel.set_zoom(self.default_zoom_percent)
        else:
            self.preview_panel.set_zoom(100)  # Will be recalculated by fit methods

        self._update_header()
        self._populate_thumbnails()
        self._display_current_page()
        self.metadata_panel.load_bundle(bundle, self.page_order, 0, self.prototype_mode)

        # Apply configured zoom mode after UI is fully laid out
        QTimer.singleShot(300, self._apply_default_zoom)

    def _update_header(self):
        """Update header and nav button state for the current bundle."""
        bundle = self.bundles[self.current_bundle_index]
        self._header_widget.refresh(
            bundle,
            self.current_bundle_index,
            len(self.bundles),
            len(self.accepted_bundles),
            len(self.rejected_bundles),
            len(self.skipped_bundles),
        )
        self._action_bar.update_nav_state(self.current_bundle_index, len(self.bundles))

    def _populate_thumbnails(self):
        """Delegate to BundleThumbnailPanel.populate()."""
        bundle = self.bundles[self.current_bundle_index]
        self.thumbnail_panel.populate(
            bundle.get("file_paths", []),
            self.page_order,
            self.current_page_index,
            self.prototype_mode,
        )

    def _display_current_page(self):
        """Create a pixmap for the current page and hand it to preview_panel."""
        bundle = self.bundles[self.current_bundle_index]
        file_paths = bundle.get("file_paths", [])

        if not file_paths or self.current_page_index >= len(self.page_order):
            return

        actual_index = self.page_order[self.current_page_index]
        file_path = file_paths[actual_index]

        if self.prototype_mode:
            pixmap = QPixmap(600, 800)
            base_color = QColor(220 + (actual_index * 10) % 30, 230, 245)
            pixmap.fill(base_color)
            painter = QPainter(pixmap)
            painter.drawText(
                pixmap.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"Page {actual_index + 1}\n\n(Mock Preview)",
            )
            painter.end()
        else:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                pixmap = QPixmap(600, 800)
                pixmap.fill(QColor(240, 240, 240))
                painter = QPainter(pixmap)
                painter.drawText(
                    pixmap.rect(),
                    Qt.AlignmentFlag.AlignCenter,
                    f"Page {actual_index + 1}\n\nFailed to load image:\n{file_path}",
                )
                painter.end()

        self.preview_panel.display_page(pixmap, self.current_page_index + 1, len(self.page_order))

    def _on_zoom_in(self):
        """Zoom in."""
        new_zoom = min(400, self.preview_panel.zoom_level + 25)
        self._action_bar.zoom_spinner.setValue(new_zoom)

    def _on_zoom_out(self):
        """Zoom out."""
        new_zoom = max(25, self.preview_panel.zoom_level - 25)
        self._action_bar.zoom_spinner.setValue(new_zoom)

    def _on_zoom_changed(self, value: int):
        """Propagate zoom change to the preview panel."""
        self.preview_panel.set_zoom(value)

    def _on_fit_width(self):
        """Fit image to preview panel width."""
        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)
        if size is None:
            return
        image_width = size[0]
        container_width = self.preview_panel.get_container_size()[0] - 40
        if image_width > 0:
            zoom = max(25, min(400, int(container_width / image_width * 100)))
            self._action_bar.zoom_spinner.setValue(zoom)

    def _on_fit_height(self):
        """Fit image to preview panel height."""
        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)
        if size is None:
            return
        image_height = size[1]
        container_height = self.preview_panel.get_container_size()[1] - 100
        if image_height > 0:
            zoom = max(25, min(400, int(container_height / image_height * 100)))
            self._action_bar.zoom_spinner.setValue(zoom)

    def _on_fit_window(self):
        """Fit image to preview panel (both width and height)."""
        size = self.preview_panel.get_original_pixel_size(rotation_adjusted=True)
        if size is None:
            return
        image_width, image_height = size
        container_width = self.preview_panel.get_container_size()[0] - 40
        container_height = self.preview_panel.get_container_size()[1] - 100
        if image_width > 0 and image_height > 0:
            zoom_w = int(container_width / image_width * 100)
            zoom_h = int(container_height / image_height * 100)
            zoom = max(25, min(400, min(zoom_w, zoom_h)))
            self._action_bar.zoom_spinner.setValue(zoom)

    def _apply_default_zoom(self):
        """Apply the default zoom mode from config settings."""
        if self.default_zoom_mode == "fit_to_width":
            self._on_fit_width()
        elif self.default_zoom_mode == "fit_to_height":
            self._on_fit_height()
        elif self.default_zoom_mode == "fit_to_window":
            self._on_fit_window()
        elif self.default_zoom_mode == "custom_%":
            self.preview_panel.set_zoom(self.default_zoom_percent)

    def _on_rotate_ccw(self):
        """Rotate counter-clockwise."""
        self.preview_panel.rotate_ccw()

    def _on_rotate_cw(self):
        """Rotate clockwise."""
        self.preview_panel.rotate_cw()

    def _get_pdf_filename(self, filename: str) -> str:
        """Get final PDF filename with .PDF extension enforced."""
        import os

        name_without_ext = os.path.splitext(filename)[0]
        name_without_ext = BundleMetadataPanel._sanitize_filename(name_without_ext)
        return f"{name_without_ext}.PDF"

    def _on_previous_bundle(self):
        """Navigate to previous bundle."""
        if self.current_bundle_index > 0:
            self.current_bundle_index -= 1
            self._load_current_bundle()

    def _on_next_bundle(self):
        """Navigate to next bundle."""
        if self.current_bundle_index < len(self.bundles) - 1:
            self.current_bundle_index += 1
            self._load_current_bundle()

    def _on_skip_bundle(self):
        """Skip bundle for later review."""
        bundle = self.bundles[self.current_bundle_index]
        self.skipped_bundles.append(bundle)

        if self.current_bundle_index < len(self.bundles) - 1:
            self._on_next_bundle()
        else:
            self._show_completion_summary()

    def _on_reject_bundle(self):
        """Reject the current bundle."""
        bundle = self.bundles[self.current_bundle_index]

        reply = QMessageBox.question(
            self,
            "Reject Bundle",
            f"Reject this bundle?\n\n{bundle.get('document_type')} - {bundle.get('company')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.rejected_bundles.append(bundle)
            self.bundle_rejected.emit(bundle)

            if self.current_bundle_index < len(self.bundles) - 1:
                self._on_next_bundle()
            else:
                self._show_completion_summary()

    def _on_accept_bundle(self):
        """Accept bundle and convert to PDF."""
        bundle = self.bundles[self.current_bundle_index]
        metadata = self.metadata_panel.get_metadata()
        raw_filename = self.metadata_panel.get_output_filename().strip()
        metadata["output_filename"] = self._get_pdf_filename(raw_filename)
        self._show_pdf_conversion(bundle, metadata)

    def _determine_output_directory(self, bundle: dict) -> str:
        """Determine output directory based on configuration strategy."""
        return self._pdf_converter.determine_output_directory(bundle)

    def _show_pdf_conversion(self, bundle: dict, metadata: dict) -> None:
        """Show PDF conversion progress dialog."""
        show_pdf_conversion(
            self, self.dark_mode, bundle, metadata, on_complete=self._complete_pdf_conversion
        )

    def _complete_pdf_conversion(self, progress_dialog, bundle: dict, metadata: dict) -> None:
        """Complete PDF conversion and show success."""

        def _on_accepted(bundle_with_metadata: dict) -> None:
            self.accepted_bundles.append(bundle_with_metadata)
            self.bundle_accepted.emit(bundle_with_metadata)

        def _on_next_or_complete() -> None:
            if self.current_bundle_index < len(self.bundles) - 1:
                self._on_next_bundle()
            else:
                self._show_completion_summary()

        complete_pdf_conversion(
            self,
            progress_dialog,
            bundle,
            metadata,
            prototype_mode=self.prototype_mode,
            page_order=self.page_order,
            rotation_angle=self.preview_panel.rotation_angle,
            pdf_converter=self._pdf_converter,
            on_accepted=_on_accepted,
            on_next_or_complete=_on_next_or_complete,
        )

    def _show_completion_summary(self) -> None:
        """Show workflow completion summary."""
        show_completion_summary(
            self,
            len(self.accepted_bundles),
            len(self.rejected_bundles),
            len(self.skipped_bundles),
            len(self.bundles),
            on_completed=self.workflow_completed.emit,
        )

    def _on_reanalyze_page(self):
        """Re-analyze the current page using LLM provider."""
        if self.prototype_mode:
            QMessageBox.information(
                self,
                "Re-analyze Page",
                "Re-analysis feature is not available in prototype mode.\n\n"
                "In production, this would:\n"
                "1. Call the configured LLM provider\n"
                "2. Extract metadata from the current page\n"
                "3. Update the analysis database\n"
                "4. Refresh the metadata fields",
            )
            return

        # Production implementation
        from services.analysis_service import AnalysisService

        bundle = self.bundles[self.current_bundle_index]

        actual_index = (
            self.page_order[self.current_page_index]
            if self.current_page_index < len(self.page_order)
            else self.current_page_index
        )
        if actual_index >= len(bundle.get("file_paths", [])):
            return

        file_path = bundle["file_paths"][actual_index]

        progress = QProgressBar()
        progress.setMinimum(0)
        progress.setMaximum(0)
        progress.setWindowTitle("Re-analyzing Page")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:

            def update_progress(status_text: str):
                progress.setWindowTitle(status_text)
                QApplication.processEvents()

            analysis_service = AnalysisService(
                self.config_manager, self.analysis_db, self.metadata_db
            )
            result = analysis_service.re_analyze_file(file_path, progress_callback=update_progress)

            if result["success"]:
                fresh_analysis = result.get("analysis")
                if fresh_analysis:
                    bundle["analyses"][actual_index] = fresh_analysis
                    self.metadata_panel.load_bundle(
                        bundle, self.page_order, self.current_page_index, self.prototype_mode
                    )
                    QMessageBox.information(self, "Success", "Page re-analyzed successfully!")
                else:
                    QMessageBox.warning(self, "Error", "Re-analysis completed but no data returned")
            else:
                QMessageBox.warning(
                    self, "Error", f"Re-analysis failed:\n{result.get('error', 'Unknown error')}"
                )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Re-analysis error:\n{str(e)}")
        finally:
            progress.close()

    def _on_add_page(self):
        """Add a page from other bundles or loose pages."""
        if self.prototype_mode:
            QMessageBox.information(
                self,
                "Add Page",
                "Add page feature is not available in prototype mode.\n\n"
                "In production, this would:\n"
                "1. Show a dialog with all available pages\n"
                "2. Allow searching/filtering pages\n"
                "3. Add selected page to current bundle\n"
                "4. Update page order and refresh thumbnails",
            )
            return

        QMessageBox.information(
            self,
            "Add Page",
            "This feature allows you to:\n\n"
            "• Browse pages from other bundles\n"
            "• Add loose/unassigned pages\n"
            "• Search pages by metadata\n\n"
            "Implementation: Create a PagePickerDialog that lists all available pages",
        )

    def _on_remove_page(self, visual_index: int):
        """Remove a page from the current bundle."""
        bundle = self.bundles[self.current_bundle_index]

        if len(bundle["file_paths"]) <= 1:
            QMessageBox.warning(
                self,
                "Cannot Remove",
                "Cannot remove the last page from a bundle.\n\n"
                "A bundle must have at least one page.",
            )
            return

        actual_index = self.page_order[visual_index]
        file_path = bundle["file_paths"][actual_index]
        filename = Path(file_path).name

        reply = QMessageBox.question(
            self,
            "Remove Page",
            f"Remove this page from the bundle?\n\n{filename}\n\n"
            "The page will be marked as a loose page.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            bundle["file_paths"].pop(actual_index)
            if "analyses" in bundle and actual_index < len(bundle["analyses"]):
                bundle["analyses"].pop(actual_index)

            self.page_order = [
                idx if idx < actual_index else idx - 1
                for idx in self.page_order
                if idx != actual_index
            ]

            if self.current_page_index >= len(self.page_order):
                self.current_page_index = max(0, len(self.page_order) - 1)

            self._populate_thumbnails()
            self._display_current_page()
            self._update_header()

    def _toggle_theme(self):
        """Toggle between light and dark mode (not used - theme set from config)."""
        self.dark_mode = not self.dark_mode
        self._update_all_component_styles()

    def _update_all_component_styles(self) -> None:
        """Update all component styles based on current theme."""
        self.setStyleSheet(build_bundle_stylesheet(self.dark_mode))
        bundle = self.bundles[self.current_bundle_index]
        self._header_widget.apply_theme(self.dark_mode)
        self._header_widget.refresh(
            bundle,
            self.current_bundle_index,
            len(self.bundles),
            len(self.accepted_bundles),
            len(self.rejected_bundles),
            len(self.skipped_bundles),
        )
        self._action_bar.apply_theme(self.dark_mode)
        self._action_bar.update_nav_state(self.current_bundle_index, len(self.bundles))
        self.thumbnail_panel.apply_theme(self.dark_mode)
        self.preview_panel.apply_theme(self.dark_mode)
        self.metadata_panel.apply_theme(self.dark_mode)
        self.update()
        self._populate_thumbnails()
        self._display_current_page()

    def _on_metadata_changed(self) -> None:
        """Disable cross-panel interaction while user is editing metadata."""
        self.thumbnail_panel.setEnabled(False)
        self._action_bar.setEnabled(False)

    def _on_metadata_save(self, metadata: dict) -> None:
        """Re-enable panels after metadata save."""
        self.thumbnail_panel.setEnabled(True)
        self._action_bar.setEnabled(True)
        QMessageBox.information(
            self,
            "Changes Saved",
            "Metadata changes saved for this page.\n\n"
            "Changes will be applied when you accept or save the bundle.",
        )

    def _on_metadata_cancel(self) -> None:
        """Re-enable panels after metadata cancel."""
        self.thumbnail_panel.setEnabled(True)
        self._action_bar.setEnabled(True)

    def showEvent(self, event):  # noqa: N802
        """Handle first show - apply configured default zoom."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            QTimer.singleShot(200, self._apply_default_zoom)
