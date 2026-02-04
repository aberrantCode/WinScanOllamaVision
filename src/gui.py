import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QLineEdit, QScrollArea, QFrame,
    QMessageBox, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QCheckBox,
    QGridLayout, QSizePolicy, QFileDialog, QProgressBar, QPlainTextEdit,
    QSplitter, QStyle, QGraphicsOpacityEffect, QSpinBox
)
from PyQt6.QtGui import QPixmap, QDesktopServices, QMovie, QIcon, QTransform
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QThread, QTimer, QSize
from enum import Enum
from typing import List, Dict, Optional

try:
    import fitz
except ImportError:
    print("Error: PyMuPDF (fitz) is not installed. Please run 'pip install PyMuPDF'.")
    sys.exit(1)

from config_manager import ConfigManager
from ollama_service import OllamaService
from file_processor import FileProcessor
from metadata_db import MetadataDB
from settings_window_enhanced import EnhancedSettingsWindow
from bundle_widgets import BundleSuggestionsView
from bundling_service import BundlingService
from analysis_db import AnalysisDB
from analysis_status_window import AnalysisStatusWindow
from styles import show_information, show_warning, show_critical, show_question

class ProgressBannerWidget(QWidget):
    """Non-modal progress banner for analysis progress"""
    cancelled = pyqtSignal()
    details_toggled = pyqtSignal(bool)
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.details_expanded = False
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            ProgressBannerWidget {
                background-color: #E3F2FD;
                border: 1px solid #90CAF9;
                border-radius: 5px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(5)

        # Top row: Icon, status, buttons
        top_layout = QHBoxLayout()

        self.icon_label = QLabel("📊")
        self.icon_label.setStyleSheet("font-size: 18pt; background: transparent;")
        top_layout.addWidget(self.icon_label)

        self.status_label = QLabel("Analyzing documents...")
        self.status_label.setStyleSheet("font-size: 11pt; font-weight: bold; background: transparent; color: #0D47A1;")
        top_layout.addWidget(self.status_label, 1)

        self.time_label = QLabel("")
        self.time_label.setStyleSheet("font-size: 10pt; background: transparent; color: #546E7A;")
        top_layout.addWidget(self.time_label)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        self.cancel_button.clicked.connect(self.cancelled.emit)
        top_layout.addWidget(self.cancel_button)

        self.details_button = QPushButton("▼ Details")
        self.details_button.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 5px 15px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.details_button.clicked.connect(self._toggle_details)
        top_layout.addWidget(self.details_button)

        main_layout.addLayout(top_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #90CAF9;
                border-radius: 3px;
                text-align: center;
                background-color: white;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #2563EB;
            }
        """)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # Progress text
        self.progress_label = QLabel("Starting...")
        self.progress_label.setStyleSheet("font-size: 10pt; background: transparent; color: #37474F;")
        main_layout.addWidget(self.progress_label)

        # Details panel (initially hidden)
        self.details_widget = QWidget()
        self.details_widget.setVisible(False)
        self.details_widget.setStyleSheet("background: transparent;")
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 5, 0, 0)

        self.current_file_label = QLabel("")
        self.current_file_label.setStyleSheet("font-size: 9pt; background: transparent; color: #546E7A;")
        details_layout.addWidget(self.current_file_label)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 9pt; background: transparent; color: #546E7A;")
        details_layout.addWidget(self.stats_label)

        main_layout.addWidget(self.details_widget)

        self.setFixedHeight(120)  # Initial compact height

        # Set cursor to hand pointer to indicate clickability
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        """Show hand cursor on hover"""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Reset cursor"""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle click on banner"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Only emit click if not clicking on buttons
            widget = self.childAt(event.pos())
            if widget not in [self.cancel_button, self.details_button]:
                self.clicked.emit()
        super().mousePressEvent(event)

    def _toggle_details(self):
        self.details_expanded = not self.details_expanded
        self.details_widget.setVisible(self.details_expanded)

        if self.details_expanded:
            self.details_button.setText("▲ Hide Details")
            self.setFixedHeight(180)
            # Notify parent that details are expanded (to cancel auto-dismiss)
            self.details_toggled.emit(True)
        else:
            self.details_button.setText("▼ Details")
            self.setFixedHeight(120)
            self.details_toggled.emit(False)

        self.details_toggled.emit(self.details_expanded)

    def update_progress(self, current: int, total: int, status_text: str = ""):
        """Update progress display"""
        if total > 0:
            percentage = int((current / total) * 100)
            self.progress_bar.setValue(percentage)
            self.progress_label.setText(f"{current} / {total} pages ({percentage}%)")
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText("Calculating...")

        if status_text:
            self.current_file_label.setText(f"Current: {status_text}")

    def update_stats(self, analyzed: int, cached: int, errors: int):
        """Update statistics"""
        self.stats_label.setText(
            f"Analyzed: {analyzed} | Cached: {cached} | Errors: {errors}"
        )

    def update_time(self, elapsed_seconds: int, estimated_remaining: int = None):
        """Update elapsed/remaining time"""
        elapsed_str = self._format_time(elapsed_seconds)

        if estimated_remaining is not None and estimated_remaining > 0:
            remaining_str = self._format_time(estimated_remaining)
            self.time_label.setText(f"{elapsed_str} | ~{remaining_str} remaining")
        else:
            self.time_label.setText(elapsed_str)

    def _format_time(self, seconds: int) -> str:
        """Format seconds as human-readable time"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def show_completion(self, success: bool, message: str):
        """Show completion status"""
        if success:
            self.icon_label.setText("✓")
            self.status_label.setText(message)
            self.status_label.setStyleSheet("font-size: 11pt; font-weight: bold; background: transparent; color: #2E7D32;")
        else:
            self.icon_label.setText("⚠")
            self.status_label.setText(message)
            self.status_label.setStyleSheet("font-size: 11pt; font-weight: bold; background: transparent; color: #F57C00;")

        self.cancel_button.setVisible(False)

        # Add dismiss button
        if not hasattr(self, 'dismiss_button'):
            self.dismiss_button = QPushButton("Dismiss")
            self.dismiss_button.setStyleSheet("""
                QPushButton {
                    background-color: #6B7280;
                    color: white;
                    border: none;
                    border-radius: 3px;
                    padding: 5px 15px;
                    font-size: 9pt;
                }
                QPushButton:hover {
                    background-color: #4B5563;
                }
            """)
            self.dismiss_button.clicked.connect(self.hide)
            # Add to layout
            top_layout = self.layout().itemAt(0).layout()
            top_layout.addWidget(self.dismiss_button)
        else:
            self.dismiss_button.setVisible(True)

class OllamaWorker(QThread):
    finished = pyqtSignal(object)
    progress = pyqtSignal(str)

    def __init__(self, service_method, *args, **kwargs):
        super().__init__()
        self.service_method = service_method
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # Add progress callback to kwargs if method supports it
            # Check if the method accepts a progress_callback parameter
            import inspect
            sig = inspect.signature(self.service_method)
            if 'progress_callback' in sig.parameters:
                self.kwargs['progress_callback'] = self._emit_progress

            result = self.service_method(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit(e)

    def _emit_progress(self, message):
        """Emit progress update"""
        self.progress.emit(message)

class FinalConfirmationDialog(QDialog):
    ACCEPT_DELETE_SOURCES, ACCEPT_KEEP_SOURCES, REJECT_DELETE_PDF = range(3)

    def __init__(self, pdf_path, source_paths, expected, actual, searchable, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        self.setWindowTitle(f"{self.app_name} - Confirm Action")
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setGeometry(100, 100, 700, 500)
        self.pdf_path = pdf_path
        self._init_ui(source_paths, expected, actual, searchable)

    def _init_ui(self, source_paths, expected, actual, searchable):
        main_layout = QVBoxLayout(self)
        summary_label = QLabel()
        summary = (f"PDF Created: <b>{os.path.basename(self.pdf_path)}</b><br>"
                   f"Pages: {actual} (Expected: {expected})<br>"
                   f"Searchable: {'Yes' if searchable else 'No'}")
        summary_label.setText(summary)
        summary_label.setTextFormat(Qt.TextFormat.RichText)
        main_layout.addWidget(summary_label)

        if expected != actual:
            warning_label = QLabel(f"<p style='color:red; font-weight:bold;'>⚠️ VERIFICATION FAILED! Expected {expected} pages, but the PDF has {actual} pages.</p>")
            warning_label.setTextFormat(Qt.TextFormat.RichText)
            main_layout.addWidget(warning_label)
        
        if not searchable:
            searchable_warning_label = QLabel("<p style='color:orange; font-weight:bold;'>ⓘ WARNING: This PDF is image-only and NOT text-searchable.</p>")
            searchable_warning_label.setTextFormat(Qt.TextFormat.RichText)
            main_layout.addWidget(searchable_warning_label)

        main_layout.addWidget(QLabel("Source PNGs:"))
        source_list_widget = QListWidget()
        for path in source_paths:
            source_list_widget.addItem(os.path.basename(path))
        main_layout.addWidget(source_list_widget)

        open_pdf_button = QPushButton("Open PDF for Review")
        open_pdf_button.clicked.connect(self._open_pdf_for_review)
        main_layout.addWidget(open_pdf_button)

        button_box = QDialogButtonBox()
        accept_delete_button = QPushButton("Accept & Delete Source Files")
        accept_delete_button.clicked.connect(lambda: self.done(self.ACCEPT_DELETE_SOURCES))
        button_box.addButton(accept_delete_button, QDialogButtonBox.ButtonRole.YesRole)

        accept_keep_button = QPushButton("Accept & Keep Source Files")
        accept_keep_button.clicked.connect(lambda: self.done(self.ACCEPT_KEEP_SOURCES))
        button_box.addButton(accept_keep_button, QDialogButtonBox.ButtonRole.AcceptRole)

        reject_delete_button = QPushButton("Reject & Delete PDF")
        reject_delete_button.clicked.connect(lambda: self.done(self.REJECT_DELETE_PDF))
        button_box.addButton(reject_delete_button, QDialogButtonBox.ButtonRole.RejectRole)
        main_layout.addWidget(button_box)

    def _open_pdf_for_review(self):
        if os.path.exists(self.pdf_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.pdf_path))

class ExpandablePromptEdit(QPlainTextEdit):
    """Text edit that expands on focus and collapses on blur"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.collapsed_height = 30  # Single line height
        self.expanded_height = 400  # ~15-20 lines at typical font size
        self.setMaximumHeight(self.collapsed_height)
        self.setMinimumHeight(self.collapsed_height)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setPlaceholderText("Click to edit prompt...")

    def focusInEvent(self, event):
        """Expand when focused"""
        super().focusInEvent(event)
        self.setMaximumHeight(self.expanded_height)
        self.setMinimumHeight(self.expanded_height)  # Force expansion
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def focusOutEvent(self, event):
        """Collapse when focus lost"""
        super().focusOutEvent(event)
        self.setMaximumHeight(self.collapsed_height)
        self.setMinimumHeight(self.collapsed_height)  # Force collapse
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Resize parent window to fit new size
        window = self.window()
        if window:
            window.adjustSize()

# Old SettingsWindow class removed - replaced by EnhancedSettingsWindow
# See settings_window_enhanced.py for the new tabbed settings interface

class PagePreviewWidget(QWidget):
    def __init__(self, image_path, thumbnail_width=100, parent=None):
        super().__init__(parent)
        self.image_path = image_path

        # Use vertical layout for compact horizontal display
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)

        # Checkbox at top
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        layout.addWidget(self.checkbox, alignment=Qt.AlignmentFlag.AlignCenter)

        # Thumbnail image
        image_label = QLabel()
        image_label.setFrameShape(QFrame.Shape.StyledPanel)
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaledToWidth(thumbnail_width, Qt.TransformationMode.SmoothTransformation)
        image_label.setPixmap(scaled_pixmap)
        layout.addWidget(image_label)

        # Page number label
        page_num = os.path.basename(image_path)
        page_label = QLabel(f"Page {page_num[:10]}...")
        page_label.setStyleSheet("font-size: 8pt;")
        page_label.setWordWrap(True)
        layout.addWidget(page_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()

class WorkflowStep(Enum):
    BUNDLE_SUGGESTIONS = 0  # Step 0: AI Bundle Suggestions (Phase 7)
    STITCHING = 1  # Step 1: Document Stitching
    ANALYSIS = 2   # Step 2: Document Analysis (Metadata Extraction)
    ORDERING = 3   # Step 3: Order Pages
    FINALIZATION = 4  # Step 4: Document Finalization


class ConvertPDFsWindow(QMainWindow):
    """Window for extracting pages from PDFs for re-bundling"""

    def __init__(self, pdf_files=None):
        super().__init__()
        self.config_manager = ConfigManager()
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        self.setWindowTitle(f"{self.app_name} - Convert PDFs")

        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setGeometry(100, 100, 900, 700)

        # State
        self.current_step = 1
        self.pdf_files = pdf_files if pdf_files else []
        self.selected_pdfs = []
        self.extraction_results = []

        self._init_ui()

        # If no PDF files provided, load from scan folder
        if not self.pdf_files:
            self._load_pdfs()

    def _init_ui(self):
        """Initialize the UI with 3-step workflow"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel("Convert PDFs to Images")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; padding: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Step indicator
        self.step_label = QLabel("Step 1: Select PDFs")
        self.step_label.setStyleSheet("font-size: 14pt; padding: 5px;")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.step_label)

        # Content area (stacked)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        main_layout.addWidget(self.content_widget)

        # Button area
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self._go_back)
        self.back_button.setEnabled(False)
        button_layout.addWidget(self.back_button)

        self.next_button = QPushButton("Extract Pages")
        self.next_button.clicked.connect(self._go_next)
        button_layout.addWidget(self.next_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        main_layout.addLayout(button_layout)

        self._show_step_1()

    def _load_pdfs(self):
        """Load PDF files from scan folder"""
        scan_folder = self.config_manager.get_setting("DocumentProcessing", "scan_folder")
        if not os.path.isdir(scan_folder):
            return

        self.pdf_files = [
            os.path.join(scan_folder, f)
            for f in os.listdir(scan_folder)
            if f.lower().endswith('.pdf')
        ]

    def _clear_content(self):
        """Clear current content"""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_step_1(self):
        """Step 1: PDF Selection with checkboxes"""
        self._clear_content()
        self.step_label.setText("Step 1: Select PDFs to Extract")

        if not self.pdf_files:
            no_pdfs_label = QLabel("No PDF files found in scan folder")
            no_pdfs_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_layout.addWidget(no_pdfs_label)
            self.next_button.setEnabled(False)
            return

        # Scrollable list of PDFs with checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self.pdf_checkboxes = []

        for pdf_path in self.pdf_files:
            pdf_name = os.path.basename(pdf_path)

            # Get PDF info
            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)
                doc.close()
                info_text = f"{pdf_name} ({page_count} pages)"
            except:
                info_text = f"{pdf_name} (unable to read)"

            checkbox = QCheckBox(info_text)
            checkbox.setProperty("pdf_path", pdf_path)
            checkbox.stateChanged.connect(self._update_selection)
            scroll_layout.addWidget(checkbox)
            self.pdf_checkboxes.append(checkbox)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        self.content_layout.addWidget(scroll)

        # Select/Deselect all
        select_layout = QHBoxLayout()
        select_all = QPushButton("Select All")
        select_all.clicked.connect(lambda: self._select_all(True))
        deselect_all = QPushButton("Deselect All")
        deselect_all.clicked.connect(lambda: self._select_all(False))
        select_layout.addWidget(select_all)
        select_layout.addWidget(deselect_all)
        select_layout.addStretch()
        self.content_layout.addLayout(select_layout)

        self.next_button.setText("Extract Pages")
        self.back_button.setEnabled(False)

    def _select_all(self, checked):
        """Select or deselect all PDFs"""
        for checkbox in self.pdf_checkboxes:
            checkbox.setChecked(checked)

    def _update_selection(self):
        """Update selected PDFs list"""
        self.selected_pdfs = [
            cb.property("pdf_path")
            for cb in self.pdf_checkboxes
            if cb.isChecked()
        ]
        self.next_button.setEnabled(len(self.selected_pdfs) > 0)

    def _show_step_2(self):
        """Step 2: Extraction Progress"""
        self._clear_content()
        self.step_label.setText("Step 2: Extracting Pages...")

        self.progress_label = QLabel("Preparing extraction...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.content_layout.addWidget(self.progress_bar)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.content_layout.addWidget(self.log_text)

        self.next_button.setEnabled(False)
        self.back_button.setEnabled(False)
        self.close_button.setEnabled(False)

        # Start extraction in background
        QTimer.singleShot(100, self._extract_pdfs)

    def _extract_pdfs(self):
        """Extract pages from selected PDFs"""
        scan_folder = self.config_manager.get_setting("DocumentProcessing", "scan_folder")
        total_pdfs = len(self.selected_pdfs)
        self.extraction_results = []

        for idx, pdf_path in enumerate(self.selected_pdfs):
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            self.progress_label.setText(f"Extracting {pdf_name}... ({idx+1}/{total_pdfs})")
            self.progress_bar.setValue(int((idx / total_pdfs) * 100))
            QApplication.processEvents()

            try:
                doc = fitz.open(pdf_path)
                page_count = len(doc)

                self.log_text.appendPlainText(f"\nExtracting {pdf_name} ({page_count} pages)...")

                extracted_pages = []
                for page_num in range(page_count):
                    page = doc[page_num]

                    # Render at 300 DPI
                    zoom = 300 / 72
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)

                    # Save as PNG
                    output_name = f"{pdf_name}_page_{page_num+1:03d}.png"
                    output_path = os.path.join(scan_folder, output_name)
                    pix.save(output_path)

                    extracted_pages.append(output_path)
                    self.log_text.appendPlainText(f"  Page {page_num+1} -> {output_name}")
                    QApplication.processEvents()

                doc.close()

                self.extraction_results.append({
                    'pdf_name': pdf_name,
                    'page_count': page_count,
                    'extracted_pages': extracted_pages,
                    'success': True
                })

                self.log_text.appendPlainText(f"✓ Completed {pdf_name}")

            except Exception as e:
                self.log_text.appendPlainText(f"✗ Error extracting {pdf_name}: {e}")
                self.extraction_results.append({
                    'pdf_name': pdf_name,
                    'success': False,
                    'error': str(e)
                })

        self.progress_bar.setValue(100)
        self.progress_label.setText("Extraction Complete!")
        self.log_text.appendPlainText("\nAll extractions finished.")

        self.next_button.setText("Continue")
        self.next_button.setEnabled(True)
        self.close_button.setEnabled(True)

    def _show_step_3(self):
        """Step 3: Completion Summary"""
        self._clear_content()
        self.step_label.setText("Step 3: Extraction Summary")

        # Summary
        summary_text = QLabel()
        successful = sum(1 for r in self.extraction_results if r['success'])
        failed = len(self.extraction_results) - successful
        total_pages = sum(r.get('page_count', 0) for r in self.extraction_results if r['success'])

        summary_html = f"""
        <h3>Extraction Complete</h3>
        <p><b>PDFs Processed:</b> {len(self.extraction_results)}</p>
        <p><b>Successful:</b> {successful}</p>
        <p><b>Failed:</b> {failed}</p>
        <p><b>Total Pages Extracted:</b> {total_pages}</p>
        """
        summary_text.setText(summary_html)
        summary_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(summary_text)

        # Details
        details_label = QLabel("<b>Details:</b>")
        self.content_layout.addWidget(details_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        for result in self.extraction_results:
            if result['success']:
                text = f"✓ {result['pdf_name']}: {result['page_count']} pages extracted"
            else:
                text = f"✗ {result['pdf_name']}: {result.get('error', 'Unknown error')}"

            label = QLabel(text)
            scroll_layout.addWidget(label)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        self.content_layout.addWidget(scroll)

        # Action buttons
        action_layout = QHBoxLayout()

        send_button = QPushButton("Send to Convert Scans")
        send_button.clicked.connect(self._send_to_conversion)
        action_layout.addWidget(send_button)

        action_layout.addStretch()
        self.content_layout.addLayout(action_layout)

        self.next_button.setVisible(False)
        self.back_button.setEnabled(False)

    def _send_to_conversion(self):
        """Open ConvertImagesWindow with extracted images"""
        show_information(
            self,
            "Open Convert Scans",
            "Close this window and click 'Convert Scans' to process the extracted images."
        )
        self.close()

    def _go_next(self):
        """Navigate to next step"""
        if self.current_step == 1:
            if not self.selected_pdfs:
                show_warning(self, "No PDFs Selected", "Please select at least one PDF to extract.")
                return
            self.current_step = 2
            self._show_step_2()
        elif self.current_step == 2:
            self.current_step = 3
            self._show_step_3()

    def _go_back(self):
        """Navigate to previous step"""
        if self.current_step > 1:
            self.current_step -= 1
            if self.current_step == 1:
                self._show_step_1()
            elif self.current_step == 2:
                self._show_step_2()


class ImageGalleryWidget(QWidget):
    """
    Phase 3: Image Gallery (Left Panel)
    Shows all available images with search, sort, checkboxes, and status badges.
    """
    image_selected = pyqtSignal(str)  # file_path
    image_toggled = pyqtSignal(str, bool)  # file_path, checked

    def __init__(self, analysis_db: 'AnalysisDB' = None, parent=None):
        super().__init__(parent)
        self.analysis_db = analysis_db
        self.all_images = []  # List[Dict] - full image metadata
        self.filtered_images = []  # List[Dict] - after search/sort
        self.checked_files = set()  # Set[str] - file paths that are checked
        self.current_file = None  # Currently selected file path
        self._init_ui()

    def _init_ui(self):
        """Initialize the image gallery UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("Available Pages")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #111827;")
        layout.addWidget(title_label)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search by filename...")
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.setStyleSheet("""
            QLineEdit {
                padding: 6px;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                background-color: white;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #2563EB;
            }
        """)
        layout.addWidget(self.search_box)

        # Sort dropdown
        sort_layout = QHBoxLayout()
        sort_label = QLabel("Sort:")
        sort_label.setStyleSheet("font-size: 9pt; color: #6B7280;")
        sort_layout.addWidget(sort_label)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Date", "Name", "Type"])
        self.sort_combo.currentTextChanged.connect(self._on_sort_changed)
        self.sort_combo.setStyleSheet("""
            QComboBox {
                padding: 4px;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                background-color: white;
                font-size: 9pt;
            }
            QComboBox:hover {
                border: 1px solid #2563EB;
            }
        """)
        sort_layout.addWidget(self.sort_combo, 1)
        layout.addLayout(sort_layout)

        # Image list (QListWidget with custom items)
        self.image_list = QListWidget()
        self.image_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                background-color: white;
                outline: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #E5E7EB;
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #DBEAFE;
                border: 2px solid #2563EB;
            }
            QListWidget::item:hover {
                background-color: #F3F4F6;
            }
        """)
        self.image_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.image_list)

        # Count label
        self.count_label = QLabel("Showing: 0 of 0")
        self.count_label.setStyleSheet("font-size: 9pt; color: #6B7280;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)

        # Bulk action buttons
        bulk_layout = QHBoxLayout()

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.select_all_button.clicked.connect(self._on_select_all)
        bulk_layout.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        self.clear_selection_button.clicked.connect(self._on_clear_selection)
        bulk_layout.addWidget(self.clear_selection_button)

        layout.addLayout(bulk_layout)

        # Status badge legend
        layout.addSpacing(10)
        legend_label = QLabel("<b>Status:</b>")
        legend_label.setStyleSheet("font-size: 9pt; color: #374151;")
        layout.addWidget(legend_label)

        badge_layout = QVBoxLayout()
        badge_layout.setSpacing(3)

        analyzed_label = QLabel("🟢 Analyzed")
        analyzed_label.setStyleSheet("font-size: 9pt; color: #374151;")
        badge_layout.addWidget(analyzed_label)

        unanalyzed_label = QLabel("⭘ Unanalyzed")
        unanalyzed_label.setStyleSheet("font-size: 9pt; color: #374151;")
        badge_layout.addWidget(unanalyzed_label)

        failed_label = QLabel("🔴 Failed")
        failed_label.setStyleSheet("font-size: 9pt; color: #374151;")
        badge_layout.addWidget(failed_label)

        layout.addLayout(badge_layout)
        layout.addStretch(1)

    def set_images(self, image_paths: List[str]):
        """
        Set the list of images to display in the gallery.

        Args:
            image_paths: List of file paths
        """
        self.all_images = []

        for path in image_paths:
            # Get analysis status from database
            status = 'unanalyzed'
            analysis_info = None

            if self.analysis_db:
                analysis_info = self.analysis_db.get_analysis(path)
                if analysis_info:
                    status = 'analyzed'

            # Extract filename and basic info
            filename = os.path.basename(path)

            # Get file modification time for sorting
            try:
                mod_time = os.path.getmtime(path)
            except:
                mod_time = 0

            image_data = {
                'file_path': path,
                'filename': filename,
                'status': status,
                'mod_time': mod_time,
                'document_type': analysis_info.get('document_type', '') if analysis_info else '',
                'analysis_info': analysis_info
            }

            self.all_images.append(image_data)

        # Apply initial sort and filter
        self._apply_filters()

    def _apply_filters(self):
        """Apply search and sort filters to the image list"""
        # Start with all images
        filtered = list(self.all_images)

        # Apply search filter
        search_text = self.search_box.text().lower()
        if search_text:
            filtered = [img for img in filtered if search_text in img['filename'].lower()]

        # Apply sort
        sort_mode = self.sort_combo.currentText()
        if sort_mode == "Date":
            filtered.sort(key=lambda x: x['mod_time'], reverse=True)
        elif sort_mode == "Name":
            filtered.sort(key=lambda x: x['filename'])
        elif sort_mode == "Type":
            filtered.sort(key=lambda x: x['document_type'] or '')

        self.filtered_images = filtered
        self._refresh_list()

    def _refresh_list(self):
        """Refresh the QListWidget with current filtered images"""
        self.image_list.clear()

        for img_data in self.filtered_images:
            item = QListWidgetItem()

            # Create custom widget for the list item
            item_widget = self._create_list_item_widget(img_data)

            item.setSizeHint(item_widget.sizeHint())
            self.image_list.addItem(item)
            self.image_list.setItemWidget(item, item_widget)

            # Store file path in item data
            item.setData(Qt.ItemDataRole.UserRole, img_data['file_path'])

        # Update count label
        total = len(self.all_images)
        showing = len(self.filtered_images)
        self.count_label.setText(f"Showing: {showing} of {total}")

        # Restore selection highlight
        if self.current_file:
            self._highlight_current()

    def _create_list_item_widget(self, img_data: Dict) -> QWidget:
        """
        Create a custom widget for a list item showing checkbox, thumbnail, filename, and status.

        Args:
            img_data: Dictionary with image metadata

        Returns:
            QWidget containing the item UI
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Checkbox
        checkbox = QCheckBox()
        checkbox.setChecked(img_data['file_path'] in self.checked_files)
        checkbox.stateChanged.connect(
            lambda state, path=img_data['file_path']: self._on_checkbox_changed(path, state)
        )
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        layout.addWidget(checkbox)

        # Thumbnail (80x100px)
        thumbnail_label = QLabel()
        try:
            pixmap = QPixmap(img_data['file_path'])
            if not pixmap.isNull():
                scaled = pixmap.scaled(60, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                thumbnail_label.setPixmap(scaled)
            else:
                thumbnail_label.setText("No\nPreview")
                thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except:
            thumbnail_label.setText("Error")
            thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        thumbnail_label.setFixedSize(60, 80)
        thumbnail_label.setStyleSheet("border: 1px solid #E5E7EB; background-color: #F9FAFB;")
        layout.addWidget(thumbnail_label)

        # Right side: filename and status
        right_layout = QVBoxLayout()
        right_layout.setSpacing(3)

        # Filename
        filename_label = QLabel(img_data['filename'])
        filename_label.setStyleSheet("font-size: 9pt; font-weight: bold; color: #111827;")
        filename_label.setWordWrap(True)
        right_layout.addWidget(filename_label)

        # Status badge
        status = img_data['status']
        if status == 'analyzed':
            badge_text = "🟢 Analyzed"
            badge_color = "#059669"
        elif status == 'failed':
            badge_text = "🔴 Failed"
            badge_color = "#DC2626"
        else:
            badge_text = "⭘ Unanalyzed"
            badge_color = "#6B7280"

        status_label = QLabel(badge_text)
        status_label.setStyleSheet(f"font-size: 8pt; color: {badge_color};")
        right_layout.addWidget(status_label)

        right_layout.addStretch(1)
        layout.addLayout(right_layout, 1)

        return widget

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle clicking on an image item"""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self.current_file = file_path
            self.image_selected.emit(file_path)

    def _on_checkbox_changed(self, file_path: str, state: int):
        """Handle checkbox state change"""
        checked = (state == Qt.CheckState.Checked.value)

        if checked:
            self.checked_files.add(file_path)
        else:
            self.checked_files.discard(file_path)

        self.image_toggled.emit(file_path, checked)

    def _on_search_changed(self, text: str):
        """Handle search text change"""
        self._apply_filters()

    def _on_sort_changed(self, sort_mode: str):
        """Handle sort mode change"""
        self._apply_filters()

    def _on_select_all(self):
        """Select all visible images"""
        for img_data in self.filtered_images:
            self.checked_files.add(img_data['file_path'])
        self._refresh_list()

        # Emit signals for all checked files
        for img_data in self.filtered_images:
            self.image_toggled.emit(img_data['file_path'], True)

    def _on_clear_selection(self):
        """Clear all selections"""
        # Store files that were checked
        previously_checked = list(self.checked_files)

        self.checked_files.clear()
        self._refresh_list()

        # Emit signals for all unchecked files
        for file_path in previously_checked:
            self.image_toggled.emit(file_path, False)

    def _highlight_current(self):
        """Highlight the currently selected item"""
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path == self.current_file:
                self.image_list.setCurrentItem(item)
                break

    def set_current_file(self, file_path: str):
        """Set the currently selected file (for external updates)"""
        self.current_file = file_path
        self._highlight_current()

    def get_checked_files(self) -> List[str]:
        """Get list of checked file paths"""
        return list(self.checked_files)

    def set_checked_files(self, file_paths: List[str]):
        """Set which files are checked"""
        self.checked_files = set(file_paths)
        self._refresh_list()


class MetadataDisplayWidget(QWidget):
    """
    Phase 4: Metadata Display Widget (Right Panel)
    Shows AI analysis results, current bundle, and action buttons.
    """
    re_analyze_requested = pyqtSignal(str)  # file_path
    thumbnail_clicked = pyqtSignal(str)  # file_path from bundle thumbnail

    def __init__(self, analysis_db: 'AnalysisDB' = None, parent=None):
        super().__init__(parent)
        self.analysis_db = analysis_db
        self.current_file_path = None
        self.current_bundle_files = []  # List of file paths in current bundle
        self._init_ui()

    def _init_ui(self):
        """Initialize the metadata display UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Create scroll area for metadata content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        # Container widget for scrollable content
        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)

        # === AI ANALYSIS CARD ===
        self.analysis_card = self._create_analysis_card()
        self.content_layout.addWidget(self.analysis_card)

        # === CURRENT BUNDLE SECTION ===
        self.bundle_card = self._create_bundle_card()
        self.content_layout.addWidget(self.bundle_card)

        self.content_layout.addStretch(1)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    def _create_analysis_card(self) -> QWidget:
        """Create the AI Analysis card"""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #F9FAFB;
                border-radius: 6px;
                border: 1px solid #E5E7EB;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Section title
        title_label = QLabel("AI Analysis")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #111827; background: transparent; border: none;")
        layout.addWidget(title_label)

        # Confidence badge
        self.confidence_badge = QLabel("⭘ No Analysis")
        self.confidence_badge.setStyleSheet("""
            font-size: 10pt;
            font-weight: bold;
            color: #6B7280;
            background: transparent;
            border: none;
            padding: 4px;
        """)
        layout.addWidget(self.confidence_badge)

        # Metadata fields container
        self.metadata_container = QWidget()
        self.metadata_container.setStyleSheet("background: transparent; border: none;")
        self.metadata_layout = QVBoxLayout(self.metadata_container)
        self.metadata_layout.setContentsMargins(0, 8, 0, 0)
        self.metadata_layout.setSpacing(6)

        # Document Type
        self.doc_type_label = QLabel("Document Type: --")
        self.doc_type_label.setStyleSheet("font-size: 10pt; color: #374151; background: transparent; border: none;")
        self.metadata_layout.addWidget(self.doc_type_label)

        # Company
        self.company_label = QLabel("Company: --")
        self.company_label.setStyleSheet("font-size: 10pt; color: #374151; background: transparent; border: none;")
        self.metadata_layout.addWidget(self.company_label)

        # Date
        self.date_label = QLabel("Date: --")
        self.date_label.setStyleSheet("font-size: 10pt; color: #374151; background: transparent; border: none;")
        self.metadata_layout.addWidget(self.date_label)

        # Page number
        self.page_label = QLabel("Page: --")
        self.page_label.setStyleSheet("font-size: 10pt; color: #374151; background: transparent; border: none;")
        self.metadata_layout.addWidget(self.page_label)

        # Rotation status
        self.rotation_label = QLabel("Rotation: --")
        self.rotation_label.setStyleSheet("font-size: 10pt; color: #374151; background: transparent; border: none;")
        self.metadata_layout.addWidget(self.rotation_label)

        layout.addWidget(self.metadata_container)

        # Re-analyze button
        self.reanalyze_button = QPushButton("↻ Re-analyze")
        self.reanalyze_button.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 9pt;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
        self.reanalyze_button.clicked.connect(self._on_reanalyze_clicked)
        layout.addWidget(self.reanalyze_button)

        return card

    def _create_bundle_card(self) -> QWidget:
        """Create the Current Bundle card"""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #F9FAFB;
                border-radius: 6px;
                border: 1px solid #E5E7EB;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Section title
        title_label = QLabel("Current Bundle")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #111827; background: transparent; border: none;")
        layout.addWidget(title_label)

        # Bundle count label
        self.bundle_count_label = QLabel("0 pages included")
        self.bundle_count_label.setStyleSheet("font-size: 10pt; color: #6B7280; background: transparent; border: none;")
        layout.addWidget(self.bundle_count_label)

        # Scroll area for bundle thumbnails
        bundle_scroll = QScrollArea()
        bundle_scroll.setWidgetResizable(True)
        bundle_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bundle_scroll.setMaximumHeight(300)
        bundle_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        # Container for thumbnails
        self.bundle_thumbnails_container = QWidget()
        self.bundle_thumbnails_container.setStyleSheet("background: transparent; border: none;")
        self.bundle_thumbnails_layout = QVBoxLayout(self.bundle_thumbnails_container)
        self.bundle_thumbnails_layout.setContentsMargins(0, 0, 0, 0)
        self.bundle_thumbnails_layout.setSpacing(8)
        self.bundle_thumbnails_layout.addStretch(1)

        bundle_scroll.setWidget(self.bundle_thumbnails_container)
        layout.addWidget(bundle_scroll)

        return card

    def _create_bundle_thumbnail_widget(self, file_path: str) -> QWidget:
        """Create a thumbnail widget for a bundle file"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
            }
            QWidget:hover {
                background-color: #F3F4F6;
                border: 1px solid #2563EB;
            }
        """)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)

        # Make widget clickable
        widget.mousePressEvent = lambda event: self.thumbnail_clicked.emit(file_path)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        # Thumbnail
        thumbnail_label = QLabel()
        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(50, 70, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                thumbnail_label.setPixmap(scaled)
            else:
                thumbnail_label.setText("No\nPreview")
                thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except:
            thumbnail_label.setText("Error")
            thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        thumbnail_label.setFixedSize(50, 70)
        thumbnail_label.setStyleSheet("border: 1px solid #E5E7EB; background-color: #F9FAFB;")
        layout.addWidget(thumbnail_label)

        # Filename
        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setStyleSheet("font-size: 9pt; color: #111827; background: transparent; border: none;")
        filename_label.setWordWrap(True)
        layout.addWidget(filename_label, 1)

        return widget

    def set_current_file(self, file_path: str):
        """
        Update the display with metadata for the current file.

        Args:
            file_path: Path to the current file
        """
        self.current_file_path = file_path

        if not self.analysis_db:
            self._show_no_analysis()
            return

        # Get analysis from database
        analysis = self.analysis_db.get_analysis(file_path)

        if not analysis:
            self._show_no_analysis()
            return

        # Update confidence badge
        confidence_score = analysis.get('confidence_score')
        if confidence_score is not None:
            confidence_pct = int(confidence_score * 100)

            # Color-code based on confidence
            if confidence_score >= 0.8:
                badge_color = "#059669"  # Green
                badge_icon = "🟢"
                confidence_level = "HIGH CONFIDENCE"
            elif confidence_score >= 0.5:
                badge_color = "#F59E0B"  # Yellow
                badge_icon = "🟡"
                confidence_level = "MEDIUM CONFIDENCE"
            else:
                badge_color = "#DC2626"  # Red
                badge_icon = "🔴"
                confidence_level = "LOW CONFIDENCE"

            self.confidence_badge.setText(f"{badge_icon} {confidence_level} ({confidence_pct}%)")
            self.confidence_badge.setStyleSheet(f"""
                font-size: 10pt;
                font-weight: bold;
                color: {badge_color};
                background: transparent;
                border: none;
                padding: 4px;
            """)
        else:
            self.confidence_badge.setText("⭘ Confidence: Unknown")
            self.confidence_badge.setStyleSheet("""
                font-size: 10pt;
                font-weight: bold;
                color: #6B7280;
                background: transparent;
                border: none;
                padding: 4px;
            """)

        # Update metadata fields
        doc_type = analysis.get('document_type', '--')
        self.doc_type_label.setText(f"Document Type: {doc_type}")

        company = analysis.get('company', '--')
        self.company_label.setText(f"Company: {company}")

        doc_date = analysis.get('document_date', '--')
        self.date_label.setText(f"Date: {doc_date}")

        # Page number
        page_num = analysis.get('page_number')
        total_pages = analysis.get('total_pages')
        if page_num and total_pages:
            self.page_label.setText(f"Page: {page_num} of {total_pages}")
        elif page_num:
            self.page_label.setText(f"Page: {page_num}")
        else:
            self.page_label.setText("Page: --")

        # Rotation status
        rotation_needed = analysis.get('rotation_needed', False)
        suggested_rotation = analysis.get('suggested_rotation', 0)
        if rotation_needed and suggested_rotation:
            self.rotation_label.setText(f"Rotation: {suggested_rotation}° suggested")
            self.rotation_label.setStyleSheet("font-size: 10pt; color: #F59E0B; background: transparent; border: none;")
        else:
            self.rotation_label.setText("Rotation: None needed ✓")
            self.rotation_label.setStyleSheet("font-size: 10pt; color: #059669; background: transparent; border: none;")

    def _show_no_analysis(self):
        """Show placeholder when no analysis data is available"""
        self.confidence_badge.setText("⭘ No Analysis Data")
        self.confidence_badge.setStyleSheet("""
            font-size: 10pt;
            font-weight: bold;
            color: #6B7280;
            background: transparent;
            border: none;
            padding: 4px;
        """)

        self.doc_type_label.setText("Document Type: --")
        self.company_label.setText("Company: --")
        self.date_label.setText("Date: --")
        self.page_label.setText("Page: --")
        self.rotation_label.setText("Rotation: --")
        self.rotation_label.setStyleSheet("font-size: 10pt; color: #374151; background: transparent; border: none;")

    def set_bundle_files(self, file_paths: List[str]):
        """
        Update the bundle display with the current bundle files.

        Args:
            file_paths: List of file paths in the current bundle
        """
        self.current_bundle_files = file_paths

        # Update count label
        count = len(file_paths)
        self.bundle_count_label.setText(f"{count} page{'s' if count != 1 else ''} included")

        # Clear existing thumbnails
        while self.bundle_thumbnails_layout.count() > 1:  # Keep the stretch
            item = self.bundle_thumbnails_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new thumbnails
        for file_path in file_paths:
            thumbnail_widget = self._create_bundle_thumbnail_widget(file_path)
            self.bundle_thumbnails_layout.insertWidget(self.bundle_thumbnails_layout.count() - 1, thumbnail_widget)

    def _on_reanalyze_clicked(self):
        """Handle re-analyze button click"""
        if self.current_file_path:
            self.re_analyze_requested.emit(self.current_file_path)


class ConvertImagesWindow(QMainWindow):
    processing_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        timeout = float(self.config_manager.get_setting('Ollama', 'timeout', '300'))
        self.ollama_service = OllamaService(
            base_url=self.config_manager.get_setting('Ollama', 'base_url'),
            timeout=timeout
        )
        self.file_processor = FileProcessor(self.config_manager)
        self.metadata_db = MetadataDB()  # Initialize metadata database for caching

        # Phase 7: Bundle suggestion services
        self.analysis_db = AnalysisDB()
        self.bundling_service = BundlingService(self.analysis_db)

        # Analysis service for pre-processing files
        from analysis_service import AnalysisService
        self.analysis_service = AnalysisService(self.config_manager, self.analysis_db, self.metadata_db)

        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        self.setWindowTitle(f"{self.app_name} - Convert Images")
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        width = int(self.config_manager.get_setting('GUI', 'window_width', '1024'))
        height = int(self.config_manager.get_setting('GUI', 'window_height', '768'))
        self.setGeometry(100, 100, width, height)

        # Phase 2: Set minimum window size for three-column layout
        self.setMinimumSize(1200, 700)

        # Workflow state
        self.current_step = WorkflowStep.BUNDLE_SUGGESTIONS  # Phase 7: Start with bundle suggestions

        # Document data
        self.all_files = []  # All PNG files to process
        self.current_file_index = 0  # Current position in all_files
        self.current_group = []  # Group being built incrementally
        self.current_page_path = None  # Currently displayed page
        self.completed_groups = []  # Finalized groups

        # Metadata
        self.extracted_metadata = {}

        # Page ordering data (Phase 1)
        self.page_metadata_list = []  # List[Dict] - metadata for each page including detected page numbers
        self.original_page_order = []  # List[str] - original order backup for reset functionality

        # Zoom functionality (Phase 8: Enhanced zoom controls)
        self.zoom_level = 1.0  # 1.0 = 100%, 0.5 = 50%, 2.0 = 200%
        self.zoom_min = 0.25  # Minimum zoom (25%)
        self.zoom_max = 4.0   # Maximum zoom (400%)
        self.zoom_step = 0.25  # Zoom increment (25%)
        self.zoom_mode = 'custom'  # 'fit_width', 'fit_height', 'fit_window', 'custom'
        self.zoom_custom_percent = 100  # Custom zoom percentage (25-400)

        # Rotation state (Phase 8)
        self.rotation_states = {}  # Track rotation per file path

        # Store raw Ollama requests and responses for debugging
        self.last_ollama_request = None
        self.last_ollama_response = None
        self.last_ollama_response_type = ""

        # Auto-approval state
        self.auto_approval_timer = None
        self.auto_approval_countdown = 0
        self.auto_approval_button = None
        self.auto_approval_original_text = ""

        self._init_ui()

        # Phase 8: Setup keyboard shortcuts
        self._setup_keyboard_shortcuts()

        # Auto-start import scans after UI is initialized
        QTimer.singleShot(100, self._scan_and_group)

    def _init_ui(self):
        """Initialize the three-step workflow UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)

        # ===== STEP HEADER =====
        step_header_layout = QHBoxLayout()
        self.step_title_label = QLabel("Document Stitching")
        self.step_title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #2563EB;")
        step_header_layout.addWidget(self.step_title_label)

        step_header_layout.addSpacing(15)

        # Auto-approval toggle button (play/pause icon)
        self.auto_approval_toggle = QPushButton()
        self._update_auto_approval_toggle_icon()  # Set initial icon based on current setting
        self.auto_approval_toggle.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "border: none; "
            "padding: 5px; "
            "font-size: 14pt; "
            "}"
            "QPushButton:hover { "
            "background-color: #f0f0f0; "
            "border-radius: 3px; "
            "}"
        )
        self.auto_approval_toggle.setFixedSize(32, 32)
        self.auto_approval_toggle.clicked.connect(self._on_toggle_auto_approval)
        step_header_layout.addWidget(self.auto_approval_toggle)

        step_header_layout.addSpacing(10)

        # Header back button (icon only, subtle)
        self.header_back_button = QPushButton()
        self.header_back_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.header_back_button.setStyleSheet(
            "QPushButton { "
            "background-color: transparent; "
            "border: 1px solid #ccc; "
            "border-radius: 3px; "
            "padding: 5px; "
            "}"
            "QPushButton:hover { "
            "background-color: #f0f0f0; "
            "border: 1px solid #999; "
            "}"
        )
        self.header_back_button.setFixedSize(32, 32)
        self.header_back_button.setToolTip("Go back to previous step")
        self.header_back_button.setVisible(False)  # Hidden by default (Step 1 has no previous step)
        self.header_back_button.clicked.connect(self._on_header_back_clicked)
        step_header_layout.addWidget(self.header_back_button)

        step_header_layout.addStretch(1)

        self.step_indicator_label = QLabel("Step 1 of 5")
        self.step_indicator_label.setStyleSheet("font-size: 14pt; font-weight: bold; color: #666;")
        step_header_layout.addWidget(self.step_indicator_label)

        self.main_layout.addLayout(step_header_layout)
        self.main_layout.addSpacing(10)

        # ===== THUMBNAIL STRIP (220px high, horizontal) =====
        self.thumbnail_scroll = QScrollArea()
        self.thumbnail_scroll.setWidgetResizable(True)
        self.thumbnail_scroll.setFixedHeight(220)
        self.thumbnail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.thumbnail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QHBoxLayout(self.thumbnail_container)
        self.thumbnail_layout.setSpacing(10)
        self.thumbnail_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.thumbnail_scroll.setWidget(self.thumbnail_container)

        self.main_layout.addWidget(self.thumbnail_scroll)

        # ===== PHASE 7: Bundle Suggestions View =====
        self.bundle_suggestions_view = BundleSuggestionsView()
        self.bundle_suggestions_view.bundle_accepted.connect(self._on_bundle_accepted)
        self.bundle_suggestions_view.bundle_modified.connect(self._on_bundle_modified)
        self.bundle_suggestions_view.bundle_rejected.connect(self._on_bundle_rejected)
        self.bundle_suggestions_view.accept_all_high.connect(self._on_accept_all_high_confidence)
        self.bundle_suggestions_view.skip_to_manual.connect(self._on_skip_to_manual_workflow)
        self.bundle_suggestions_view.setVisible(False)  # Hidden by default
        self.main_layout.addWidget(self.bundle_suggestions_view)

        # ===== MAIN CONTENT AREA (dynamic based on step) =====
        # Phase 2: Use QSplitter for resizable three-column layout
        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)  # Prevent panels from collapsing completely
        self.content_splitter.setHandleWidth(8)  # Space between panels
        self.content_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #E5E7EB;
            }
            QSplitter::handle:hover {
                background-color: #D1D5DB;
            }
        """)

        # LEFT PANEL (changes per step)
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(250)  # Phase 2: Fixed width
        self.left_panel_layout = QVBoxLayout(self.left_panel)
        self.left_panel_layout.setContentsMargins(5, 5, 5, 5)
        # Add spacer to ensure panel has content
        self.left_panel_layout.addStretch()
        self.content_splitter.addWidget(self.left_panel)

        # CENTER: Large Page Preview with Zoom Controls
        # Create a container for the preview and zoom buttons
        preview_container = QWidget()
        preview_container.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
            }
        """)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(0)

        self.large_preview_label = QLabel()
        self.large_preview_label.setFrameShape(QFrame.Shape.Box)
        self.large_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.large_preview_label.setStyleSheet("background-color: #F9FAFB; border: 1px solid #E5E7EB;")
        self.large_preview_label.setMinimumSize(600, 500)  # Phase 2: Increased min width to 600px
        self.large_preview_label.setScaledContents(False)

        # Install event filter for mouse wheel zoom
        self.large_preview_label.installEventFilter(self)
        self.large_preview_label.setMouseTracking(True)

        preview_layout.addWidget(self.large_preview_label)

        # Create zoom control buttons (overlaid on top-right)
        self._setup_zoom_controls()

        self.content_splitter.addWidget(preview_container)

        # RIGHT PANEL (changes per step)
        self.right_panel = QWidget()
        self.right_panel.setFixedWidth(350)  # Phase 2: Fixed width
        self.right_panel_layout = QVBoxLayout(self.right_panel)
        self.right_panel_layout.setContentsMargins(5, 5, 5, 5)
        # Add spacer to ensure panel has content
        self.right_panel_layout.addStretch()
        self.content_splitter.addWidget(self.right_panel)

        # Phase 2: Explicitly prevent each widget from collapsing (must be done after widgets added)
        self.content_splitter.setCollapsible(0, False)  # Left panel
        self.content_splitter.setCollapsible(1, False)  # Center panel
        self.content_splitter.setCollapsible(2, False)  # Right panel

        # Phase 2: Set splitter proportions (left: 250, center: flexible, right: 350)
        # Initial sizes will be set based on window width
        # Use minimum stretch for fixed panels, higher for flexible center
        self.content_splitter.setStretchFactor(0, 1)  # Left panel: minimal stretch
        self.content_splitter.setStretchFactor(1, 3)  # Center panel: takes most extra space
        self.content_splitter.setStretchFactor(2, 1)  # Right panel: minimal stretch

        # Set initial sizes for panels (will be applied after window is shown)
        # Left: 250px, Center: remaining, Right: 350px
        QTimer.singleShot(100, self._apply_initial_splitter_sizes)

        # Add splitter to main layout
        self.main_layout.addWidget(self.content_splitter)

        # ===== STATUS BAR (persistent) =====
        status_bar_layout = QHBoxLayout()

        # Spinner
        self.spinner_label = QLabel()
        self.spinner_label.setFixedSize(24, 24)
        self.spinner_label.setVisible(False)
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self._update_spinner)
        self.spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_index = 0
        status_bar_layout.addWidget(self.spinner_label)

        # Status text
        self.status_label = QLabel("Ready to scan documents.")
        self.status_label.setStyleSheet("QLabel:hover { text-decoration: underline; }")
        self.status_label.setToolTip("Click to view raw Ollama response (when available)")
        self.status_label.mousePressEvent = self._on_status_clicked
        self.status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        status_bar_layout.addWidget(self.status_label)
        status_bar_layout.addStretch(1)

        self.main_layout.addLayout(status_bar_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setFormat("%p%")
        self.main_layout.addWidget(self.progress_bar)

        # Elapsed time tracking
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._update_elapsed_time)
        self.elapsed_seconds = 0

        # Store raw Ollama requests and responses for debugging
        self.last_ollama_request = None
        self.last_ollama_response = None
        self.last_ollama_response_type = ""

        # Initialize with loading UI (will transition to Step 1 after scan completes)
        self._setup_loading_ui()

    def _setup_zoom_controls(self):
        """Create enhanced zoom control toolbar overlaid on large preview (Phase 8)"""
        from PyQt6.QtWidgets import QComboBox, QSpinBox

        # Create container for zoom controls
        zoom_container = QWidget(self.large_preview_label)
        zoom_main_layout = QVBoxLayout(zoom_container)
        zoom_main_layout.setContentsMargins(5, 5, 5, 5)
        zoom_main_layout.setSpacing(3)

        # Top row: Zoom mode dropdown
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(3)

        self.zoom_mode_combo = QComboBox()
        self.zoom_mode_combo.addItem("Fit to Width", "fit_width")
        self.zoom_mode_combo.addItem("Fit to Height", "fit_height")
        self.zoom_mode_combo.addItem("Fit to Window", "fit_window")
        self.zoom_mode_combo.addItem("Custom %", "custom")
        self.zoom_mode_combo.setCurrentIndex(3)  # Default to custom
        self.zoom_mode_combo.currentIndexChanged.connect(self._on_zoom_mode_changed)
        self.zoom_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(255, 255, 255, 230);
                color: #333;
                border: 1px solid #999;
                border-radius: 3px;
                padding: 5px;
                font-size: 9pt;
                min-height: 25px;
            }
            QComboBox:hover {
                border: 2px solid #666;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        mode_layout.addWidget(self.zoom_mode_combo)
        zoom_main_layout.addLayout(mode_layout)

        # Bottom row: Zoom buttons and spinner
        control_layout = QHBoxLayout()
        control_layout.setSpacing(2)

        # Button style
        button_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 230);
                color: #333;
                border: 1px solid #999;
                border-radius: 5px;
                padding: 6px;
                font-size: 16pt;
                font-weight: bold;
                min-width: 35px;
                max-width: 35px;
                min-height: 35px;
                max-height: 35px;
            }
            QPushButton:hover {
                background-color: rgba(240, 240, 240, 250);
                border: 2px solid #666;
            }
            QPushButton:pressed {
                background-color: rgba(220, 220, 220, 250);
            }
            QPushButton:disabled {
                background-color: rgba(200, 200, 200, 150);
                color: #999;
                border: 1px solid #ccc;
            }
        """

        # Zoom Out button
        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setStyleSheet(button_style)
        self.zoom_out_button.setToolTip("Zoom Out (Ctrl+-)")
        self.zoom_out_button.clicked.connect(self._zoom_out)
        control_layout.addWidget(self.zoom_out_button)

        # Zoom percentage spinner
        self.zoom_percent_spin = QSpinBox()
        self.zoom_percent_spin.setRange(25, 400)
        self.zoom_percent_spin.setSingleStep(25)
        self.zoom_percent_spin.setValue(100)
        self.zoom_percent_spin.setSuffix("%")
        self.zoom_percent_spin.valueChanged.connect(self._on_zoom_percent_changed)
        self.zoom_percent_spin.setStyleSheet("""
            QSpinBox {
                background-color: rgba(255, 255, 255, 230);
                color: #333;
                border: 1px solid #999;
                border-radius: 5px;
                padding: 5px;
                font-size: 10pt;
                font-weight: bold;
                min-width: 65px;
                max-width: 65px;
                min-height: 35px;
                max-height: 35px;
            }
            QSpinBox:hover {
                border: 2px solid #666;
            }
        """)
        control_layout.addWidget(self.zoom_percent_spin)

        # Zoom In button
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setStyleSheet(button_style)
        self.zoom_in_button.setToolTip("Zoom In (Ctrl++)")
        self.zoom_in_button.clicked.connect(self._zoom_in)
        control_layout.addWidget(self.zoom_in_button)

        zoom_main_layout.addLayout(control_layout)

        # Position zoom controls in bottom-right corner
        zoom_container.setFixedSize(200, 75)
        zoom_container.move(self.large_preview_label.width() - 210, self.large_preview_label.height() - 85)
        zoom_container.raise_()
        zoom_container.show()

        # Store reference for repositioning on resize
        self.zoom_controls = zoom_container

    def _zoom_in(self):
        """Zoom in by one step"""
        if self.zoom_level < self.zoom_max:
            self.zoom_level = min(self.zoom_level + self.zoom_step, self.zoom_max)
            self._refresh_preview_zoom()

    def _zoom_out(self):
        """Zoom out by one step"""
        if self.zoom_level > self.zoom_min:
            self.zoom_level = max(self.zoom_level - self.zoom_step, self.zoom_min)
            self._refresh_preview_zoom()

    def _zoom_reset(self):
        """Reset zoom to 100%"""
        self.zoom_level = 1.0
        self._refresh_preview_zoom()

    def _refresh_preview_zoom(self):
        """Refresh the current preview image with current zoom level (Phase 8: Updated)"""
        if self.current_page_path and os.path.exists(self.current_page_path):
            self._display_page_in_large_preview(self.current_page_path, show_indicator=False)
        # Update button states
        self.zoom_in_button.setEnabled(self.zoom_level < self.zoom_max)
        self.zoom_out_button.setEnabled(self.zoom_level > self.zoom_min)
        # Update zoom percentage spinner
        zoom_pct = int(self.zoom_level * 100)
        if hasattr(self, 'zoom_percent_spin'):
            self.zoom_percent_spin.blockSignals(True)  # Prevent recursive call
            self.zoom_percent_spin.setValue(zoom_pct)
            self.zoom_percent_spin.blockSignals(False)

    def eventFilter(self, obj, event):
        """Handle mouse wheel events for zooming"""
        if obj == self.large_preview_label and event.type() == event.Type.Wheel:
            # Get wheel delta (positive = zoom in, negative = zoom out)
            delta = event.angleDelta().y()

            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()

            return True  # Event handled

        return super().eventFilter(obj, event)

    def _on_zoom_mode_changed(self):
        """Handle zoom mode dropdown change (Phase 8)"""
        self.zoom_mode = self.zoom_mode_combo.currentData()
        self._apply_zoom_mode()

    def _on_zoom_percent_changed(self, value):
        """Handle zoom percentage spinner change (Phase 8)"""
        self.zoom_custom_percent = value
        if self.zoom_mode == 'custom':
            self.zoom_level = value / 100.0
            self._refresh_preview_zoom()

    def _apply_zoom_mode(self):
        """Apply current zoom mode (fit to width/height/window or custom) (Phase 8)"""
        if not self.current_page_path or not os.path.exists(self.current_page_path):
            return

        if self.zoom_mode == 'fit_width':
            # Calculate zoom to fit width
            pixmap = QPixmap(self.current_page_path)
            if not pixmap.isNull():
                available_width = self.large_preview_label.width() - 20  # padding
                self.zoom_level = available_width / pixmap.width()
                self._refresh_preview_zoom()
        elif self.zoom_mode == 'fit_height':
            # Calculate zoom to fit height
            pixmap = QPixmap(self.current_page_path)
            if not pixmap.isNull():
                available_height = self.large_preview_label.height() - 20  # padding
                self.zoom_level = available_height / pixmap.height()
                self._refresh_preview_zoom()
        elif self.zoom_mode == 'fit_window':
            # Calculate zoom to fit entire window
            pixmap = QPixmap(self.current_page_path)
            if not pixmap.isNull():
                available_width = self.large_preview_label.width() - 20
                available_height = self.large_preview_label.height() - 20
                zoom_width = available_width / pixmap.width()
                zoom_height = available_height / pixmap.height()
                self.zoom_level = min(zoom_width, zoom_height)  # Use smaller to fit both
                self._refresh_preview_zoom()
        elif self.zoom_mode == 'custom':
            # Use custom zoom level from spinner
            self.zoom_level = self.zoom_custom_percent / 100.0
            self._refresh_preview_zoom()

    def _update_zoom_control_position(self):
        """Update position of zoom controls to bottom-right corner (Phase 8: Updated dimensions)"""
        if hasattr(self, 'zoom_controls') and hasattr(self, 'large_preview_label'):
            # Position in bottom-right corner of preview label
            x_pos = max(self.large_preview_label.width() - 210, 0)
            y_pos = max(self.large_preview_label.height() - 85, 0)
            self.zoom_controls.move(x_pos, y_pos)

    def resizeEvent(self, event):
        """Handle window resize to reposition zoom controls and re-apply fit modes (Phase 8)"""
        super().resizeEvent(event)
        self._update_zoom_control_position()

        # Re-apply zoom mode if in fit mode (recalculate for new window size)
        if hasattr(self, 'zoom_mode') and self.zoom_mode in ['fit_width', 'fit_height', 'fit_window']:
            self._apply_zoom_mode()

    def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for navigation, actions, zoom, and bundles (Phase 6)"""
        from PyQt6.QtGui import QShortcut, QKeySequence

        # ===== NAVIGATION SHORTCUTS =====
        # Previous/Next image (gallery navigation)
        left_arrow_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        left_arrow_shortcut.activated.connect(self._navigate_previous_image)

        right_arrow_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        right_arrow_shortcut.activated.connect(self._navigate_next_image)

        # Jump 10 images
        pgup_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self)
        pgup_shortcut.activated.connect(lambda: self._jump_images(-10))

        pgdown_shortcut = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self)
        pgdown_shortcut.activated.connect(lambda: self._jump_images(10))

        # First/Last image
        home_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Home), self)
        home_shortcut.activated.connect(self._jump_to_first_image)

        end_shortcut = QShortcut(QKeySequence(Qt.Key.Key_End), self)
        end_shortcut.activated.connect(self._jump_to_last_image)

        # ===== ACTION SHORTCUTS =====
        # Include current page in bundle
        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_shortcut.activated.connect(self._shortcut_include_page)

        # Exclude current page from bundle
        delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        delete_shortcut.activated.connect(self._shortcut_exclude_page)

        # Approve/Continue to next step
        enter_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        enter_shortcut.activated.connect(self._shortcut_approve_continue)

        # Cancel/Back
        esc_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        esc_shortcut.activated.connect(self._shortcut_cancel_back)

        # ===== ZOOM SHORTCUTS =====
        # Zoom in (25% increment)
        zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        zoom_in_shortcut.activated.connect(self._zoom_in)

        # Zoom out (25% decrement)
        zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        zoom_out_shortcut.activated.connect(self._zoom_out)

        # Fit to window
        zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        zoom_reset_shortcut.activated.connect(lambda: self._set_zoom_mode_to_fit_window())

        # ===== BUNDLE SHORTCUTS (Step 0) =====
        # Accept all high confidence
        ctrl_a_shortcut = QShortcut(QKeySequence("Ctrl+A"), self)
        ctrl_a_shortcut.activated.connect(self._shortcut_accept_all_high)

        # Skip to manual workflow
        ctrl_d_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        ctrl_d_shortcut.activated.connect(self._shortcut_skip_to_manual)

        # ===== HELP SHORTCUT =====
        # Toggle shortcuts legend
        f1_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), self)
        f1_shortcut.activated.connect(self._toggle_shortcuts_legend)

        question_shortcut = QShortcut(QKeySequence("?"), self)
        question_shortcut.activated.connect(self._toggle_shortcuts_legend)

        # Store shortcuts for later reference
        self.keyboard_shortcuts = {
            'navigation': {
                'Left/Right Arrow': 'Previous/Next image',
                'Page Up/Down': 'Jump 10 images',
                'Home/End': 'First/Last image',
            },
            'actions': {
                'Space': 'Include current page in bundle',
                'Delete': 'Exclude current page from bundle',
                'Enter': 'Approve/Continue to next step',
                'Esc': 'Cancel/Back',
            },
            'zoom': {
                'Ctrl + +': 'Zoom in (25%)',
                'Ctrl + -': 'Zoom out (25%)',
                'Ctrl + 0': 'Fit to window',
            },
            'bundles': {
                'Ctrl + A': 'Accept all high confidence (Step 0)',
                'Ctrl + D': 'Skip to manual workflow (Step 0)',
            },
            'help': {
                'F1 or ?': 'Toggle shortcuts legend',
            }
        }

    # ===== KEYBOARD SHORTCUT HANDLER METHODS (Phase 6) =====

    def _navigate_previous_image(self):
        """Navigate to previous image in gallery (Left Arrow)"""
        if not self.all_files or not self.current_page_path:
            return

        try:
            current_idx = self.all_files.index(self.current_page_path)
            if current_idx > 0:
                prev_file = self.all_files[current_idx - 1]
                self._on_thumbnail_clicked(prev_file)
        except (ValueError, IndexError):
            pass

    def _navigate_next_image(self):
        """Navigate to next image in gallery (Right Arrow)"""
        if not self.all_files or not self.current_page_path:
            return

        try:
            current_idx = self.all_files.index(self.current_page_path)
            if current_idx < len(self.all_files) - 1:
                next_file = self.all_files[current_idx + 1]
                self._on_thumbnail_clicked(next_file)
        except (ValueError, IndexError):
            pass

    def _jump_images(self, offset):
        """Jump forward or backward by offset images (Page Up/Down)"""
        if not self.all_files or not self.current_page_path:
            return

        try:
            current_idx = self.all_files.index(self.current_page_path)
            new_idx = max(0, min(len(self.all_files) - 1, current_idx + offset))
            if new_idx != current_idx:
                target_file = self.all_files[new_idx]
                self._on_thumbnail_clicked(target_file)
        except (ValueError, IndexError):
            pass

    def _jump_to_first_image(self):
        """Jump to first image in gallery (Home)"""
        if self.all_files:
            self._on_thumbnail_clicked(self.all_files[0])

    def _jump_to_last_image(self):
        """Jump to last image in gallery (End)"""
        if self.all_files:
            self._on_thumbnail_clicked(self.all_files[-1])

    def _shortcut_include_page(self):
        """Include current page in bundle (Space)"""
        if self.current_step == WorkflowStep.STITCHING:
            if hasattr(self, 'include_button') and self.include_button.isVisible() and self.include_button.isEnabled():
                self.include_button.click()

    def _shortcut_exclude_page(self):
        """Exclude current page from bundle (Delete)"""
        if self.current_step == WorkflowStep.STITCHING:
            if hasattr(self, 'exclude_page_button') and self.exclude_page_button.isVisible() and self.exclude_page_button.isEnabled():
                self.exclude_page_button.click()

    def _shortcut_approve_continue(self):
        """Approve/Continue to next step (Enter)"""
        if self.current_step == WorkflowStep.STITCHING:
            # Try exclude_button (which is the "Approve" button in Step 1)
            if hasattr(self, 'exclude_button') and self.exclude_button.isVisible() and self.exclude_button.isEnabled():
                self.exclude_button.click()
        elif self.current_step == WorkflowStep.ORDERING:
            # Approve order button in Step 3
            if hasattr(self, 'approve_order_button') and self.approve_order_button.isVisible() and self.approve_order_button.isEnabled():
                self.approve_order_button.click()
        elif self.current_step == WorkflowStep.FINALIZATION:
            # Finalize button in Step 4
            if hasattr(self, 'finalize_button') and self.finalize_button.isVisible() and self.finalize_button.isEnabled():
                self.finalize_button.click()

    def _shortcut_cancel_back(self):
        """Cancel/Back to previous step (Esc)"""
        if hasattr(self, 'header_back_button') and self.header_back_button.isVisible():
            self.header_back_button.click()
        elif hasattr(self, 'cancel_request_button') and self.cancel_request_button.isVisible():
            self.cancel_request_button.click()

    def _shortcut_accept_all_high(self):
        """Accept all high confidence bundles (Ctrl+A in Step 0)"""
        if self.current_step == WorkflowStep.BUNDLE_SUGGESTIONS:
            if hasattr(self, 'bundle_suggestions_view'):
                self.bundle_suggestions_view._on_accept_all_high_clicked()

    def _shortcut_skip_to_manual(self):
        """Skip to manual workflow (Ctrl+D in Step 0)"""
        if self.current_step == WorkflowStep.BUNDLE_SUGGESTIONS:
            if hasattr(self, 'bundle_suggestions_view'):
                self.bundle_suggestions_view._on_skip_to_manual_clicked()

    def _toggle_shortcuts_legend(self):
        """Toggle visibility of keyboard shortcuts legend (F1 or ?)"""
        if hasattr(self, 'shortcuts_legend_widget'):
            self.shortcuts_legend_widget.setVisible(not self.shortcuts_legend_widget.isVisible())
        else:
            self._create_shortcuts_legend()
            self.shortcuts_legend_widget.setVisible(True)

    def _create_shortcuts_legend(self):
        """Create collapsible keyboard shortcuts legend widget (Phase 6)"""
        from PyQt6.QtWidgets import QGroupBox, QGridLayout

        # Create a collapsible group box
        self.shortcuts_legend_widget = QGroupBox("Keyboard Shortcuts")
        self.shortcuts_legend_widget.setCheckable(True)
        self.shortcuts_legend_widget.setChecked(True)
        self.shortcuts_legend_widget.setStyleSheet("""
            QGroupBox {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                margin-top: 10px;
                padding-top: 15px;
                font-size: 11pt;
                font-weight: bold;
                color: #374151;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                background-color: #F9FAFB;
            }
        """)

        legend_layout = QGridLayout()
        legend_layout.setSpacing(8)
        legend_layout.setContentsMargins(10, 10, 10, 10)

        row = 0
        for category, shortcuts in self.keyboard_shortcuts.items():
            # Category header
            category_label = QLabel(f"{category.upper()}")
            category_label.setStyleSheet("font-weight: bold; color: #2563EB; font-size: 10pt;")
            legend_layout.addWidget(category_label, row, 0, 1, 2)
            row += 1

            # Shortcuts in this category
            for shortcut_key, description in shortcuts.items():
                key_label = QLabel(shortcut_key)
                key_label.setStyleSheet("""
                    QLabel {
                        background-color: #FFFFFF;
                        border: 1px solid #D1D5DB;
                        border-radius: 3px;
                        padding: 3px 8px;
                        font-family: 'Consolas', monospace;
                        font-size: 9pt;
                        color: #111827;
                    }
                """)
                desc_label = QLabel(description)
                desc_label.setStyleSheet("font-size: 9pt; color: #6B7280;")

                legend_layout.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignLeft)
                legend_layout.addWidget(desc_label, row, 1, Qt.AlignmentFlag.AlignLeft)
                row += 1

        self.shortcuts_legend_widget.setLayout(legend_layout)

        # Add to main layout at the bottom
        self.main_layout.addWidget(self.shortcuts_legend_widget)

        # Don't set visibility here - let the caller (_toggle_shortcuts_legend) handle it

    def _set_zoom_mode_to_fit_window(self):
        """Set zoom mode to fit window (Ctrl+0 shortcut) (Phase 8)"""
        if hasattr(self, 'zoom_mode_combo'):
            # Find index of "fit_window" mode
            for i in range(self.zoom_mode_combo.count()):
                if self.zoom_mode_combo.itemData(i) == 'fit_window':
                    self.zoom_mode_combo.setCurrentIndex(i)
                    break

    # ===== ROTATION METHODS (PHASE 8) =====

    def _rotate_current_page(self, degrees):
        """
        Rotate the current page by specified degrees (90, 180, 270) (Phase 8).
        Rotation is display-only and stored in database - source file is NEVER modified.
        """
        if not self.current_page_path or not os.path.exists(self.current_page_path):
            return

        try:
            # Get current rotation from database
            current_rotation = self.metadata_db.get_rotation(self.current_page_path)

            # Calculate new rotation (cumulative)
            new_rotation = (current_rotation + degrees) % 360

            # Save rotation to database (NOT to file!)
            self.metadata_db.save_rotation(self.current_page_path, new_rotation)

            # Update in-memory state
            self.rotation_states[self.current_page_path] = new_rotation

            # Refresh preview with rotation applied
            self._refresh_preview_zoom()

            print(f"[Rotation] Set rotation for {os.path.basename(self.current_page_path)} to {new_rotation}° (display-only, source file unchanged)")

        except Exception as e:
            show_warning(
                self,
                "Rotation Failed",
                f"Could not save rotation: {e}"
            )
            print(f"[Rotation] Error: {e}")
            import traceback
            traceback.print_exc()

    # ===== VISUAL FEEDBACK METHODS (PHASE 6) =====

    def _flash_preview(self, color="#059669", duration=200):
        """Flash the preview area with a color to provide visual feedback (Phase 6)"""
        if not hasattr(self, 'large_preview_label'):
            return

        # Store original stylesheet
        original_style = self.large_preview_label.styleSheet()

        # Apply flash color
        flash_style = f"background-color: {color}; border: 3px solid {color};"
        self.large_preview_label.setStyleSheet(flash_style)

        # Reset after duration
        QTimer.singleShot(duration, lambda: self.large_preview_label.setStyleSheet(original_style))

    def _flash_thumbnail(self, file_path, color="#059669", duration=200):
        """Flash a specific thumbnail to provide visual feedback (Phase 6)"""
        # Find the thumbnail widget for this file
        for i in range(self.thumbnail_layout.count()):
            item = self.thumbnail_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, 'file_path') and widget.file_path == file_path:
                    # Store original stylesheet
                    original_style = widget.styleSheet()

                    # Apply flash color
                    flash_style = f"border: 3px solid {color}; background-color: {color};"
                    widget.setStyleSheet(flash_style)

                    # Reset after duration
                    QTimer.singleShot(duration, lambda w=widget, s=original_style: w.setStyleSheet(s))
                    break

    def _show_status_flash(self, message, color="#059669", duration=2000):
        """Show a temporary status message with color (Phase 6)"""
        # Store original status
        original_text = self.status_label.text()
        original_style = self.status_label.styleSheet()

        # Apply flash message
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        # Reset after duration
        QTimer.singleShot(duration, lambda: (
            self.status_label.setText(original_text),
            self.status_label.setStyleSheet(original_style)
        ))

    # ===== AUTO-APPROVAL METHODS =====

    def _update_auto_approval_toggle_icon(self):
        """Update the auto-approval toggle button icon based on current setting"""
        auto_approval_enabled = self.config_manager.get_setting("AutoApproval", "enable_automatic_approvals", "false")
        if auto_approval_enabled.lower() == "true":
            # Enabled - show pause/stop icon (can be stopped)
            self.auto_approval_toggle.setText("⏸")
            self.auto_approval_toggle.setToolTip("Auto-approval ENABLED\nClick to disable")
        else:
            # Disabled - show play icon (can be started)
            self.auto_approval_toggle.setText("▶")
            self.auto_approval_toggle.setToolTip("Auto-approval DISABLED\nClick to enable")

    def _on_toggle_auto_approval(self):
        """Toggle auto-approval setting and persist to config"""
        auto_approval_enabled = self.config_manager.get_setting("AutoApproval", "enable_automatic_approvals", "false")

        # Toggle the setting
        new_value = "false" if auto_approval_enabled.lower() == "true" else "true"
        self.config_manager.set_setting("AutoApproval", "enable_automatic_approvals", new_value)

        # Handle active countdown based on new state
        if new_value == "false":
            # Toggled OFF - stop any running auto-approval countdown but preserve button for potential restart
            self._stop_auto_approval(clear_button=False)
        else:
            # Toggled ON - restart countdown if there's a pending button
            if hasattr(self, 'auto_approval_button') and self.auto_approval_button:
                # There was a button waiting for auto-approval - restart the countdown
                if hasattr(self, 'auto_approval_original_text'):
                    self._start_auto_approval(self.auto_approval_button, self.auto_approval_original_text)

        # Update the icon
        self._update_auto_approval_toggle_icon()

        # Update the checkbox in the main window if it exists
        if hasattr(self, 'auto_approval_checkbox'):
            self.auto_approval_checkbox.setChecked(new_value == "true")

    def _start_auto_approval(self, button, button_text):
        """Start auto-approval countdown timer"""
        # Check if auto-approval is enabled
        auto_approval_enabled = self.config_manager.get_setting("AutoApproval", "enable_automatic_approvals", "false")
        if auto_approval_enabled.lower() != "true":
            return

        # Stop any existing timer
        self._stop_auto_approval()

        # Get delay from settings
        delay = int(self.config_manager.get_setting("AutoApproval", "automatic_approval_delay", "5"))

        # Setup countdown
        self.auto_approval_countdown = delay
        self.auto_approval_button = button
        self.auto_approval_original_text = button_text

        # Update button text with countdown
        self.auto_approval_button.setText(f"{button_text} ({self.auto_approval_countdown})")

        # Start timer (1000ms = 1 second)
        self.auto_approval_timer = QTimer(self)
        self.auto_approval_timer.timeout.connect(self._update_auto_approval_countdown)
        self.auto_approval_timer.start(1000)

    def _update_auto_approval_countdown(self):
        """Update countdown and auto-click when reaches 0"""
        self.auto_approval_countdown -= 1

        if self.auto_approval_countdown > 0:
            # Update button text
            self.auto_approval_button.setText(f"{self.auto_approval_original_text} ({self.auto_approval_countdown})")
        else:
            # Countdown complete - save button reference, stop timer, then click
            button_to_click = self.auto_approval_button
            self._stop_auto_approval()
            if button_to_click:
                button_to_click.click()

    def _stop_auto_approval(self, clear_button=True):
        """Stop and cleanup auto-approval timer

        Args:
            clear_button: If True, clear button reference. If False, preserve for potential restart.
        """
        if self.auto_approval_timer and self.auto_approval_timer.isActive():
            self.auto_approval_timer.stop()
            self.auto_approval_timer = None

        # Restore original button text if button still exists
        if self.auto_approval_button and hasattr(self, 'auto_approval_original_text'):
            self.auto_approval_button.setText(self.auto_approval_original_text)

        if clear_button:
            self.auto_approval_button = None
            self.auto_approval_original_text = None

        self.auto_approval_countdown = 0

    def closeEvent(self, event):
        self.processing_finished.emit()
        super().closeEvent(event)

    def _clear_panel(self, layout):
        """Clear all widgets from a layout"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _apply_initial_splitter_sizes(self):
        """Apply initial sizes to splitter panels (Phase 2)"""
        # Calculate sizes based on splitter's actual width
        splitter_width = self.content_splitter.width()
        left_width = 250
        right_width = 350
        # Center gets remaining space, but ensure it's at least 600px
        center_width = splitter_width - left_width - right_width
        if center_width < 600:
            # If not enough space, reduce side panels
            center_width = 600
            left_width = (splitter_width - 600) // 2
            right_width = splitter_width - 600 - left_width

        # Try moving splitter handles manually
        self.content_splitter.moveSplitter(left_width, 1)  # Move first handle to left_width position
        self.content_splitter.moveSplitter(left_width + center_width, 2)  # Move second handle

    def _setup_loading_ui(self):
        """Show full-window loading animation while importing scans"""
        # Update header
        self.step_title_label.setText("Importing Scans")
        self.step_indicator_label.setText("Step 1 of 5")

        # Clear all panels
        self._clear_panel(self.left_panel_layout)
        self._clear_panel(self.right_panel_layout)

        # Hide side panels completely
        self.left_panel.setVisible(False)
        self.right_panel.setVisible(False)

        # Create modern loading animation in center preview area
        # Clear any existing content
        self.large_preview_label.setMovie(None)
        self.large_preview_label.clear()

        # Create a container widget for centered loading animation
        loading_container = QWidget()
        loading_layout = QVBoxLayout(loading_container)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Large animated spinner
        self.loading_spinner = QLabel()
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_spinner.setStyleSheet(
            "font-size: 72pt; color: #2563EB; background: transparent;"
        )
        loading_layout.addWidget(self.loading_spinner)

        # Loading text
        loading_text = QLabel("Importing scans from folder...")
        loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_text.setStyleSheet(
            "font-size: 16pt; color: #666; background: transparent; margin-top: 20px;"
        )
        loading_layout.addWidget(loading_text)

        # Set the container as the preview content
        self.large_preview_label.setStyleSheet("background-color: #f0f0f0; border: 2px solid #ccc;")
        # Use a temporary layout to center the loading container
        temp_widget = QWidget()
        temp_layout = QVBoxLayout(temp_widget)
        temp_layout.addWidget(loading_container)
        temp_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Replace preview label content
        old_layout = self.large_preview_label.layout()
        if old_layout:
            QWidget().setLayout(old_layout)  # Delete old layout
        preview_layout = QVBoxLayout(self.large_preview_label)
        preview_layout.addWidget(loading_container)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Start loading animation
        self.loading_spinner_frames = ['◐', '◓', '◑', '◒']  # Rotating circle
        self.loading_spinner_index = 0
        self.loading_spinner_timer = QTimer(self)
        self.loading_spinner_timer.timeout.connect(self._update_loading_spinner)
        self.loading_spinner_timer.start(10000)  # 10000ms (10 seconds) per frame - almost static

        # Update status
        self.status_label.setText("Importing scans from folder...")

    def _update_loading_spinner(self):
        """Update the loading spinner animation"""
        if hasattr(self, 'loading_spinner'):
            self.loading_spinner.setText(self.loading_spinner_frames[self.loading_spinner_index])
            self.loading_spinner_index = (self.loading_spinner_index + 1) % len(self.loading_spinner_frames)

    def _setup_step1_ui(self):
        """Step 1: Document Stitching - page-by-page inclusion with spinner and buttons
        Phase 2: Three-column layout with left (250px), center (fluid, min 600px), right (350px)
        """
        self.current_step = WorkflowStep.STITCHING
        self.current_ollama_prompt = None  # Store current prompt for tooltip/clipboard
        self.page_states = {}  # Track included/excluded state for each page

        # Stop loading spinner if it's running
        if hasattr(self, 'loading_spinner_timer') and self.loading_spinner_timer.isActive():
            self.loading_spinner_timer.stop()

        # Clear loading UI from preview area
        old_layout = self.large_preview_label.layout()
        if old_layout:
            # Remove all widgets from the layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # Delete the layout itself
            QWidget().setLayout(old_layout)

        # Reset preview label to normal state
        self.large_preview_label.clear()
        self.large_preview_label.setStyleSheet("background-color: #f0f0f0; border: 2px solid #ccc;")

        # Update header
        self.step_title_label.setText("Document Stitching")
        self.step_indicator_label.setText("Step 1 of 5")
        self.header_back_button.setVisible(False)  # Hide back button in Step 1

        # Clear side panels
        self._clear_panel(self.left_panel_layout)
        self._clear_panel(self.right_panel_layout)

        # Phase 2: Configure three-column layout
        # LEFT PANEL: Fixed 250px width
        self.left_panel.setVisible(True)
        self.left_panel.setFixedWidth(250)
        self.left_panel.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
            }
        """)
        self.left_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.left_panel_layout.setSpacing(0)

        # LEFT PANEL: Phase 3 - Image Gallery Widget
        self.image_gallery = ImageGalleryWidget(analysis_db=self.analysis_db, parent=self.left_panel)
        self.image_gallery.image_selected.connect(self._on_gallery_image_selected)
        self.image_gallery.image_toggled.connect(self._on_gallery_image_toggled)
        self.image_gallery.setStyleSheet("background: transparent; border: none;")
        self.left_panel_layout.addWidget(self.image_gallery)

        # Populate image gallery with current files
        if hasattr(self, 'all_files') and self.all_files:
            self.image_gallery.set_images(self.all_files)
            # Set checked files based on current_group
            if hasattr(self, 'current_group') and self.current_group:
                self.image_gallery.set_checked_files(self.current_group)

        # CENTER PANEL: Already configured in _init_ui with minimum width 600px

        # RIGHT PANEL: Fixed 350px width
        self.right_panel.setVisible(True)
        self.right_panel.setFixedWidth(350)
        self.right_panel.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
            }
        """)
        self.right_panel_layout.setContentsMargins(12, 12, 12, 12)
        self.right_panel_layout.setSpacing(8)

        # RIGHT PANEL: Phase 4 - Metadata Display Widget
        self.metadata_display = MetadataDisplayWidget(analysis_db=self.analysis_db, parent=self.right_panel)
        self.metadata_display.re_analyze_requested.connect(self._on_metadata_reanalyze)
        self.metadata_display.thumbnail_clicked.connect(self._on_bundle_thumbnail_clicked)
        self.metadata_display.setStyleSheet("background: transparent; border: none;")
        self.right_panel_layout.addWidget(self.metadata_display)

        # Update metadata display if we have a current page
        if hasattr(self, 'current_page_path') and self.current_page_path:
            self.metadata_display.set_current_file(self.current_page_path)
        if hasattr(self, 'current_group') and self.current_group:
            self.metadata_display.set_bundle_files(self.current_group)

        # Actions section below metadata display
        actions_label = QLabel("Actions")
        actions_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #111827; background: transparent; border: none;")
        self.right_panel_layout.addWidget(actions_label)

        button_container = QWidget()
        button_container.setStyleSheet("background: transparent; border: none;")
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        # Cancel Request button (cancels current Ollama operation) - TOP POSITION
        self.cancel_request_button = QPushButton("Cancel\nRequest")
        self.cancel_request_button.setStyleSheet(
            "QPushButton { background-color: #F59E0B; color: white; "
            "font-size: 10pt; padding: 10px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #D97706; }"
        )
        self.cancel_request_button.setToolTip("Cancel current request (Esc)")
        self.cancel_request_button.clicked.connect(self._on_cancel_ollama_step1)
        self.cancel_request_button.setVisible(False)
        button_layout.addWidget(self.cancel_request_button)

        button_layout.addSpacing(10)

        # Approve button (ends stitching and moves to Step 2)
        self.exclude_button = QPushButton("Approve")
        self.exclude_button.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; "
            "font-size: 11pt; padding: 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
        )
        self.exclude_button.setToolTip("Approve bundle and continue to next step (Enter)")
        self.exclude_button.clicked.connect(self._on_finish_group)
        self.exclude_button.setVisible(False)
        button_layout.addWidget(self.exclude_button)

        button_layout.addSpacing(10)

        # Import Scans button (initially shown)
        self.start_scan_button = QPushButton("Import Scans")
        self.start_scan_button.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; "
            "font-size: 13pt; padding: 20px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
        )
        self.start_scan_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_scan_button.clicked.connect(self._scan_and_group)
        button_layout.addWidget(self.start_scan_button)

        button_layout.addSpacing(10)

        # Include button (hidden initially, dynamically shown/hidden)
        self.include_button = QPushButton("Include")
        self.include_button.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; "
            "font-size: 12pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #047857; }"
        )
        self.include_button.setToolTip("Include current page in bundle (Space)")
        self.include_button.clicked.connect(self._on_include_current_page)
        self.include_button.setVisible(False)
        button_layout.addWidget(self.include_button)

        button_layout.addSpacing(10)

        # Exclude button (remove current page from group and mark as excluded)
        self.exclude_page_button = QPushButton("Exclude")
        self.exclude_page_button.setStyleSheet(
            "QPushButton { background-color: #DC2626; color: white; "
            "font-size: 11pt; padding: 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #B91C1C; }"
        )
        self.exclude_page_button.setToolTip("Exclude current page from bundle (Delete)")
        self.exclude_page_button.clicked.connect(self._on_exclude_current_page)
        self.exclude_page_button.setVisible(False)
        button_layout.addWidget(self.exclude_page_button)

        button_layout.addSpacing(10)

        # Abort button (gray, exits entire workflow)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet(
            "QPushButton { background-color: #6B7280; color: white; "
            "font-size: 11pt; padding: 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #4B5563; }"
        )
        self.abort_button.clicked.connect(self._on_abort_stitching)
        self.abort_button.setVisible(False)
        button_layout.addWidget(self.abort_button)

        button_layout.addSpacing(20)

        # Phase 8: Rotation Controls
        rotation_label = QLabel("Rotate Page:")
        rotation_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #555;")
        rotation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        button_layout.addWidget(rotation_label)

        # Rotation button grid (2x2)
        rotation_grid_widget = QWidget()
        rotation_grid = QGridLayout(rotation_grid_widget)
        rotation_grid.setSpacing(5)
        rotation_grid.setContentsMargins(0, 5, 0, 5)

        rotation_button_style = """
            QPushButton {
                background-color: #6B7280;
                color: white;
                font-size: 18pt;
                padding: 10px;
                border-radius: 5px;
                min-width: 60px;
                min-height: 50px;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
            QPushButton:pressed {
                background-color: #374151;
            }
        """

        # 90° CCW (↺)
        rotate_ccw_button = QPushButton("↺")
        rotate_ccw_button.setStyleSheet(rotation_button_style)
        rotate_ccw_button.setToolTip("Rotate 90° Counter-Clockwise")
        rotate_ccw_button.clicked.connect(lambda: self._rotate_current_page(270))
        rotation_grid.addWidget(rotate_ccw_button, 0, 0)

        # 90° CW (↻)
        rotate_cw_button = QPushButton("↻")
        rotate_cw_button.setStyleSheet(rotation_button_style)
        rotate_cw_button.setToolTip("Rotate 90° Clockwise")
        rotate_cw_button.clicked.connect(lambda: self._rotate_current_page(90))
        rotation_grid.addWidget(rotate_cw_button, 0, 1)

        # 180° (⟲)
        rotate_180_button = QPushButton("180°")
        rotate_180_button.setStyleSheet(rotation_button_style)
        rotate_180_button.setToolTip("Rotate 180°")
        rotate_180_button.clicked.connect(lambda: self._rotate_current_page(180))
        rotation_grid.addWidget(rotate_180_button, 1, 0)

        # 270° / Reset
        rotate_270_button = QPushButton("270°")
        rotate_270_button.setStyleSheet(rotation_button_style)
        rotate_270_button.setToolTip("Rotate 270° (90° CCW)")
        rotate_270_button.clicked.connect(lambda: self._rotate_current_page(270))
        rotation_grid.addWidget(rotate_270_button, 1, 1)

        button_layout.addWidget(rotation_grid_widget)
        rotation_grid_widget.setVisible(False)  # Hide until page is loaded
        self.rotation_controls_widget = rotation_grid_widget

        button_layout.addStretch(1)
        self.right_panel_layout.addWidget(button_container)

        # Set placeholder in large preview
        self.large_preview_label.setText("Click 'Import Scans' to begin\ndocument stitching")
        self.large_preview_label.setStyleSheet(
            "background-color: #f9f9f9; border: 2px dashed #ccc; "
            "font-size: 14pt; color: #999;"
        )

    def _setup_step2_ui(self):
        """Step 2: Document Analysis - metadata extraction with editable fields"""
        self.current_step = WorkflowStep.ANALYSIS

        # Remove excluded pages from thumbnail strip
        self._remove_excluded_thumbnails()

        # Update header
        self.step_title_label.setText("Document Analysis")
        self.step_indicator_label.setText("Step 2 of 5")
        self.header_back_button.setVisible(True)  # Show back button in Step 2

        # Show side panels (may have been hidden by loading UI)
        self.left_panel.setVisible(True)
        self.right_panel.setVisible(True)

        # Clear side panels
        self._clear_panel(self.left_panel_layout)
        self._clear_panel(self.right_panel_layout)

        # LEFT PANEL: Metadata fields
        self.left_panel.setFixedWidth(250)

        fields_label = QLabel("Document Metadata:")
        fields_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        self.left_panel_layout.addWidget(fields_label)

        # Company field (combo box with history)
        self.left_panel_layout.addWidget(QLabel("Company:"))
        self.company_edit = QComboBox()
        self.company_edit.setEditable(True)
        self.company_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.company_edit.lineEdit().setPlaceholderText("Company name...")
        # Populate with history
        companies = self.metadata_db.get_unique_companies()
        self.company_edit.addItems(companies)
        self.company_edit.setCurrentText("")  # Start empty
        self.left_panel_layout.addWidget(self.company_edit)

        self.left_panel_layout.addSpacing(10)

        # Title field (combo box with history)
        self.left_panel_layout.addWidget(QLabel("Title:"))
        self.title_edit = QComboBox()
        self.title_edit.setEditable(True)
        self.title_edit.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.title_edit.lineEdit().setPlaceholderText("Document title...")
        # Populate with history
        titles = self.metadata_db.get_unique_titles()
        self.title_edit.addItems(titles)
        self.title_edit.setCurrentText("")  # Start empty
        self.left_panel_layout.addWidget(self.title_edit)

        self.left_panel_layout.addSpacing(10)

        # Date field
        self.left_panel_layout.addWidget(QLabel("Date:"))
        self.date_edit = QLineEdit()
        self.date_edit.setPlaceholderText("YYYY-MM-DD...")
        self.left_panel_layout.addWidget(self.date_edit)

        self.left_panel_layout.addStretch(1)

        # RIGHT PANEL: Action buttons
        self.right_panel.setFixedWidth(200)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.addStretch(1)

        # Approve button (enabled when Ollama responds)
        self.continue_button = QPushButton("Approve")
        self.continue_button.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; "
            "font-size: 12pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        self.continue_button.clicked.connect(self._on_continue_to_step3)
        self.continue_button.setEnabled(False)
        button_layout.addWidget(self.continue_button)

        button_layout.addSpacing(10)

        # Cancel Request button (stops Ollama, allows manual completion)
        self.cancel_ollama_button = QPushButton("Cancel\nRequest")
        self.cancel_ollama_button.setStyleSheet(
            "QPushButton { background-color: #6B7280; color: white; "
            "font-size: 10pt; padding: 12px; border-radius: 5px; text-align: center; }"
            "QPushButton:hover { background-color: #4B5563; }"
        )
        self.cancel_ollama_button.clicked.connect(self._on_cancel_ollama)
        self.cancel_ollama_button.setEnabled(False)
        button_layout.addWidget(self.cancel_ollama_button)

        button_layout.addSpacing(10)

        # Close Window button (return to main window)
        self.abort_button = QPushButton("Close\nWindow")
        self.abort_button.setStyleSheet(
            "QPushButton { background-color: #DC2626; color: white; "
            "font-size: 10pt; padding: 12px; border-radius: 5px; text-align: center; }"
            "QPushButton:hover { background-color: #B91C1C; }"
        )
        self.abort_button.clicked.connect(self._on_abort)
        button_layout.addWidget(self.abort_button)

        button_layout.addStretch(1)
        self.right_panel_layout.addWidget(button_container)

        # Make thumbnails clickable to change preview
        self._make_thumbnails_clickable()

        # Display the first included page in the preview
        if self.current_group:
            self._display_page_in_large_preview(self.current_group[0])

        # Start automatic metadata extraction
        self._start_metadata_extraction()

    # ===== STEP 3: ORDER PAGES (Phase 4) =====

    def _setup_step3_ui(self):
        """Step 3: Order Pages - automatic reordering with manual override"""
        self.current_step = WorkflowStep.ORDERING

        # Update header
        self.step_title_label.setText("Order Pages")
        self.step_indicator_label.setText("Step 3 of 5")
        self.header_back_button.setVisible(True)  # Show back button in Step 3

        # Show side panels
        self.left_panel.setVisible(True)
        self.right_panel.setVisible(True)

        # Clear panels
        self._clear_panel(self.left_panel_layout)
        self._clear_panel(self.right_panel_layout)

        # === LEFT PANEL: Page Order List (250px) ===
        self.left_panel.setFixedWidth(250)

        order_title = QLabel("Page Order:")
        order_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        self.left_panel_layout.addWidget(order_title)

        # List widget showing page order (drag-and-drop enabled)
        self.page_order_list = QListWidget()
        self.page_order_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.page_order_list.itemSelectionChanged.connect(self._on_order_list_selection_changed)
        self.page_order_list.model().rowsMoved.connect(self._on_order_list_reordered)
        self.left_panel_layout.addWidget(self.page_order_list)

        # Reset button
        reset_button = QPushButton("Reset to Original Order")
        reset_button.setStyleSheet(
            "QPushButton { background-color: #6B7280; color: white; "
            "font-size: 9pt; padding: 8px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #4B5563; }"
        )
        reset_button.clicked.connect(self._reset_page_order)
        self.left_panel_layout.addWidget(reset_button)

        # === RIGHT PANEL: Reordering Controls (220px) ===
        self.right_panel.setFixedWidth(220)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.addStretch(1)

        # Manual reorder section
        manual_label = QLabel("Manual Reorder:")
        manual_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        button_layout.addWidget(manual_label)

        # Up/Down buttons
        move_up_button = QPushButton("↑ Move Up")
        move_up_button.clicked.connect(lambda: self._move_page(-1))
        button_layout.addWidget(move_up_button)

        move_down_button = QPushButton("↓ Move Down")
        move_down_button.clicked.connect(lambda: self._move_page(1))
        button_layout.addWidget(move_down_button)

        button_layout.addSpacing(10)

        # Approve button
        self.approve_order_button = QPushButton("✓ Approve Order")
        self.approve_order_button.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; "
            "font-size: 12pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #047857; }"
        )
        self.approve_order_button.setToolTip("Approve page order and continue (Enter)")
        self.approve_order_button.clicked.connect(self._on_approve_page_order)
        button_layout.addWidget(self.approve_order_button)

        button_layout.addStretch(1)
        self.right_panel_layout.addWidget(button_container)

        # Initialize and auto-reorder
        self._initialize_page_order()
        self._auto_reorder_pages()

    def _initialize_page_order(self):
        """Initialize page order list from current_group and metadata"""
        # Save original order
        self.original_page_order = self.current_group.copy()

        # Populate list widget
        self.page_order_list.clear()
        for i, page_path in enumerate(self.current_group):
            metadata = next((m for m in self.page_metadata_list if m['image_path'] == page_path), None)
            page_num = metadata.get('detected_page_number') if metadata else None
            confidence = metadata.get('confidence', 'low') if metadata else 'low'

            filename = os.path.basename(page_path)[:20]
            if page_num:
                confidence_icon = {'high': '✓', 'medium': '~', 'low': '?'}.get(confidence, '?')
                item_text = f"{i+1}. Page {page_num} {confidence_icon} - {filename}"
            else:
                item_text = f"{i+1}. [No page #] - {filename}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, page_path)
            self.page_order_list.addItem(item)

        if self.current_group:
            self._display_page_in_large_preview(self.current_group[0], show_indicator=False)

    def _auto_reorder_pages(self):
        """Automatically reorder pages based on detected page numbers"""
        pages_with_numbers = [m for m in self.page_metadata_list if m.get('detected_page_number') is not None]

        if not pages_with_numbers:
            self._offer_content_based_ordering()
            return

        # Check for duplicates
        page_numbers = [m['detected_page_number'] for m in pages_with_numbers]
        if len(page_numbers) != len(set(page_numbers)):
            duplicates = [num for num in set(page_numbers) if page_numbers.count(num) > 1]
            show_warning(
                self, "Duplicate Page Numbers",
                f"Duplicate page numbers detected: {duplicates}\n\nPlease review and reorder manually."
            )

        # Sort pages by detected page number
        try:
            sortable = []
            for m in self.page_metadata_list:
                page_num = m.get('detected_page_number')
                if page_num is not None:
                    sortable.append((page_num, m['original_index'], m))
                else:
                    sortable.append((float('inf'), m['original_index'], m))

            sortable.sort(key=lambda x: (x[0], x[1]))
            self.current_group = [m['image_path'] for _, _, m in sortable]

            self._refresh_page_order_list()
            self.status_label.setText(
                f"✓ Pages auto-reordered. {len(pages_with_numbers)}/{len(self.page_metadata_list)} pages had numbers."
            )
        except Exception as e:
            show_critical(self, "Reordering Error", f"Failed to auto-reorder pages: {e}")

    def _refresh_page_order_list(self):
        """Refresh the page order list widget from current_group"""
        self.page_order_list.clear()
        for i, page_path in enumerate(self.current_group):
            metadata = next((m for m in self.page_metadata_list if m['image_path'] == page_path), None)
            page_num = metadata.get('detected_page_number') if metadata else None
            confidence = metadata.get('confidence', 'low') if metadata else 'low'

            filename = os.path.basename(page_path)[:20]
            if page_num:
                confidence_icon = {'high': '✓', 'medium': '~', 'low': '?'}.get(confidence, '?')
                item_text = f"{i+1}. Page {page_num} {confidence_icon} - {filename}"
            else:
                item_text = f"{i+1}. [No page #] - {filename}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, page_path)
            self.page_order_list.addItem(item)

    def _move_page(self, direction):
        """Move selected page up (-1) or down (+1)"""
        current_row = self.page_order_list.currentRow()
        if current_row < 0:
            show_information(self, "No Selection", "Please select a page to move.")
            return

        new_row = current_row + direction
        if new_row < 0 or new_row >= self.page_order_list.count():
            return

        # Move in list widget
        item = self.page_order_list.takeItem(current_row)
        self.page_order_list.insertItem(new_row, item)
        self.page_order_list.setCurrentRow(new_row)

        # Update current_group
        self.current_group.insert(new_row, self.current_group.pop(current_row))
        self._refresh_page_order_list()
        self.page_order_list.setCurrentRow(new_row)

    def _on_order_list_reordered(self, parent, start, end, destination, row):
        """Handle drag-and-drop reordering"""
        new_order = []
        for i in range(self.page_order_list.count()):
            item = self.page_order_list.item(i)
            page_path = item.data(Qt.ItemDataRole.UserRole)
            new_order.append(page_path)

        self.current_group = new_order
        self._refresh_page_order_list()

    def _on_order_list_selection_changed(self):
        """Update preview when list selection changes"""
        current_item = self.page_order_list.currentItem()
        if current_item:
            page_path = current_item.data(Qt.ItemDataRole.UserRole)
            self._display_page_in_large_preview(page_path, show_indicator=False)

    def _reset_page_order(self):
        """Reset to original stitching order"""
        reply = show_question(
            self, "Reset Order",
            "Reset to original page order from stitching step?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.current_group = self.original_page_order.copy()
            self._refresh_page_order_list()
            self.status_label.setText("Page order reset to original.")

    def _on_approve_page_order(self):
        """User approves page order - move to Step 4"""
        if not self.current_group:
            show_warning(self, "No Pages", "No pages to finalize.")
            return

        self.status_label.setText(f"Page order approved. {len(self.current_group)} pages ready for PDF.")
        self._setup_step4_ui()

    def _on_back_to_step2(self):
        """Go back to Step 2 (Analysis)"""
        # Cancel any running Ollama request
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self._stop_spinner()

        self._setup_step2_ui()

    def _on_back_to_step1(self):
        """Go back to Step 1 (Stitching) from Step 2"""
        # Cancel any running Ollama request
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self._stop_spinner()

        # Confirm with user since this might lose metadata edits
        reply = show_question(
            self, "Return to Stitching?",
            "Going back will discard any metadata edits. Continue?"
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Clear metadata
            self.extracted_metadata = {}

            # Reset to Step 1
            self._setup_step1_ui()

            # Restore current group state (show all included pages)
            for page_path in self.current_group:
                self._update_thumbnail_state(page_path, 'included')

            # Display first page
            if self.current_group:
                self._display_page_in_large_preview(self.current_group[0])

            # Update buttons for review state
            self.start_scan_button.setVisible(False)
            self.exclude_button.setVisible(True)
            self.exclude_button.setText("Finish Group")

            self.status_label.setText(
                f"Returned to stitching. Group has {len(self.current_group)} page(s). "
                f"Click 'Finish Group' to proceed or modify pages."
            )

    def _on_back_to_step3(self):
        """Go back to Step 3 (Order Pages) from Step 4"""
        # Cancel any running Ollama request
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self._stop_spinner()

        # Delete the preview PDF if it exists
        if hasattr(self, 'created_pdf_path') and os.path.exists(self.created_pdf_path):
            try:
                os.remove(self.created_pdf_path)
                print(f"Deleted preview PDF: {self.created_pdf_path}")
            except Exception as e:
                print(f"Warning: Could not delete preview PDF: {e}")

        # Return to Step 3
        self._setup_step3_ui()

    def _offer_content_based_ordering(self):
        """Offer to use Ollama for content-based ordering (Phase 5)"""
        reply = show_question(
            self, "Content-Based Ordering",
            "No page numbers detected. Would you like Ollama to analyze content flow and suggest page order?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_content_based_ordering()

    def _start_content_based_ordering(self):
        """Start Ollama worker for content-based ordering"""
        selected_model = self.config_manager.get_setting('Ollama', 'model')

        self._start_spinner()
        self.status_label.setText(f"Analyzing content flow with {selected_model}...")

        self.worker_thread = OllamaWorker(
            self.ollama_service.infer_page_order_from_content,
            selected_model,
            self.current_group
        )
        self.worker_thread.finished.connect(self._on_content_ordering_result)
        self.worker_thread.progress.connect(self._on_worker_progress)
        self.worker_thread.start()

    def _on_content_ordering_result(self, result):
        """Handle content-based ordering result"""
        self._stop_spinner()

        # Safety check: ensure we're still in Step 3 (Ordering)
        if not hasattr(self, 'current_step') or self.current_step != WorkflowStep.ORDERING:
            print("⚠ Content ordering completed but UI has moved to a different step")
            return

        if isinstance(result, Exception):
            show_warning(
                self, "Ordering Failed",
                f"Content-based ordering failed: {result}\n\nPlease reorder manually."
            )
            return

        ordered_indices = result.get('ordered_indices', [])
        confidence = result.get('confidence', 'low')

        try:
            original_group = self.current_group.copy()
            self.current_group = [original_group[i] for i in ordered_indices]

            self._refresh_page_order_list()

            # Safety check: ensure status_label still exists
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    self.status_label.setText(
                        f"✓ Pages reordered by content analysis (confidence: {confidence}). Review and approve."
                    )
                except RuntimeError:
                    print("⚠ Status label no longer exists")
        except Exception as e:
            show_critical(
                self, "Ordering Error",
                f"Failed to apply content-based ordering: {e}"
            )

    # ===== STEP 4: DOCUMENT FINALIZATION =====

    def _setup_step4_ui(self):
        """Step 4: Document Finalization - PDF review and confirmation"""
        self.current_step = WorkflowStep.FINALIZATION

        # Update header
        self.step_title_label.setText("Document Finalization")
        self.step_indicator_label.setText("Step 4 of 5")
        self.header_back_button.setVisible(True)  # Show back button in Step 4

        # Show side panels (may have been hidden by loading UI)
        self.left_panel.setVisible(True)
        self.right_panel.setVisible(True)

        # Clear side panels
        self._clear_panel(self.left_panel_layout)
        self._clear_panel(self.right_panel_layout)

        # LEFT PANEL: PDF info
        self.left_panel.setFixedWidth(200)

        info_label = QLabel("PDF Information:")
        info_label.setStyleSheet("font-weight: bold; font-size: 11pt;")
        self.left_panel_layout.addWidget(info_label)

        self.left_panel_layout.addSpacing(10)

        # PDF details
        self.pdf_pages_label = QLabel(f"Pages: {len(self.current_group)}")
        self.pdf_pages_label.setStyleSheet("font-size: 10pt;")
        self.left_panel_layout.addWidget(self.pdf_pages_label)

        self.pdf_searchable_label = QLabel("Type: Image PDF")
        self.pdf_searchable_label.setStyleSheet("font-size: 10pt;")
        self.left_panel_layout.addWidget(self.pdf_searchable_label)

        self.left_panel_layout.addSpacing(10)

        # File info - show metadata components
        company = self.extracted_metadata.get('company', 'Unknown')
        title = self.extracted_metadata.get('title', 'Document')
        date = self.extracted_metadata.get('date', 'NoDate')

        metadata_label = QLabel(f"Company: {company}\nTitle: {title}\nDate: {date}")
        metadata_label.setWordWrap(True)
        metadata_label.setStyleSheet("font-size: 9pt; color: #666;")
        self.left_panel_layout.addWidget(metadata_label)

        self.left_panel_layout.addStretch(1)

        # RIGHT PANEL: Confirmation buttons
        self.right_panel.setFixedWidth(220)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.addStretch(1)

        # Accept & Delete Sources
        self.accept_delete_button = QPushButton("✓ Accept & Delete Sources")
        self.accept_delete_button.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; "
            "font-size: 11pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #047857; }"
        )
        self.accept_delete_button.clicked.connect(lambda: self._finalize_document(delete_sources=True))
        button_layout.addWidget(self.accept_delete_button)

        button_layout.addSpacing(10)

        # Accept & Keep Sources
        self.accept_keep_button = QPushButton("✓ Accept & Keep Sources")
        self.accept_keep_button.setStyleSheet(
            "QPushButton { background-color: #2563EB; color: white; "
            "font-size: 11pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #1D4ED8; }"
        )
        self.accept_keep_button.clicked.connect(lambda: self._finalize_document(delete_sources=False))
        button_layout.addWidget(self.accept_keep_button)

        button_layout.addSpacing(10)

        # Reject & Delete PDF
        self.reject_button = QPushButton("✗ Reject & Delete PDF")
        self.reject_button.setStyleSheet(
            "QPushButton { background-color: #DC2626; color: white; "
            "font-size: 11pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #B91C1C; }"
        )
        self.reject_button.clicked.connect(self._on_reject_pdf)
        button_layout.addWidget(self.reject_button)

        button_layout.addStretch(1)
        self.right_panel_layout.addWidget(button_container)

        # Create the PDF and display it
        self._create_pdf_for_preview()

    def _update_spinner(self):
        """Update the spinner animation frame"""
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
        self.spinner_label.setText(self.spinner_frames[self.spinner_index])

    def _start_spinner(self):
        """Start the spinner animation"""
        self.spinner_label.setVisible(True)
        self.spinner_label.setStyleSheet("font-size: 16pt; color: #2563EB;")
        self.spinner_timer.start(100)  # Update every 100ms
        self._show_progress(indeterminate=True)  # Show indeterminate progress
        self._start_elapsed_timer()  # Start tracking time

    def _stop_spinner(self):
        """Stop the spinner animation"""
        self.spinner_timer.stop()
        self.spinner_label.setVisible(False)
        self._hide_progress()
        self._stop_elapsed_timer()

    def _set_stage(self, stage_text):
        """Set the current processing stage"""
        if stage_text:
            self.stage_label.setText(stage_text)
            self.stage_label.setVisible(True)
        else:
            self.stage_label.setVisible(False)

    def _show_progress(self, indeterminate=False):
        """Show the progress bar"""
        self.progress_bar.setVisible(True)
        if indeterminate:
            self.progress_bar.setMaximum(0)  # Indeterminate mode (pulse)
            self.progress_bar.setFormat("Processing...")
        else:
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("%p%")

    def _hide_progress(self):
        """Hide the progress bar"""
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

    def _update_progress(self, value, text=None):
        """Update progress bar value and optional text"""
        if self.progress_bar.maximum() > 0:  # Only update if not indeterminate
            self.progress_bar.setValue(value)
        if text:
            self.progress_bar.setFormat(text)

    def _start_elapsed_timer(self):
        """Start tracking elapsed time"""
        self.elapsed_seconds = 0
        self.elapsed_timer.start(1000)  # Update every second

    def _stop_elapsed_timer(self):
        """Stop tracking elapsed time"""
        self.elapsed_timer.stop()
        self.elapsed_seconds = 0

    def _update_elapsed_time(self):
        """Update elapsed time counter and refresh status message"""
        self.elapsed_seconds += 1
        # Update status message with elapsed time if we're processing
        if hasattr(self, '_current_status_base'):
            self._set_status_with_time(self._current_status_base)

    def _set_status_with_time(self, base_message):
        """Set status message with elapsed time"""
        self._current_status_base = base_message
        if self.elapsed_seconds > 0:
            self.status_label.setText(f"{base_message} ({self.elapsed_seconds}s elapsed)")
        else:
            self.status_label.setText(base_message)

    def _animate_step1_spinner(self):
        """Animate the Step 1 spinner by rotating it"""
        self.step1_spinner_rotation = (self.step1_spinner_rotation + 45) % 360
        # Cycle through spinner characters for animation effect
        spinner_chars = ['◐', '◓', '◑', '◒']
        char_index = (self.step1_spinner_rotation // 45) % len(spinner_chars)
        self.step1_spinner.setText(spinner_chars[char_index])

    def _on_spinner_clicked(self, event):
        """Copy the current Ollama prompt to clipboard when spinner is clicked"""
        if self.current_ollama_prompt:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_ollama_prompt)

            # Show brief confirmation
            original_text = self.status_label.text()
            self.status_label.setText("✓ Prompt copied to clipboard!")
            QTimer.singleShot(2000, lambda: self.status_label.setText(original_text))

    def _update_connection_status(self):
        """Update the Ollama connection status indicator"""
        try:
            models = self.ollama_service.list_models()
            if models:
                # Green: Connected with models
                self.connection_status_label.setStyleSheet("font-size: 16pt; color: #28a745;")
                self.connection_status_label.setToolTip(f"Ollama connected - {len(models)} model(s) available")
                self.connection_text_label.setText("Ollama: Connected")
                self.connection_text_label.setStyleSheet("font-size: 9pt; color: #28a745;")
            else:
                # Yellow: Connected but no models
                self.connection_status_label.setStyleSheet("font-size: 16pt; color: #ffc107;")
                self.connection_status_label.setToolTip("Ollama connected but no models installed")
                self.connection_text_label.setText("Ollama: No models")
                self.connection_text_label.setStyleSheet("font-size: 9pt; color: #ffc107;")
        except Exception:
            # Red: Connection failed
            self.connection_status_label.setStyleSheet("font-size: 16pt; color: #dc3545;")
            self.connection_status_label.setToolTip("Cannot connect to Ollama - check if service is running")
            self.connection_text_label.setText("Ollama: Disconnected")
            self.connection_text_label.setStyleSheet("font-size: 9pt; color: #dc3545;")

    def _on_worker_progress(self, message):
        """Handle progress updates from worker thread"""
        # Update status with progress message
        self._set_status_with_time(message)

    def _on_status_clicked(self, event):
        """Handle clicking on status label to show raw Ollama request and response"""
        if self.last_ollama_response is not None or self.last_ollama_request is not None:
            # Create a custom dialog to show both request and response
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Ollama Debug - {self.last_ollama_response_type}")
            dialog.setMinimumWidth(700)
            dialog.setMinimumHeight(600)

            layout = QVBoxLayout(dialog)

            # Model info
            model_name = getattr(self, 'current_extraction_model', 'Unknown')
            info_label = QLabel(f"<b>Model:</b> {model_name} | <b>Type:</b> {self.last_ollama_response_type}")
            layout.addWidget(info_label)

            # Request section
            if self.last_ollama_request:
                request_label = QLabel("<b>Request (Prompt):</b>")
                layout.addWidget(request_label)

                request_text = QPlainTextEdit()
                request_text.setPlainText(str(self.last_ollama_request))
                request_text.setReadOnly(True)
                request_text.setMaximumHeight(250)
                layout.addWidget(request_text)

            # Response section
            if self.last_ollama_response:
                response_label = QLabel("<b>Response:</b>")
                layout.addWidget(response_label)

                # Format the response nicely
                if isinstance(self.last_ollama_response, dict):
                    import json
                    response_text_str = json.dumps(self.last_ollama_response, indent=2)
                else:
                    response_text_str = str(self.last_ollama_response)

                response_text = QPlainTextEdit()
                response_text.setPlainText(response_text_str)
                response_text.setReadOnly(True)
                response_text.setMaximumHeight(250)
                layout.addWidget(response_text)

            # Close button
            close_button = QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            layout.addWidget(close_button)

            dialog.exec()
        else:
            show_information(
                self,
                "No Data",
                "No Ollama request/response available yet.\n\nData will be stored after metadata extraction operations."
            )

    # DEPRECATED METHODS FROM OLD WORKFLOW - REMOVED
    # The 3-step workflow has replaced these methods with:
    # - Step 1 handlers (_load_next_page_for_stitching, _on_include_page, _on_exclude_page)
    # - Step 2 handlers (_start_metadata_extraction, _on_metadata_extracted, _on_continue_to_step3)
    # - Step 3 handlers (_setup_step3_ui, _initialize_page_order, _auto_reorder_pages, etc.)
    # - Step 4 handlers (_create_pdf_for_preview, _finalize_document)

    def _check_ollama_connection(self):
        """Verify Ollama is accessible before processing"""
        try:
            models = self.ollama_service.list_models()
            if not models:
                show_warning(
                    self,
                    "No Models Available",
                    "Ollama is running but no models are installed.\n\n"
                    "To fix:\n"
                    "• Pull a model using the 'Pull Model' button above\n"
                    "• Or run: ollama pull <model-name>"
                )
                return False
            return True
        except ConnectionError as e:
            error_msg = str(e)
            base_url = self.ollama_service.base_url

            # Provide specific troubleshooting based on error
            if "Failed to connect" in error_msg or "Connection refused" in error_msg:
                show_critical(
                    self,
                    "Ollama Connection Failed",
                    f"Cannot connect to Ollama server at {base_url}\n\n"
                    f"To fix:\n"
                    f"• Start Ollama: Run 'ollama serve' in terminal\n"
                    f"• Check if Ollama is installed\n"
                    f"• Verify firewall settings\n"
                    f"• Check if another process is using port 11434"
                )
            else:
                show_critical(
                    self,
                    "Ollama Error",
                    f"Error connecting to Ollama:\n\n{error_msg}\n\n"
                    f"Server: {base_url}\n\n"
                    f"Please ensure:\n"
                    f"1. Ollama is installed\n"
                    f"2. Ollama service is running\n"
                    f"3. Server URL is correct in Settings"
                )
            return False
        except Exception as e:
            show_critical(
                self,
                "Unexpected Error",
                f"An unexpected error occurred while connecting to Ollama:\n\n{e}\n\n"
                f"Please check your Ollama installation and try again."
            )
            return False

    # Model management moved to SettingsWindow only

    # _clear_preview_area - DEPRECATED (replaced by _clear_thumbnails in 3-step workflow)

    def _scan_and_group(self):
        """Step 1: Scan files and begin incremental document stitching"""
        self.status_label.setText("Scanning for PNG files...")

        try:
            # Get all image files (no pre-grouping)
            self.all_files = self.file_processor._get_image_files()

            if not self.all_files:
                show_information(self, "Scan Complete", "No PNG files found in scan folder.")
                self.status_label.setText("No files found.")
                # Return to loading UI (could add a reset/retry button here)
                return

            # Check model selection
            selected_model = self.config_manager.get_setting('Ollama', 'model')
            if not selected_model:
                show_warning(self, "No Model Selected", "Please select a model from the dropdown above.")
                self.status_label.setText("No model selected.")
                # Return to loading UI
                return

            # Pre-flight check: Verify Ollama connection
            if not self._check_ollama_connection():
                self.status_label.setText("Ollama connection failed. Please check the error message.")
                # Return to loading UI
                return

            # Reset state
            self.current_file_index = 0
            self.current_group = []
            self.completed_groups = []

            # Phase 7: Setup Step 1 UI first (needed for layout structure)
            self._setup_step1_ui()

            # Check if files need analysis before bundling
            unanalyzed_files = []
            for file_path in self.all_files:
                if not self.analysis_db.get_analysis(file_path):
                    unanalyzed_files.append(file_path)

            if unanalyzed_files:
                # Trigger analysis for unanalyzed files
                self.status_label.setText(
                    f"Found {len(self.all_files)} file(s). Analyzing {len(unanalyzed_files)} unanalyzed file(s)..."
                )
                print(f"[ConvertImages] Analyzing {len(unanalyzed_files)} unanalyzed files before bundling")

                # Start analysis service
                self.analysis_worker = SpecificFilesAnalysisWorker(self.analysis_service, unanalyzed_files)
                self.analysis_worker.progress.connect(self._on_analysis_progress)
                self.analysis_worker.finished.connect(self._on_analysis_complete_proceed_to_bundling)
                self.analysis_worker.start()
            else:
                # All files already analyzed, proceed to bundling
                self.status_label.setText(f"Found {len(self.all_files)} file(s). Generating bundle suggestions...")
                self._load_and_show_bundle_suggestions()

        except Exception as e:
            show_critical(self, "Error Scanning", f"An error occurred: {e}")
            self.status_label.setText(f"Error: {e}")
            # Stay in loading UI on error (buttons don't exist yet)

    # ===== STEP 1: DOCUMENT STITCHING HANDLERS =====

    def _load_next_page_for_stitching(self):
        """Load next page and display it for user review/Ollama validation"""
        # Find next unprocessed file (skip files already in thumbnail strip)
        while self.current_file_index < len(self.all_files):
            next_file = self.all_files[self.current_file_index]

            # Check if this file has already been processed (in page_states)
            if next_file in self.page_states:
                print(f"⚠ Skipping already processed file: {os.path.basename(next_file)}")
                self.current_file_index += 1
                continue

            # Found an unprocessed file
            break

        # Check if we're done with all files
        if self.current_file_index >= len(self.all_files):
            # No more files - finalize current group if any
            if self.current_group:
                self._on_exclude_page()  # End stitching
            else:
                show_information(self, "No Files", "No files to process.")
                self._reset_to_start()
            return

        # Get next unprocessed file
        next_file = self.all_files[self.current_file_index]
        self.current_page_path = next_file

        # Display in large preview
        self._display_page_in_large_preview(next_file)

        # Phase 8: Show rotation controls when page is loaded
        if hasattr(self, 'rotation_controls_widget'):
            self.rotation_controls_widget.setVisible(True)

        # If this is the first page, automatically add it
        if not self.current_group:
            self.current_group.append(next_file)
            self.current_file_index += 1

            # Add to thumbnail strip (first page is auto-included)
            self._add_thumbnail(next_file, 'included')

            # Phase 4: Update metadata display
            if hasattr(self, 'metadata_display'):
                self.metadata_display.set_current_file(next_file)
                self.metadata_display.set_bundle_files(self.current_group)

            files_remaining = len(self.all_files) - self.current_file_index
            self.status_label.setText(f"Started new group. Page 1 added. ({files_remaining} files remaining)")

            # Load next page
            if self.current_file_index < len(self.all_files):
                self._load_next_page_for_stitching()
            return

        # For subsequent pages, ask Ollama if they belong
        selected_model = self.config_manager.get_setting('Ollama', 'model')
        files_remaining = len(self.all_files) - self.current_file_index
        group_size = len(self.current_group)

        # Show processing buttons, hide start button
        self.start_scan_button.setVisible(False)
        self.include_button.setVisible(False)
        self.exclude_button.setVisible(False)
        self.exclude_page_button.setVisible(False)
        self.cancel_request_button.setVisible(True)
        self.abort_button.setVisible(True)

        # Stop any running auto-approval timer from previous page
        self._stop_auto_approval()

        self._start_spinner()
        self._set_status_with_time(f"Analyzing page {group_size + 1} with {selected_model}... ({files_remaining} files remaining)")

        # Add thumbnail with pending state while analyzing
        self._add_thumbnail(next_file, 'pending')

        # Validate with Ollama
        files_to_validate = self.current_group + [next_file]
        pages_prompt_default = """You are an expert document analyst. Examine the provided images. Determine if all pages belong to the *same continuous physical document*. Respond ONLY with 'YES' if all pages are from the same document, or 'NO' if they are not. Do not add any other text or explanation."""
        pages_prompt = self.config_manager.get_setting("Prompts", "document_pages", pages_prompt_default)

        # Store prompt for tooltip/clipboard
        self.current_ollama_prompt = pages_prompt
        if hasattr(self, 'step1_spinner'):
            prompt_preview = pages_prompt[:200] if pages_prompt else "No prompt configured"
            self.step1_spinner.setToolTip(f"Click to copy prompt to clipboard\n\nPrompt:\n{prompt_preview}...")

        # Store request for debugging (with file paths)
        file_list = "\n".join(f"  {i}. {path}" for i, path in enumerate(files_to_validate, 1))
        self.last_ollama_request = f"""{pages_prompt}

Model: {selected_model}
Images: {len(files_to_validate)} page(s)

Files being sent to Ollama:
{file_list}"""
        self.last_ollama_response_type = "Page Validation"

        # Check metadata cache first (avoid unnecessary Ollama calls)
        cached_metadata = self.metadata_db.get_metadata(next_file)

        if cached_metadata and cached_metadata.get('belongs_to_same_doc') is not None:
            # Use cached metadata instead of calling Ollama
            print(f"✓ Using cached metadata for {os.path.basename(next_file)}")

            # Convert cached data to expected format
            result = {
                'belongs': cached_metadata.get('belongs_to_same_doc', False),
                'page_number': cached_metadata.get('page_number'),
                'total_pages': cached_metadata.get('total_pages'),
                'page_position': cached_metadata.get('page_position'),
                'confidence': cached_metadata.get('confidence', 'low'),
                'company': cached_metadata.get('company'),
                'document_type': cached_metadata.get('document_type'),
                'document_date': cached_metadata.get('document_date'),
                'additional': {}
            }

            # Process cached result immediately
            self._on_page_validation_result(result, next_file)
            return

        # No cache or stale cache - call Ollama
        print(f"⟳ Fetching fresh metadata for {os.path.basename(next_file)}")

        # Start spinner animation
        if hasattr(self, 'step1_spinner_timer'):
            self.step1_spinner_timer.start(100)  # 100ms interval

        # Phase 2: Use new method that detects comprehensive metadata
        import time
        start_time = time.time()

        self.worker_thread = OllamaWorker(self.ollama_service.validate_grouping_with_page_number, selected_model, files_to_validate, pages_prompt)
        self.worker_thread.finished.connect(lambda result: self._on_page_validation_result(result, next_file, start_time=start_time))
        self.worker_thread.progress.connect(self._on_worker_progress)
        self.worker_thread.start()

    def _on_page_validation_result(self, result, evaluated_file, start_time=None):
        """Handle Ollama's response - now includes comprehensive metadata (Phase 3 + Caching)"""
        self._stop_spinner()

        # Stop spinner animation
        if hasattr(self, 'step1_spinner_timer'):
            self.step1_spinner_timer.stop()

        # Safety check: ensure we're still in Step 1 (Stitching)
        if not hasattr(self, 'current_step') or self.current_step != WorkflowStep.STITCHING:
            print("⚠ Page validation completed but UI has moved to a different step")
            return

        # Hide cancel request button, keep abort visible
        if hasattr(self, 'cancel_request_button') and self.cancel_request_button:
            try:
                self.cancel_request_button.setVisible(False)
            except RuntimeError:
                print("⚠ Step 1 UI no longer exists")
                return

        # Extract validation result and comprehensive metadata
        if isinstance(result, Exception):
            self.last_ollama_response = f"ERROR: {str(result)}"
            belongs = False
            page_number = None
            total_pages = None
            page_position = None
            confidence = 'low'
            company = None
            document_type = None
            document_date = None
            additional = {}
        else:
            belongs = result.get('belongs', False) if isinstance(result, dict) else result
            doc_page_count = result.get('doc_page_count', 0) if isinstance(result, dict) else 0
            do_not_belong = result.get('do_not_belong', []) if isinstance(result, dict) else []
            page_number = result.get('page_number') if isinstance(result, dict) else None
            total_pages = result.get('total_pages') if isinstance(result, dict) else None
            page_position = result.get('page_position') if isinstance(result, dict) else None
            confidence = result.get('confidence', 'low') if isinstance(result, dict) else 'low'
            company = result.get('company') if isinstance(result, dict) else None
            document_type = result.get('document_type') if isinstance(result, dict) else None
            document_date = result.get('document_date') if isinstance(result, dict) else None
            additional = result.get('additional', {}) if isinstance(result, dict) else {}

            # Build response summary with new validation format
            response_parts = [f"Result: {'YES' if belongs else 'NO'}"]
            if doc_page_count > 0:
                response_parts.append(f"Matching pages: {doc_page_count}")
            if do_not_belong:
                response_parts.append(f"Non-matching pages: {do_not_belong}")
            if page_number:
                response_parts.append(f"Page: {page_number}")
            if page_position:
                response_parts.append(f"Position: {page_position}")
            if company:
                response_parts.append(f"Company: {company}")
            if document_type:
                response_parts.append(f"Type: {document_type}")
            self.last_ollama_response = "\n".join(response_parts)

        # Save metadata to cache database (for future runs)
        if not isinstance(result, Exception) and start_time is not None:
            import time
            processing_time_ms = int((time.time() - start_time) * 1000)
            selected_model = self.config_manager.get_setting('Ollama', 'model')

            try:
                self.metadata_db.save_metadata(
                    evaluated_file,
                    result,
                    model_used=selected_model,
                    processing_time_ms=processing_time_ms
                )
                print(f"✓ Cached metadata for {os.path.basename(evaluated_file)} ({processing_time_ms}ms)")
            except Exception as e:
                print(f"⚠ Failed to cache metadata: {e}")

        # Store page metadata for ordering step
        metadata = {
            'image_path': evaluated_file,
            'detected_page_number': page_number,
            'total_pages': total_pages,
            'page_position': page_position,
            'confidence': confidence,
            'company': company,
            'document_type': document_type,
            'document_date': document_date,
            'additional': additional,
            'original_index': len(self.page_metadata_list),
            'from_cache': start_time is None  # True if from cache, False if from Ollama
        }
        self.page_metadata_list.append(metadata)

        if isinstance(result, Exception):
            # On error, mark as excluded but let user override
            self._update_thumbnail_state(evaluated_file, 'excluded')
            self._display_page_in_large_preview(evaluated_file)
            self._update_step1_buttons_for_state('excluded')

            # Safety check: ensure status_label still exists
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    self.status_label.setText(
                        f"⚠ Validation error. Page marked as excluded. "
                        f"Group has {len(self.current_group)} page(s). Use buttons to override."
                    )
                except RuntimeError:
                    print("⚠ Status label no longer exists")
            return

        if belongs:
            # Ollama says YES - auto-include
            self.current_group.append(evaluated_file)
            self.current_file_index += 1
            self._update_thumbnail_state(evaluated_file, 'included')
            self._display_page_in_large_preview(evaluated_file)
            self._update_step1_buttons_for_state('included')

            files_remaining = len(self.all_files) - self.current_file_index
            page_info = f" [Page {page_number}]" if page_number else ""

            # Safety check: ensure status_label still exists
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    self.status_label.setText(
                        f"✓ Page included automatically{page_info}. Group has {len(self.current_group)} page(s). "
                        f"({files_remaining} remaining)"
                    )
                except RuntimeError:
                    print("⚠ Status label no longer exists")

            # Auto-load next page
            if self.current_file_index < len(self.all_files):
                self._load_next_page_for_stitching()
            else:
                # Safety check: ensure status_label still exists
                if hasattr(self, 'status_label') and self.status_label:
                    try:
                        self.status_label.setText(
                            f"All pages processed. Group has {len(self.current_group)} page(s). "
                            f"Click Exclude to finish stitching."
                        )
                    except RuntimeError:
                        print("⚠ Status label no longer exists")
        else:
            # Ollama says NO - mark as excluded visually, let user decide
            self._update_thumbnail_state(evaluated_file, 'excluded')
            self._display_page_in_large_preview(evaluated_file)
            self._update_step1_buttons_for_state('excluded')

            # Build detailed exclusion message
            exclusion_reason = "doesn't match the current document"
            if do_not_belong:
                # Check if the newly added page (last one) is in do_not_belong
                total_pages_checked = len(self.current_group) + 1  # current group + new page
                if total_pages_checked in do_not_belong:
                    if doc_page_count > 0:
                        exclusion_reason = f"doesn't belong (only {doc_page_count} of {total_pages_checked} pages match)"
                    else:
                        exclusion_reason = "doesn't belong to this document"

            # Safety check: ensure status_label still exists
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    self.status_label.setText(
                        f"✗ AI suggests excluding: page {exclusion_reason}. "
                        f"Current group: {len(self.current_group)} page(s). "
                        f"Use buttons to Include, Skip, or Finish Group."
                    )
                except RuntimeError:
                    print("⚠ Status label no longer exists")

            # Start auto-approval on Approve button if group is not empty
            if len(self.current_group) > 0:
                if hasattr(self, 'exclude_button') and self.exclude_button:
                    try:
                        self._start_auto_approval(self.exclude_button, "Approve")
                    except RuntimeError:
                        print("⚠ Exclude button no longer exists")

    def _on_include_current_page(self):
        """User clicked Include button - change excluded page to included or include new page"""
        # Cancel Ollama request if active
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self._stop_spinner()
            if hasattr(self, 'step1_spinner_timer'):
                self.step1_spinner_timer.stop()

        # Stop auto-approval since user made a manual decision
        self._stop_auto_approval()

        if not self.current_page_path:
            return

        current_state = self.page_states.get(self.current_page_path, None)

        if current_state == 'excluded':
            # Change from excluded to included
            self._update_thumbnail_state(self.current_page_path, 'included')
            self._display_page_in_large_preview(self.current_page_path)
            self._update_step1_buttons_for_state('included')

            # Add back to group if it was removed
            if self.current_page_path not in self.current_group:
                self.current_group.append(self.current_page_path)

            # Phase 4: Update metadata display
            if hasattr(self, 'metadata_display'):
                self.metadata_display.set_bundle_files(self.current_group)

            # Phase 6: Visual feedback
            self._flash_preview("#059669")
            self._flash_thumbnail(self.current_page_path, "#059669")

            self.status_label.setText(f"Page marked as included. Group has {len(self.current_group)} page(s).")

            # Load next page to continue
            if self.current_file_index < len(self.all_files):
                self._load_next_page_for_stitching()
        else:
            # New page being included
            if self.current_page_path not in self.current_group:
                self.current_group.append(self.current_page_path)
                self.current_file_index += 1

            self._update_thumbnail_state(self.current_page_path, 'included')
            self._display_page_in_large_preview(self.current_page_path)

            # Phase 4: Update metadata display
            if hasattr(self, 'metadata_display'):
                self.metadata_display.set_bundle_files(self.current_group)

            # Phase 6: Visual feedback
            self._flash_preview("#059669")
            self._flash_thumbnail(self.current_page_path, "#059669")

            files_remaining = len(self.all_files) - self.current_file_index
            self.status_label.setText(f"✓ Page included. Group has {len(self.current_group)} page(s). ({files_remaining} remaining)")

            # Load next page
            if self.current_file_index < len(self.all_files):
                self._load_next_page_for_stitching()
            else:
                # No more files - need to explicitly end stitching
                self.status_label.setText("All pages processed. Click Exclude to finish stitching.")

    def _on_gallery_image_selected(self, file_path: str):
        """Handle image selection from gallery (Phase 3)"""
        # Display the selected image in the center preview
        self.current_page_path = file_path
        self._display_page_in_large_preview(file_path)

        # Update the current index
        if file_path in self.all_files:
            self.current_file_index = self.all_files.index(file_path)

        # Update the image gallery to highlight this file
        if hasattr(self, 'image_gallery'):
            self.image_gallery.set_current_file(file_path)

        # Phase 4: Update metadata display with current file
        if hasattr(self, 'metadata_display'):
            self.metadata_display.set_current_file(file_path)

        self.status_label.setText(f"Viewing: {os.path.basename(file_path)}")

    def _on_gallery_image_toggled(self, file_path: str, checked: bool):
        """Handle image checkbox toggle from gallery (Phase 3)"""
        if checked:
            # Add to current group if not already present
            if file_path not in self.current_group:
                self.current_group.append(file_path)
                self._update_thumbnail_state(file_path, 'included')
                self.status_label.setText(f"✓ {os.path.basename(file_path)} added to group. Group has {len(self.current_group)} page(s).")
        else:
            # Remove from current group
            if file_path in self.current_group:
                self.current_group.remove(file_path)
                self._update_thumbnail_state(file_path, 'excluded')
                self.status_label.setText(f"✗ {os.path.basename(file_path)} removed from group. Group has {len(self.current_group)} page(s).")

        # Phase 4: Update metadata display with current bundle
        if hasattr(self, 'metadata_display'):
            self.metadata_display.set_bundle_files(self.current_group)

    def _on_metadata_reanalyze(self, file_path: str):
        """Handle re-analyze request from metadata display (Phase 4)"""
        # TODO: Implement re-analysis functionality
        # This would trigger a new analysis for the specific file
        self.status_label.setText(f"Re-analysis requested for {os.path.basename(file_path)}")
        show_information(
            self,
            "Re-analyze",
            f"Re-analysis functionality will be implemented in a future phase.\n\nFile: {os.path.basename(file_path)}"
        )

    def _on_bundle_thumbnail_clicked(self, file_path: str):
        """Handle clicking on a bundle thumbnail (Phase 4)"""
        # Jump to the clicked page in the gallery and display it
        if file_path in self.all_files:
            self.current_file_index = self.all_files.index(file_path)
            self.current_page_path = file_path
            self._display_page_in_large_preview(file_path)

            # Update gallery selection
            if hasattr(self, 'image_gallery'):
                self.image_gallery.set_current_file(file_path)

            # Update metadata display
            if hasattr(self, 'metadata_display'):
                self.metadata_display.set_current_file(file_path)

            self.status_label.setText(f"Viewing: {os.path.basename(file_path)}")

    def _on_finish_group(self):
        """User clicked Finish Group button - finalize current group and move to Step 2"""
        # End stitching and move to Step 2 (without modifying current page state)
        if not self.current_group:
            show_information(self, "No Pages", "No pages in current group.")
            self._reset_to_start()
            return

        # Add current group to completed groups
        self.completed_groups.append(self.current_group.copy())

        self.status_label.setText(f"Document stitching complete. {len(self.current_group)} page(s) in group. Moving to analysis...")

        # Stop spinner animation
        if hasattr(self, 'step1_spinner_timer'):
            self.step1_spinner_timer.stop()

        # Transition to Step 2
        self._setup_step2_ui()

    def _on_exclude_current_page(self):
        """User clicked Exclude button - mark page as excluded and remove from group"""
        # Cancel Ollama request if active
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self._stop_spinner()
            if hasattr(self, 'step1_spinner_timer'):
                self.step1_spinner_timer.stop()

        # Stop auto-approval since user made a manual decision
        self._stop_auto_approval()

        if not self.current_page_path:
            return

        # Mark as excluded
        self._update_thumbnail_state(self.current_page_path, 'excluded')
        self._display_page_in_large_preview(self.current_page_path)

        # Remove from group if it was added
        if self.current_page_path in self.current_group:
            self.current_group.remove(self.current_page_path)

        # Phase 4: Update metadata display
        if hasattr(self, 'metadata_display'):
            self.metadata_display.set_bundle_files(self.current_group)

        # Update buttons based on new state
        self._update_step1_buttons_for_state('excluded')

        # Phase 6: Visual feedback
        self._flash_preview("#DC2626")
        self._flash_thumbnail(self.current_page_path, "#DC2626")

        self.status_label.setText(f"Page excluded. Group has {len(self.current_group)} page(s).")

    def _on_skip_and_continue(self):
        """User clicked Skip & Continue - accept exclusion and move to next page"""
        # Stop auto-approval since user made a manual decision
        self._stop_auto_approval()

        if not self.current_page_path:
            return

        # Keep the page marked as excluded (don't add to group)
        self._update_thumbnail_state(self.current_page_path, 'excluded')

        # Remove from group if it was somehow added
        if self.current_page_path in self.current_group:
            self.current_group.remove(self.current_page_path)

        # Move to next file
        self.current_file_index += 1

        # Load next page or finish
        if self.current_file_index < len(self.all_files):
            files_remaining = len(self.all_files) - self.current_file_index
            self.status_label.setText(
                f"Page skipped. Group has {len(self.current_group)} page(s). "
                f"({files_remaining} remaining)"
            )
            self._load_next_page_for_stitching()
        else:
            # No more files - need to finish stitching
            if not self.current_group:
                show_information(self, "No Pages", "No pages in current group.")
                self._reset_to_start()
                return

            # Add current group to completed groups
            self.completed_groups.append(self.current_group.copy())
            self.status_label.setText(
                f"All pages processed. {len(self.current_group)} page(s) in group. Moving to analysis..."
            )

            # Stop spinner animation
            if hasattr(self, 'step1_spinner_timer'):
                self.step1_spinner_timer.stop()

            # Transition to Step 2
            self._setup_step2_ui()

    def _on_cancel_ollama_step1(self):
        """User clicked Cancel Request in Step 1 - stop current Ollama validation and wait for user decision"""
        # Stop auto-approval since user cancelled
        self._stop_auto_approval()

        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()

        # Stop spinner
        if hasattr(self, 'step1_spinner_timer'):
            self.step1_spinner_timer.stop()
        self._stop_spinner()

        # Keep page in pending state (don't mark as excluded automatically)
        if self.current_page_path:
            self._update_thumbnail_state(self.current_page_path, 'pending')

        # Hide cancel request button
        self.cancel_request_button.setVisible(False)

        # Update status to indicate cancellation and wait for user decision
        files_remaining = len(self.all_files) - self.current_file_index - 1
        self.status_label.setText(
            f"Analysis cancelled. Choose to Include, Exclude, or Finish Group. ({files_remaining} files remaining)"
        )

        # Show Include and Finish Group buttons so user can manually decide
        self.include_button.setVisible(True)
        self.exclude_button.setVisible(True)  # This is the "Approve" button
        self.exclude_page_button.setVisible(False)  # Hide exclude button after cancellation

        # Don't automatically move to next file - wait for user decision
        # The user will click Include, Exclude, or Finish Group to proceed

    def _on_abort_stitching(self):
        """User clicked Abort - close window without saving"""
        # Cancel Ollama request if active
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self._stop_spinner()
            if hasattr(self, 'step1_spinner_timer'):
                self.step1_spinner_timer.stop()

        reply = show_question(
            self, "Abort Document Stitching",
            "Are you sure you want to abort?\n\nAll progress will be lost."
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    def _on_header_back_clicked(self):
        """Header back button clicked - route to appropriate back handler based on current step"""
        if not hasattr(self, 'current_step'):
            return

        # Route to appropriate back handler based on current step
        if self.current_step == WorkflowStep.ANALYSIS:
            self._on_back_to_step1()
        elif self.current_step == WorkflowStep.ORDERING:
            self._on_back_to_step2()
        elif self.current_step == WorkflowStep.FINALIZATION:
            self._on_back_to_step3()

    def _on_cache_indicator_label_clicked(self, event):
        """Handle clicks on cache indicator label"""
        # Only process clicks if it's showing CACHE (not OLLAMA)
        if hasattr(self, 'cache_indicator_label') and self.cache_indicator_label.text() == "CACHE":
            self._on_cache_indicator_clicked()

    def _on_cache_indicator_clicked(self):
        """User clicked cache indicator - clear cache and request fresh metadata from Ollama"""
        if self.current_step != WorkflowStep.STITCHING:
            return

        # Find the currently displayed page
        if not hasattr(self, 'current_page_path') or not self.current_page_path:
            return

        current_page = self.current_page_path

        # Confirm with user
        reply = show_question(
            self, "Refresh Metadata",
            f"Clear cached metadata for this page and request fresh analysis from Ollama?\n\n{os.path.basename(current_page)}"
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Delete cached metadata from database
        try:
            # Use the metadata_db to clear this file's cache
            if hasattr(self, 'metadata_db'):
                # Clear from database
                cursor = self.metadata_db.conn.cursor()
                cursor.execute("DELETE FROM active_metadata WHERE file_path = ?", (current_page,))
                self.metadata_db.conn.commit()
                print(f"✓ Cleared cached metadata for {os.path.basename(current_page)}")
        except Exception as e:
            print(f"⚠ Error clearing cache: {e}")

        # Remove from page_metadata_list
        self.page_metadata_list = [m for m in self.page_metadata_list if m['image_path'] != current_page]

        # Remove from page_states
        if current_page in self.page_states:
            del self.page_states[current_page]

        # Remove from current_group if it was included
        if current_page in self.current_group:
            self.current_group.remove(current_page)

        # Update thumbnail to pending state
        self._update_thumbnail_state(current_page, 'pending')

        # Request fresh metadata from Ollama
        self.status_label.setText(f"Requesting fresh analysis from Ollama for {os.path.basename(current_page)}...")
        self._load_next_page_for_stitching()

    def _on_status_indicator_clicked(self, image_path, current_state):
        """User clicked status indicator - toggle between included/excluded"""
        if self.current_step != WorkflowStep.STITCHING:
            return

        # Toggle state
        if current_state == 'included':
            # Switch to excluded
            self._update_thumbnail_state(image_path, 'excluded')
            self.page_states[image_path] = 'excluded'

            # Remove from current_group
            if image_path in self.current_group:
                self.current_group.remove(image_path)

            # Update status
            self.status_label.setText(
                f"✗ Page excluded. Group has {len(self.current_group)} page(s). "
                f"Click status indicator to include again."
            )
        elif current_state == 'excluded':
            # Switch to included
            self._update_thumbnail_state(image_path, 'included')
            self.page_states[image_path] = 'included'

            # Add to current_group if not already there
            if image_path not in self.current_group:
                self.current_group.append(image_path)

            # Update status
            self.status_label.setText(
                f"✓ Page included. Group has {len(self.current_group)} page(s). "
                f"Click status indicator to exclude again."
            )

        # Refresh the preview to update the indicator
        self._display_page_in_large_preview(image_path, show_indicator=True)

    def _display_page_in_large_preview(self, image_path, show_indicator=True):
        """Display a page image in the large central preview area with status indicator (Phase 8: With rotation)

        Args:
            image_path: Path to the image file
            show_indicator: Whether to show the green check/red X indicator
        """
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.large_preview_label.setText("Error loading image")
            self.large_preview_label.setStyleSheet("background-color: #ffe6e6; border: 2px solid #ccc;")
            return

        # Phase 8: Apply rotation from database (display-only, source file unchanged)
        rotation_degrees = self.metadata_db.get_rotation(image_path)
        if rotation_degrees != 0:
            # Create transform for rotation
            transform = QTransform()
            transform.rotate(rotation_degrees)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        # Apply zoom level to scaling
        target_size = self.large_preview_label.size()
        zoomed_size = target_size * self.zoom_level

        # Scale to fit preview area while maintaining aspect ratio and respecting zoom
        scaled_pixmap = pixmap.scaled(
            zoomed_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.large_preview_label.setPixmap(scaled_pixmap)
        self.large_preview_label.setStyleSheet("background-color: #ffffff; border: 2px solid #2563EB;")

        # Phase 4: Update metadata display when displaying a page
        if hasattr(self, 'metadata_display') and self.current_step == WorkflowStep.STITCHING:
            self.metadata_display.set_current_file(image_path)

        # Add or update status overlay indicator
        if show_indicator and self.current_step == WorkflowStep.STITCHING:
            state = self.page_states.get(image_path, 'pending')

            # Create overlay if it doesn't exist
            if not hasattr(self, 'preview_overlay'):
                self.preview_overlay = QLabel(self.large_preview_label)

            # Position in upper right corner
            self.preview_overlay.setGeometry(
                self.large_preview_label.width() - 60, 10, 50, 50
            )

            # Set style based on state
            if state == 'included':
                self.preview_overlay.setText("✓")
                self.preview_overlay.setStyleSheet(
                    "QLabel { background-color: #059669; color: white; "
                    "font-size: 32pt; font-weight: bold; border-radius: 25px; "
                    "padding: 5px; }"
                )
                # Make clickable (toggle to excluded)
                self.preview_overlay.setCursor(Qt.CursorShape.PointingHandCursor)
                self.preview_overlay.setToolTip("Included - Click to exclude")
                self.preview_overlay.mousePressEvent = lambda event: self._on_status_indicator_clicked(image_path, 'included')
            elif state == 'excluded':
                self.preview_overlay.setText("✗")
                self.preview_overlay.setStyleSheet(
                    "QLabel { background-color: #DC2626; color: white; "
                    "font-size: 32pt; font-weight: bold; border-radius: 25px; "
                    "padding: 5px; }"
                )
                # Make clickable (toggle to included)
                self.preview_overlay.setCursor(Qt.CursorShape.PointingHandCursor)
                self.preview_overlay.setToolTip("Excluded - Click to include")
                self.preview_overlay.mousePressEvent = lambda event: self._on_status_indicator_clicked(image_path, 'excluded')
            else:  # pending
                self.preview_overlay.setText("?")
                self.preview_overlay.setStyleSheet(
                    "QLabel { background-color: #6B7280; color: white; "
                    "font-size: 32pt; font-weight: bold; border-radius: 25px; "
                    "padding: 5px; }"
                )
                # Not clickable when pending
                self.preview_overlay.setCursor(Qt.CursorShape.ArrowCursor)
                self.preview_overlay.setToolTip("Pending...")
                self.preview_overlay.mousePressEvent = None

            self.preview_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_overlay.show()
            self.preview_overlay.raise_()  # Bring to front

            # Add cache/AI indicator label to the left of status overlay
            # Find metadata for this image to determine if it came from cache
            page_meta = next((m for m in self.page_metadata_list if m['image_path'] == image_path), None)
            from_cache = page_meta.get('from_cache', False) if page_meta else False

            # Create cache indicator label if it doesn't exist
            if not hasattr(self, 'cache_indicator_label'):
                self.cache_indicator_label = QLabel(self.large_preview_label)
                self.cache_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Click handler will check if it's cached when clicked
                self.cache_indicator_label.mousePressEvent = self._on_cache_indicator_label_clicked

            # Position to the left of status overlay
            self.cache_indicator_label.setGeometry(
                self.large_preview_label.width() - 130, 10, 60, 30
            )

            # Set text and styling based on cache status
            if from_cache:
                self.cache_indicator_label.setText("CACHE")
                self.cache_indicator_label.setStyleSheet(
                    "QLabel { "
                    "background-color: rgba(100, 150, 255, 200); "
                    "color: white; "
                    "border: 2px solid rgba(50, 100, 200, 250); "
                    "border-radius: 5px; "
                    "padding: 5px; "
                    "font-size: 10pt; "
                    "font-weight: bold; "
                    "}"
                )
                self.cache_indicator_label.setToolTip("Decision from CACHE - Click to refresh from Ollama")
                self.cache_indicator_label.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.cache_indicator_label.setText("OLLAMA")
                self.cache_indicator_label.setStyleSheet(
                    "QLabel { "
                    "background-color: rgba(100, 200, 100, 200); "
                    "color: white; "
                    "border: 2px solid rgba(50, 150, 50, 250); "
                    "border-radius: 5px; "
                    "padding: 5px; "
                    "font-size: 10pt; "
                    "font-weight: bold; "
                    "}"
                )
                self.cache_indicator_label.setToolTip("Decision from OLLAMA (real-time)")
                self.cache_indicator_label.setCursor(Qt.CursorShape.ArrowCursor)

            self.cache_indicator_label.show()
            self.cache_indicator_label.raise_()
        elif hasattr(self, 'preview_overlay'):
            self.preview_overlay.hide()
            if hasattr(self, 'cache_indicator_label'):
                self.cache_indicator_label.hide()

        # Update zoom control position after displaying image
        self._update_zoom_control_position()

        # Update thumbnail selection border in Step 1
        if self.current_step == WorkflowStep.STITCHING:
            self._update_thumbnail_selection(image_path)

    def _add_thumbnail(self, image_path, state='included'):
        """Add a thumbnail to the thumbnail strip with status indicator"""
        # Check if this image is already in the thumbnail strip
        if image_path in self.page_states:
            print(f"⚠ Skipping duplicate thumbnail: {os.path.basename(image_path)} (already in strip)")
            return

        # Check if thumbnail already exists in layout
        for i in range(self.thumbnail_layout.count()):
            widget = self.thumbnail_layout.itemAt(i).widget()
            if widget and widget.property("image_path") == image_path:
                print(f"⚠ Thumbnail already exists in layout: {os.path.basename(image_path)}")
                return

        self.page_states[image_path] = state
        thumbnail = self._create_thumbnail_widget(image_path, state)
        self.thumbnail_layout.addWidget(thumbnail)

    def _update_thumbnail_state(self, image_path, new_state):
        """Update the visual state of a thumbnail"""
        self.page_states[image_path] = new_state

        # Find and update the thumbnail
        for i in range(self.thumbnail_layout.count()):
            widget = self.thumbnail_layout.itemAt(i).widget()
            if widget and widget.property("image_path") == image_path:
                overlay = widget.property("overlay")
                if overlay:
                    if new_state == 'included':
                        overlay.setText("✓")
                        overlay.setStyleSheet(
                            "QLabel { background-color: #059669; color: white; "
                            "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                            "padding: 2px; }"
                        )
                    elif new_state == 'excluded':
                        overlay.setText("✗")
                        overlay.setStyleSheet(
                            "QLabel { background-color: #DC2626; color: white; "
                            "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                            "padding: 2px; }"
                        )
                    else:  # pending
                        overlay.setText("?")
                        overlay.setStyleSheet(
                            "QLabel { background-color: #6B7280; color: white; "
                            "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                            "padding: 2px; }"
                        )
                break

    def _update_step1_buttons_for_state(self, state):
        """Update button visibility based on current page state and Ollama request status

        Button rules:
        1. Cancel Request - Show at top when: Ollama request is active
        2. Approve - Show when: no active Ollama request AND at least one page is "Included"
        3. Include - Show when: current page status is NOT "Included"
        4. Exclude - Show when: current page status IS "Included" OR "Pending"
        5. Exit (Abort) - Always show
        """
        # Check if Ollama request is active
        is_ollama_active = hasattr(self, 'worker_thread') and self.worker_thread.isRunning()

        # Check if there's at least one included page
        has_included_pages = len(self.current_group) > 0

        # 1. Cancel Request button - at top, show when Ollama is active
        self.cancel_request_button.setVisible(is_ollama_active)

        # 2. Approve button - show when no active request and has included pages
        self.exclude_button.setVisible(not is_ollama_active and has_included_pages)

        # 3. Include button - show when current page is NOT included
        self.include_button.setVisible(state != 'included')

        # 4. Exclude button - show when current page IS included OR pending
        self.exclude_page_button.setVisible(state in ('included', 'pending'))

        # 5. Exit (Abort) button - always visible
        self.abort_button.setVisible(True)

    def _create_thumbnail_widget(self, image_path, state='pending'):
        """Create a clickable thumbnail widget with status overlay

        Args:
            image_path: Path to the image file
            state: 'included' (green check), 'excluded' (red X), or 'pending' (gray question mark)
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Container for thumbnail with overlay
        thumb_container = QWidget()
        thumb_container.setFixedSize(180, 180)

        # Thumbnail image
        label = QLabel(thumb_container)
        label.setGeometry(0, 0, 180, 180)
        label.setFrameShape(QFrame.Shape.Box)
        pixmap = QPixmap(image_path)

        # Phase 8: Apply rotation from database (display-only)
        rotation_degrees = self.metadata_db.get_rotation(image_path)
        if rotation_degrees != 0:
            transform = QTransform()
            transform.rotate(rotation_degrees)
            pixmap = pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

        scaled_pixmap = pixmap.scaledToHeight(180, Qt.TransformationMode.SmoothTransformation)
        label.setPixmap(scaled_pixmap)
        label.setStyleSheet("border: 2px solid #ccc;")

        # Status overlay (green check, red X, or gray question mark)
        overlay = QLabel(thumb_container)
        overlay.setGeometry(140, 10, 30, 30)  # Top-right corner
        if state == 'included':
            overlay.setText("✓")
            overlay.setStyleSheet(
                "QLabel { background-color: #059669; color: white; "
                "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                "padding: 2px; }"
            )
        elif state == 'excluded':
            overlay.setText("✗")
            overlay.setStyleSheet(
                "QLabel { background-color: #DC2626; color: white; "
                "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                "padding: 2px; }"
            )
        else:  # pending
            overlay.setText("?")
            overlay.setStyleSheet(
                "QLabel { background-color: #6B7280; color: white; "
                "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                "padding: 2px; }"
            )
        overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Store state and image path
        container.setProperty("image_path", image_path)
        container.setProperty("state", state)
        container.setProperty("overlay", overlay)  # Store for updates

        # Make clickable
        label.mousePressEvent = lambda event: self._on_thumbnail_clicked(image_path)
        label.setCursor(Qt.CursorShape.PointingHandCursor)

        layout.addWidget(thumb_container)

        # Page number
        page_num = os.path.basename(image_path)[:15]
        page_label = QLabel(page_num)
        page_label.setStyleSheet("font-size: 8pt; color: #666;")
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(page_label)

        return container

    def _update_thumbnail_selection(self, selected_image_path):
        """Update visual selection border on thumbnails"""
        for i in range(self.thumbnail_layout.count()):
            widget = self.thumbnail_layout.itemAt(i).widget()
            if widget:
                thumb_path = widget.property("image_path")
                if thumb_path == selected_image_path:
                    # Selected thumbnail - add very prominent border and shadow
                    widget.setStyleSheet(
                        "border: 6px solid #2563EB;"
                        "border-radius: 8px; "
                        "background-color: #E3F2FD; "
                        "padding: 2px;"
                    )
                else:
                    # Unselected thumbnail - thin gray border
                    widget.setStyleSheet(
                        "border: 2px solid #CCCCCC; "
                        "border-radius: 4px; "
                        "background-color: transparent;"
                    )

    def _on_thumbnail_clicked(self, image_path):
        """Handle thumbnail click - update large preview and set as current page"""
        self.current_page_path = image_path
        self._display_page_in_large_preview(image_path)

        # Update visual selection
        self._update_thumbnail_selection(image_path)

        # Update buttons based on current page state
        if self.current_step == WorkflowStep.STITCHING:
            state = self.page_states.get(image_path, 'included')
            self._update_step1_buttons_for_state(state)

    def _reset_to_start(self):
        """Reset to initial state"""
        self.current_file_index = 0
        self.current_group = []
        self.current_page_path = None
        self.completed_groups = []
        self.start_scan_button.setVisible(True)
        self.start_scan_button.setEnabled(True)
        self.include_button.setVisible(False)
        self.exclude_button.setVisible(False)
        # Phase 8: Hide rotation controls
        if hasattr(self, 'rotation_controls_widget'):
            self.rotation_controls_widget.setVisible(False)
        self.large_preview_label.clear()
        self.large_preview_label.setText("Click 'Start Scanning' to begin\ndocument stitching")
        self.large_preview_label.setStyleSheet("background-color: #f9f9f9; border: 2px dashed #ccc; font-size: 14pt; color: #999;")
        self._clear_thumbnails()

    def _clear_thumbnails(self):
        """Clear all thumbnails from strip"""
        while self.thumbnail_layout.count():
            item = self.thumbnail_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _remove_excluded_thumbnails(self):
        """Remove thumbnails for pages not in current_group"""
        i = 0
        while i < self.thumbnail_layout.count():
            item = self.thumbnail_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                image_path = widget.property("image_path")
                # Remove if this page is not in the current group
                if image_path and image_path not in self.current_group:
                    self.thumbnail_layout.takeAt(i)
                    widget.deleteLater()
                    # Don't increment i, check same position again
                else:
                    i += 1
            else:
                i += 1

    # ===== STEP 2: DOCUMENT ANALYSIS HANDLERS =====

    def _make_thumbnails_clickable(self):
        """Make thumbnails clickable to change preview (already handled in _create_thumbnail_widget)"""
        pass  # Already implemented in _create_thumbnail_widget

    def _start_metadata_extraction(self):
        """Automatically extract metadata using Ollama"""
        if not self.current_group:
            return

        selected_model = self.config_manager.get_setting('Ollama', 'model')
        if not selected_model:
            show_warning(self, "No Model Selected", "Please select a model.")
            return

        # Enable cancel button during processing
        self.cancel_ollama_button.setEnabled(True)
        self.continue_button.setEnabled(False)

        self._start_spinner()
        self._set_status_with_time(f"Extracting document metadata with {selected_model}...")

        # Get title keywords from settings
        title_keywords = self.config_manager.get_setting("DocumentProcessing", "title_keywords", "Invoice, Statement, Bill")

        # Store model name for popup
        self.current_extraction_model = selected_model

        # DEBUG: Verify current_group contents
        import os
        print(f"\n=== DEBUG: Metadata Extraction ===")
        print(f"current_group length: {len(self.current_group)}")
        for i, img_path in enumerate(self.current_group, 1):
            exists = os.path.exists(img_path) if img_path else False
            print(f"  Image {i}: exists={exists} | path={img_path}")
        print("=================================\n")

        # Store the request prompt for debugging (with file paths)
        file_list = "\n".join(f"  {i}. {path} (exists: {os.path.exists(path)})"
                             for i, path in enumerate(self.current_group, 1))

        self.last_ollama_request = f"""You are an expert at extracting key information from scanned documents.
Analyze the provided images to identify the following:
1.  **Source Company:** The name of the organization that issued the document. Look at headers, footers, logos, or return addresses.
2.  **Document Title:** The main purpose or type of the document (e.g., Invoice, Statement, Bill, Receipt, Report, Contract, Agreement). Consider the provided keywords: '{title_keywords}'. Choose the most appropriate and concise title.
3.  **Relevant Date:** The primary date associated with the document (e.g., issue date, statement date, invoice date, contract date). Prioritize the most prominent and relevant date.
Respond ONLY in JSON format. Your JSON should contain three keys: 'company', 'title', and 'date'.
If any information cannot be found, use null for its value.
Example: {{ "company": "Acme Corp", "title": "Invoice", "date": "2023-10-26" }}

Model: {selected_model}
Images: {len(self.current_group)} page(s)

Files being sent to Ollama:
{file_list}"""

        self.worker_thread = OllamaWorker(
            self.ollama_service.extract_document_info,
            selected_model,
            self.current_group,
            title_keywords
        )
        self.worker_thread.finished.connect(self._on_metadata_extracted)
        self.worker_thread.progress.connect(self._on_worker_progress)
        self.worker_thread.start()

    def _on_metadata_extracted(self, result):
        """Handle metadata extraction result"""
        self._stop_spinner()

        # Safety check: ensure UI elements still exist (user may have navigated away)
        if not hasattr(self, 'cancel_ollama_button') or not self.cancel_ollama_button:
            print("⚠ Metadata extraction completed but UI has changed - ignoring result")
            return

        # Try to access button, but handle gracefully if deleted
        try:
            self.cancel_ollama_button.setEnabled(False)
        except RuntimeError:
            print("⚠ Metadata extraction completed but Step 2 UI no longer exists")
            return

        if isinstance(result, Exception):
            show_warning(
                self, "Extraction Failed",
                f"Ollama failed to extract metadata.\n\nError: {result}\n\n"
                f"Please fill in the fields manually."
            )
            # Safety check before accessing UI elements
            if hasattr(self, 'continue_button') and self.continue_button:
                try:
                    self.continue_button.setEnabled(True)
                except RuntimeError:
                    pass
            self.status_label.setText("Metadata extraction failed. Fill manually.")
            return

        # Populate fields (with safety checks)
        self.extracted_metadata = result

        try:
            if hasattr(self, 'company_edit') and self.company_edit:
                self.company_edit.setCurrentText(result.get('company', '') or '')
            if hasattr(self, 'title_edit') and self.title_edit:
                self.title_edit.setCurrentText(result.get('title', '') or '')
            if hasattr(self, 'date_edit') and self.date_edit:
                self.date_edit.setText(result.get('date', '') or '')
        except RuntimeError as e:
            print(f"⚠ UI elements deleted during metadata update: {e}")
            return

        # Store raw response for debugging
        self.last_ollama_response = str(result)
        self.last_ollama_response_type = "Metadata Extraction"

        # Hide cancel button and enable continue button (with safety checks)
        try:
            if hasattr(self, 'cancel_ollama_button') and self.cancel_ollama_button:
                self.cancel_ollama_button.setVisible(False)
            if hasattr(self, 'continue_button') and self.continue_button:
                self.continue_button.setEnabled(True)
        except RuntimeError as e:
            print(f"⚠ Button access failed: {e}")
            return

        self.status_label.setText("✓ Metadata extracted successfully. Review and click Approve.")

        # Start auto-approval if all required fields have values
        company = result.get('company')
        title = result.get('title')
        if company and title:  # Both company and title are non-null
            try:
                if hasattr(self, 'continue_button') and self.continue_button:
                    self._start_auto_approval(self.continue_button, "Approve")
            except RuntimeError:
                pass  # UI changed, skip auto-approval

    def _on_continue_to_step3(self):
        """User clicked Continue - move to Step 3 (Finalization)"""
        # Validate fields
        company = self.company_edit.currentText().strip()
        title = self.title_edit.currentText().strip()

        if not company:
            show_warning(self, "Missing Information", "Please enter a Company name.")
            return

        if not title:
            show_warning(self, "Missing Information", "Please enter a Document Title.")
            return

        # Update extracted metadata with user edits
        self.extracted_metadata = {
            'company': company,
            'title': title,
            'date': self.date_edit.text().strip() or 'NoDate'
        }

        self.status_label.setText("Moving to page ordering...")

        # Transition to Step 3 (Order Pages)
        self._setup_step3_ui()

    def _on_cancel_ollama(self):
        """User clicked Cancel Ollama - stop worker and allow manual entry"""
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.terminate()
            self.worker_thread.wait()
            self._stop_spinner()
            self.cancel_ollama_button.setEnabled(False)
            self.continue_button.setEnabled(True)
            self.status_label.setText("Ollama cancelled. Fill fields manually and click Continue.")

    def _on_abort(self):
        """User clicked Abort - return to main window"""
        reply = show_question(
            self, "Abort Processing",
            "Are you sure you want to abort? All progress will be lost."
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    # ===== STEP 3: DOCUMENT FINALIZATION HANDLERS =====

    def _create_pdf_for_preview(self):
        """Create PDF and display preview"""
        if not self.current_group or not self.extracted_metadata:
            show_warning(self, "Error", "No document data to create PDF.")
            return

        try:
            self.status_label.setText("Creating PDF preview...")

            # Use file processor to create PDF
            company = self.extracted_metadata.get('company', 'Unknown')
            title = self.extracted_metadata.get('title', 'Document')
            date = self.extracted_metadata.get('date', 'NoDate')

            # Construct filename from metadata
            # Replace any invalid filename characters
            safe_company = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in company)
            safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title)
            safe_date = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in date)

            output_filename = f"{safe_company} - {safe_title} - {safe_date}.pdf"

            # Phase 8: Build rotation map from database for PDF generation
            rotation_map = {}
            for img_path in self.current_group:
                rotation_degrees = self.metadata_db.get_rotation(img_path)
                if rotation_degrees != 0:
                    rotation_map[img_path] = rotation_degrees

            # Create PDF (saved in output folder) - non-searchable for now
            self.created_pdf_path = self.file_processor.create_searchable_pdf(
                self.current_group,
                output_filename,
                extracted_text_coords={},  # No OCR text for now
                is_searchable=False,  # Create image-only PDF
                rotation_map=rotation_map  # Phase 8: Apply rotations from database
            )

            self.status_label.setText(f"✓ PDF created: {os.path.basename(self.created_pdf_path)}")

            # Display first page in preview
            if self.current_group:
                self._display_page_in_large_preview(self.current_group[0])

            # Update Step 4 UI with file information
            self._update_step4_file_info()

            # Start auto-approval on Accept & Delete Sources button
            self._start_auto_approval(self.accept_delete_button, "✓ Accept & Delete Sources")

        except Exception as e:
            show_critical(self, "PDF Creation Error", f"Failed to create PDF.\n\nError: {e}")
            self.status_label.setText(f"Error creating PDF: {e}")

    def _update_step4_file_info(self):
        """Update Step 4 left panel with file information and hyperlinks"""
        if not hasattr(self, 'created_pdf_path') or not os.path.exists(self.created_pdf_path):
            return

        # Get file info
        filename = os.path.basename(self.created_pdf_path)
        file_size_bytes = os.path.getsize(self.created_pdf_path)

        # Format file size
        if file_size_bytes < 1024:
            file_size_str = f"{file_size_bytes} bytes"
        elif file_size_bytes < 1024 * 1024:
            file_size_str = f"{file_size_bytes / 1024:.1f} KB"
        else:
            file_size_str = f"{file_size_bytes / (1024 * 1024):.1f} MB"

        # Find the position to insert (after "Type: Image PDF" label)
        insert_position = None
        for i in range(self.left_panel_layout.count()):
            item = self.left_panel_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                if item.widget() == self.pdf_searchable_label:
                    insert_position = i + 1
                    break

        if insert_position is None:
            return

        # Add spacing
        spacer = QWidget()
        spacer.setFixedHeight(10)
        self.left_panel_layout.insertWidget(insert_position, spacer)
        insert_position += 1

        # Add filename label
        filename_label = QLabel(f"<b>File:</b> {filename}")
        filename_label.setWordWrap(True)
        filename_label.setStyleSheet("font-size: 9pt;")
        self.left_panel_layout.insertWidget(insert_position, filename_label)
        insert_position += 1

        # Add file size label
        size_label = QLabel(f"<b>Size:</b> {file_size_str}")
        size_label.setStyleSheet("font-size: 9pt;")
        self.left_panel_layout.insertWidget(insert_position, size_label)
        insert_position += 1

        # Add spacing
        spacer2 = QWidget()
        spacer2.setFixedHeight(5)
        self.left_panel_layout.insertWidget(insert_position, spacer2)
        insert_position += 1

        # Add hyperlink to open PDF
        pdf_link = QLabel(f'<a href="file:///{self.created_pdf_path}">Open PDF</a>')
        pdf_link.setStyleSheet("font-size: 9pt;")
        pdf_link.setOpenExternalLinks(False)
        pdf_link.linkActivated.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.created_pdf_path)))
        self.left_panel_layout.insertWidget(insert_position, pdf_link)
        insert_position += 1

        # Add hyperlink to open output folder
        output_folder = os.path.dirname(self.created_pdf_path)
        folder_link = QLabel(f'<a href="file:///{output_folder}">Open Folder</a>')
        folder_link.setStyleSheet("font-size: 9pt;")
        folder_link.setOpenExternalLinks(False)
        folder_link.linkActivated.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(output_folder)))
        self.left_panel_layout.insertWidget(insert_position, folder_link)

    def _reset_ui_state(self):
        """Reset all UI controls and state to initial defaults"""
        # Clear thumbnails
        self._clear_thumbnails()

        # Reset state variables
        self.page_states = {}
        self.current_page_path = None
        self.extracted_metadata = {}

        # Reset large preview
        self.large_preview_label.clear()
        self.large_preview_label.setText("Processing...")
        self.large_preview_label.setStyleSheet("background-color: #f9f9f9; border: 2px dashed #ccc; font-size: 14pt; color: #999;")

        # Reset status label
        self.status_label.setText("")

        # Stop any auto-approval timers
        self._stop_auto_approval()

    def _finalize_document(self, delete_sources):
        """Finalize document - handle PDF, archive metadata, and source files"""
        if not hasattr(self, 'created_pdf_path'):
            show_warning(self, "Error", "No PDF created yet.")
            return

        try:
            # Archive metadata to database before cleanup
            try:
                document_metadata = {
                    'company': self.extracted_metadata.get('company'),
                    'title': self.extracted_metadata.get('title'),
                    'date': self.extracted_metadata.get('date'),
                    'additional': {}
                }

                self.metadata_db.archive_document(
                    pdf_path=self.created_pdf_path,
                    source_files=self.current_group,
                    document_metadata=document_metadata
                )

                print(f"✓ Archived metadata for {os.path.basename(self.created_pdf_path)}")
                print(f"  - {len(self.current_group)} source files")
                print(f"  - Company: {document_metadata.get('company')}")
                print(f"  - Type: {document_metadata.get('title')}")

            except Exception as e:
                print(f"⚠ Failed to archive metadata: {e}")
                # Don't fail the whole operation if archival fails

            # Reset UI state before processing
            self._reset_ui_state()

            # Delete source files if requested
            if delete_sources:
                for source_file in self.current_group:
                    if os.path.exists(source_file):
                        os.remove(source_file)

            # Check if there are more files to process
            if self.current_file_index < len(self.all_files):
                # Automatically proceed to next document
                self.current_group = []
                self._setup_step1_ui()
                self._load_next_page_for_stitching()
            else:
                # No more files - close the window
                self.close()

        except Exception as e:
            show_critical(self, "Finalization Error", f"Error: {e}")

    def _on_reject_pdf(self):
        """User clicked Reject - delete PDF and return"""
        if hasattr(self, 'created_pdf_path') and os.path.exists(self.created_pdf_path):
            try:
                os.remove(self.created_pdf_path)
                self.status_label.setText("PDF rejected and deleted.")
            except Exception as e:
                show_warning(self, "Delete Error", f"Could not delete PDF: {e}")

        reply = show_question(
            self, "PDF Rejected",
            "PDF has been rejected. Start over with this document?"
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Reset current group and go back to Step 1
            # Put files back in all_files at correct position
            self.current_file_index -= len(self.current_group)
            self.current_group = []
            self._setup_step1_ui()
            self._load_next_page_for_stitching()
        else:
            self.close()

    def _finalize_current_group(self):
        """DEPRECATED - replaced by Step 2/3 workflow"""
        # This method is no longer used in 3-step workflow
        pass

    # MORE DEPRECATED METHODS FROM OLD WORKFLOW - REMOVED
    # (_on_info_extracted, _approve_and_process, _on_text_coords_extracted, _show_final_confirmation)
    # All replaced by Step 2 and Step 3 handlers in the new 3-step workflow

    # ===== PHASE 7: Bundle Suggestion Methods =====

    def _on_analysis_progress(self, status_text, current, total):
        """Update status during analysis"""
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(
                f"Analyzing files: {current}/{total} - {status_text}"
            )

    def _on_analysis_complete_proceed_to_bundling(self, stats):
        """Analysis complete - proceed to bundle suggestions"""
        print(f"[ConvertImages] Analysis complete: {stats}")
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.setText(
                f"Analysis complete. Generating bundle suggestions for {len(self.all_files)} file(s)..."
            )
        # Proceed to bundle suggestions
        QTimer.singleShot(500, self._load_and_show_bundle_suggestions)

    def _load_and_show_bundle_suggestions(self):
        """Generate and display bundle suggestions (Step 0)"""
        try:
            # Generate bundle suggestions using BundlingService
            print(f"[Bundle Suggestions] Generating recommendations for {len(self.all_files)} files...")
            bundles = self.bundling_service.generate_bundle_recommendations(self.all_files)

            if bundles and len(bundles) > 0:
                # Show bundle suggestions view
                if not hasattr(self, 'bundle_suggestions_view') or self.bundle_suggestions_view is None:
                    print("[Bundle Suggestions] ERROR: bundle_suggestions_view not initialized!")
                    self._show_manual_view()
                    self._load_next_page_for_stitching()
                    return
                self._show_bundle_view()
                self.bundle_suggestions_view.set_bundles(bundles)
                print(f"[Bundle Suggestions] Showing {len(bundles)} suggestions")
                self.status_label.setText(f"Found {len(bundles)} bundle suggestion(s). Review and accept/modify/reject each.")
            else:
                # No bundles found, skip to manual workflow
                print("[Bundle Suggestions] No bundles generated, skipping to manual workflow")
                self.status_label.setText("No bundle suggestions generated. Proceeding to manual stitching...")
                QTimer.singleShot(1000, self._on_skip_to_manual_workflow)

        except Exception as e:
            print(f"[Bundle Suggestions] Error generating suggestions: {e}")
            import traceback
            traceback.print_exc()
            # Fall back to manual workflow
            show_warning(
                self,
                "Bundle Suggestions Failed",
                f"Could not generate bundle suggestions: {e}\n\nProceeding to manual workflow."
            )
            self._on_skip_to_manual_workflow()

    # ===== PHASE 7: Bundle Suggestion Handlers =====

    def _on_bundle_accepted(self, bundle_data):
        """Handle bundle acceptance - add to completed groups"""
        print(f"[Bundle] Accepted: {bundle_data.get('document_type')} - {bundle_data.get('company')}")
        file_paths = bundle_data.get('file_paths', [])
        if file_paths:
            self.completed_groups.append(file_paths)
            group_key = f"group_{len(self.completed_groups)}"
            self.extracted_metadata[group_key] = {
                'company': bundle_data.get('company'),
                'title': bundle_data.get('document_type'),
                'date': bundle_data.get('document_date')
            }
            show_information(
                self, "Bundle Accepted",
                f"Accepted {len(file_paths)} page(s) for '{bundle_data.get('document_type')}'.\n\n"
                "Regenerating suggestions for remaining pages..."
            )

            # Regenerate bundle suggestions for remaining pages
            bundled_files = set()
            for group in self.completed_groups:
                bundled_files.update(group)
            remaining_files = [f for f in self.all_files if f not in bundled_files]

            if remaining_files:
                # Regenerate suggestions for remaining files
                bundles = self.bundling_service.generate_bundle_recommendations(remaining_files)
                if bundles and len(bundles) > 0:
                    if hasattr(self, 'bundle_suggestions_view') and self.bundle_suggestions_view is not None:
                        self.bundle_suggestions_view.set_bundles(bundles)
                        self.status_label.setText(f"Updated: {len(bundles)} suggestion(s) for {len(remaining_files)} remaining page(s).")
                else:
                    # No more bundles, ask if user wants to process manually
                    self._check_remaining_pages_after_bundles()
            else:
                # All files bundled
                self._check_remaining_pages_after_bundles()

    def _on_bundle_modified(self, bundle_data):
        """Handle bundle modification - load into manual stitching workflow"""
        print(f"[Bundle] Modify requested: {bundle_data.get('document_type')}")
        file_paths = bundle_data.get('file_paths', [])
        if not file_paths:
            return

        # Store the suggested metadata for this bundle
        self.extracted_metadata['suggestion'] = {
            'company': bundle_data.get('company'),
            'title': bundle_data.get('document_type'),
            'date': bundle_data.get('document_date')
        }

        # Pre-populate current_group with the bundle pages
        self.current_group = list(file_paths)

        # Show notification
        show_information(
            self,
            "Modify Bundle",
            f"Loading {len(file_paths)} page(s) into manual stitching view.\n\n"
            "You can add/remove pages, then approve the bundle when ready."
        )

        # Ensure step 1 UI is initialized (if coming from bundle view)
        if not hasattr(self, 'page_states'):
            self._setup_step1_ui()

        # Transition to manual stitching view
        self._show_manual_view()

        # Add thumbnails for pre-loaded bundle pages
        for file_path in file_paths:
            self._add_thumbnail(file_path, 'included')
            self.page_states[file_path] = 'included'

        # Update metadata display with bundle info
        if hasattr(self, 'metadata_display') and file_paths:
            self.metadata_display.set_bundle_files(self.current_group)
            self.metadata_display.set_current_file(file_paths[0])

        # Load first page in the bundle for preview
        if file_paths:
            self.current_page_path = file_paths[0]
            self._display_page_in_large_preview(file_paths[0])

        # Set file index to start after these files
        self.current_file_index = 0  # Reset to allow adding more pages

        self.status_label.setText(f"Modifying bundle with {len(file_paths)} page(s). Add/remove pages as needed, then approve.")

    def _on_bundle_rejected(self, bundle_data):
        """Handle bundle rejection - pages remain in pool for manual processing"""
        print(f"[Bundle] Rejected: {bundle_data.get('document_type')}")
        file_paths = bundle_data.get('file_paths', [])

        # Display confirmation
        show_information(
            self, "Bundle Rejected",
            f"Rejected bundle for '{bundle_data.get('document_type')}'.\n\n"
            f"{len(file_paths)} page(s) will remain available for manual processing or re-bundling."
        )

        # Regenerate bundle suggestions for remaining pages
        bundled_files = set()
        for group in self.completed_groups:
            bundled_files.update(group)
        remaining_files = [f for f in self.all_files if f not in bundled_files]

        if remaining_files:
            # Regenerate suggestions for remaining files
            bundles = self.bundling_service.generate_bundle_recommendations(remaining_files)
            if bundles and len(bundles) > 0:
                if hasattr(self, 'bundle_suggestions_view') and self.bundle_suggestions_view is not None:
                    self.bundle_suggestions_view.set_bundles(bundles)
                    self.status_label.setText(f"Updated: {len(bundles)} suggestion(s) for {len(remaining_files)} remaining page(s).")
            else:
                # No more bundles, ask if user wants to process manually
                self._check_remaining_pages_after_bundles()
        else:
            # All files bundled
            self._check_remaining_pages_after_bundles()

    def _on_accept_all_high_confidence(self):
        """Accept all high confidence bundles automatically"""
        high_confidence_bundles = self.bundle_suggestions_view.get_high_confidence_bundles()
        if not high_confidence_bundles:
            show_information(
                self, "No High Confidence Bundles",
                "There are no high confidence bundles (>= 80%) to accept."
            )
            return

        reply = show_question(
            self, "Accept All High Confidence",
            f"Accept {len(high_confidence_bundles)} high confidence bundle(s)?"
        )

        if reply == QMessageBox.StandardButton.Yes:
            for bundle in high_confidence_bundles:
                file_paths = bundle.get('file_paths', [])
                if file_paths:
                    self.completed_groups.append(file_paths)
                    group_key = f"group_{len(self.completed_groups)}"
                    self.extracted_metadata[group_key] = {
                        'company': bundle.get('company'),
                        'title': bundle.get('document_type'),
                        'date': bundle.get('document_date')
                    }
            show_information(
                self, "Bundles Accepted",
                f"Accepted {len(high_confidence_bundles)} high confidence bundle(s)."
            )

            # Check if there are remaining pages to process
            self._check_remaining_pages_after_bundles()

    def _check_remaining_pages_after_bundles(self):
        """Check if there are pages left to process after accepting bundles"""
        # Get all pages that were bundled
        bundled_files = set()
        for group in self.completed_groups:
            bundled_files.update(group)

        # Check if all files were bundled
        remaining_files = [f for f in self.all_files if f not in bundled_files]

        if remaining_files:
            reply = show_question(
                self,
                "Remaining Pages",
                f"There are {len(remaining_files)} page(s) remaining that were not bundled.\n\n"
                "Would you like to process them manually?"
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Load remaining files for manual processing
                self.all_files = remaining_files
                self.current_file_index = 0
                self._on_skip_to_manual_workflow()
            else:
                # Skip to finalization
                if self.completed_groups:
                    self._transition_to_finalization()
                else:
                    self.status_label.setText("No documents to finalize.")
        else:
            # All pages bundled, go to finalization
            if self.completed_groups:
                show_information(
                    self,
                    "All Pages Bundled",
                    "All pages have been bundled! Proceeding to finalization."
                )
                self._transition_to_finalization()
            else:
                self.status_label.setText("No documents to finalize.")

    def _transition_to_finalization(self):
        """Transition to finalization step after bundle acceptance"""
        # Hide bundle suggestions view
        self.bundle_suggestions_view.setVisible(False)

        # Show three-column layout (finalization uses it)
        if hasattr(self, 'content_splitter'):
            self.content_splitter.setVisible(True)
        if hasattr(self, 'thumbnail_scroll'):
            self.thumbnail_scroll.setVisible(True)

        # Update step indicator
        self.current_step = WorkflowStep.FINALIZATION
        self.step_title_label.setText("Document Finalization")
        self.step_indicator_label.setText("Step 4 of 5")

        # Move to finalization step (this method should exist from earlier phases)
        self._show_finalization_step()

    def _show_bundle_view(self):
        """Show bundle suggestions view and hide three-column layout"""
        print("[Bundle View] Showing bundle suggestions view")

        # Show bundle suggestions view
        self.bundle_suggestions_view.setVisible(True)

        # Hide three-column layout
        if hasattr(self, 'content_splitter'):
            self.content_splitter.setVisible(False)
        if hasattr(self, 'thumbnail_scroll'):
            self.thumbnail_scroll.setVisible(False)

        # Update step indicator
        self.current_step = WorkflowStep.BUNDLE_SUGGESTIONS
        self.step_title_label.setText("AI Bundle Suggestions")
        self.step_indicator_label.setText("Step 0 of 5")

    def _show_manual_view(self):
        """Show three-column manual stitching view and hide bundle suggestions"""
        print("[Manual View] Showing three-column layout")

        # Hide bundle suggestions view
        self.bundle_suggestions_view.setVisible(False)

        # Show three-column layout
        if hasattr(self, 'content_splitter'):
            self.content_splitter.setVisible(True)
        if hasattr(self, 'thumbnail_scroll'):
            self.thumbnail_scroll.setVisible(True)

        # Update step indicator
        self.current_step = WorkflowStep.STITCHING
        self.step_title_label.setText("Document Stitching")
        self.step_indicator_label.setText("Step 1 of 5")

    def _on_skip_to_manual_workflow(self):
        """Skip bundle suggestions and go to manual stitching"""
        print("[Bundle] Skipping to manual workflow")

        # Show manual view
        self._show_manual_view()

        # Load first page for manual stitching
        if self.all_files and self.current_file_index < len(self.all_files):
            self._load_next_page_for_stitching()
        else:
            self.status_label.setText("Ready to begin stitching...")


class StartupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        self.setWindowTitle(self.app_name)

        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.processing_window = None
        self.analysis_service = None
        self.analysis_worker = None
        self.analysis_start_time = None
        self.analysis_db = AnalysisDB()  # Initialize database for stats
        self._init_ui()
    
    def _init_ui(self):
        # Set background color for better visibility
        self.setStyleSheet("background-color: #2563EB; color: white;")

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # No progress banner - analysis is managed in status window

        # Center content layout
        center_layout = QVBoxLayout()
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addLayout(center_layout, 1)

        title = QLabel(self.app_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28pt; font-weight: bold; color: white; padding: 20px;")
        center_layout.addWidget(title)

        content_layout = QHBoxLayout()
        center_layout.addLayout(content_layout)

        # Create clickable scanner container with stats
        self.scanner_container = QWidget()
        self.scanner_container.setCursor(Qt.CursorShape.PointingHandCursor)
        # Don't set max height here - we'll adjust it dynamically
        self.scanner_container.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 10px;
            }
            QWidget:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        self.scanner_container.mousePressEvent = lambda event: self.show_analysis_status()

        scanner_layout = QVBoxLayout(self.scanner_container)
        scanner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scanner_layout.setSpacing(10)  # Reduced from 15 to save space

        # Scanner GIF
        self.scanner_label = QLabel()
        self.scanner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Get absolute path to GIF from script directory
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scanner_gif_path = os.path.join(script_dir, "assets", "scanner.gif")

        if os.path.exists(scanner_gif_path):
            # Force reload by setting cache mode to not cache
            self.movie = QMovie(scanner_gif_path)
            self.movie.setCacheMode(QMovie.CacheMode.CacheNone)

            if self.movie.isValid():
                # Jump to first frame to get proper size
                self.movie.jumpToFrame(0)
                original_size = self.movie.currentImage().size()

                # If we still can't get size, use frameRect or default
                if original_size.width() <= 0 or original_size.height() <= 0:
                    original_size = self.movie.frameRect().size()

                if original_size.width() > 0 and original_size.height() > 0:
                    # Scale to fit nicely in the window (max 350x350 to leave room for progress banner)
                    max_dimension = 350
                    if original_size.width() > max_dimension or original_size.height() > max_dimension:
                        scale_factor = min(max_dimension / original_size.width(), max_dimension / original_size.height())
                        scaled_size = QSize(int(original_size.width() * scale_factor), int(original_size.height() * scale_factor))
                    else:
                        scaled_size = original_size

                    self.movie.setScaledSize(scaled_size)
                    self.scanner_label.setMovie(self.movie)
                    self.scanner_label.setFixedSize(scaled_size)
                    self.movie.setSpeed(20)  # 20% of original speed (5x slower)
                    # Play once on load, then stop
                    self.movie.frameChanged.connect(self._on_movie_frame_changed)
                    self.movie.start()
                    self._is_initial_animation = True
                    self._is_analyzing = False
                else:
                    # Fallback: use default size
                    default_size = QSize(350, 350)
                    self.movie.setScaledSize(default_size)
                    self.scanner_label.setMovie(self.movie)
                    self.scanner_label.setFixedSize(default_size)
                    # Play once on load, then stop
                    self.movie.frameChanged.connect(self._on_movie_frame_changed)
                    self.movie.start()
                    self._is_initial_animation = True
                    self._is_analyzing = False
            else:
                self.scanner_label.setText("Error loading GIF: Invalid movie format")
                self.scanner_label.setStyleSheet("color: white; font-size: 14pt;")
        else:
            self.scanner_label.setText(f"GIF not found at:\n{scanner_gif_path}")
            self.scanner_label.setStyleSheet("color: white; font-size: 12pt;")

        scanner_layout.addWidget(self.scanner_label)

        # Stats label below scanner
        self.scanner_stats_label = QLabel()
        self.scanner_stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scanner_stats_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 12pt;
                padding: 10px;
                background-color: transparent;
            }
        """)
        scanner_layout.addWidget(self.scanner_stats_label)

        # Load initial stats
        self._update_scanner_stats()

        content_layout.addWidget(self.scanner_container, 1)
            
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()

        process_button = QPushButton("Convert Scans")
        process_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        process_button.setMinimumHeight(60)
        process_button.setStyleSheet("QPushButton { background-color: #2563EB; color: white; border-radius: 5px; padding: 10px; } QPushButton:hover { background-color: #1D4ED8; }")
        process_button.clicked.connect(self.show_processing_window)
        button_layout.addWidget(process_button)

        self.extract_button = QPushButton("Convert PDFs")
        self.extract_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.extract_button.setMinimumHeight(60)
        self.extract_button.setEnabled(True)
        self.extract_button.setStyleSheet("QPushButton { background-color: #2563EB; color: white; border-radius: 5px; padding: 10px; } QPushButton:hover { background-color: #1D4ED8; }")
        self.extract_button.clicked.connect(self._process_pdfs)
        button_layout.addWidget(self.extract_button)

        settings_button = QPushButton("Change Settings")
        settings_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        settings_button.setMinimumHeight(60)
        settings_button.setStyleSheet("QPushButton { background-color: #2563EB; color: white; border-radius: 5px; padding: 10px; } QPushButton:hover { background-color: #1D4ED8; }")
        settings_button.clicked.connect(self.show_settings_window)
        button_layout.addWidget(settings_button)

        # Analyze Documents button
        analyze_button = QPushButton("🔍 Analyze Documents")
        analyze_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        analyze_button.setMinimumHeight(60)
        analyze_button.setStyleSheet("QPushButton { background-color: #059669; color: white; border-radius: 5px; padding: 10px; } QPushButton:hover { background-color: #047857; }")
        analyze_button.clicked.connect(self.manual_analyze_documents)
        button_layout.addWidget(analyze_button)

        analysis_status_button = QPushButton("📊 Analysis Status")
        analysis_status_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        analysis_status_button.setMinimumHeight(60)
        analysis_status_button.setStyleSheet("QPushButton { background-color: #2563EB; color: white; border-radius: 5px; padding: 10px; } QPushButton:hover { background-color: #1D4ED8; }")
        analysis_status_button.clicked.connect(self.show_analysis_status)
        button_layout.addWidget(analysis_status_button)

        quit_button = QPushButton("Quit")
        quit_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        quit_button.setMinimumHeight(60)
        quit_button.setStyleSheet("QPushButton { background-color: #DC2626; color: white; border-radius: 5px; padding: 10px; } QPushButton:hover { background-color: #B91C1C; }")
        quit_button.clicked.connect(self.quit_application)
        button_layout.addWidget(quit_button)

        button_layout.addStretch()
        content_layout.addLayout(button_layout)

        self.setFixedSize(800, 600)
        
        self.pdf_check_timer = QTimer(self)
        self.pdf_check_timer.timeout.connect(self._check_for_pdfs)
        self.pdf_check_timer.start(5000)

    # Removed _on_movie_state_changed method



    def showEvent(self, event):
        super().showEvent(event)
        self._check_for_pdfs()

    def _check_for_pdfs(self):
        """No longer needed - button is always enabled for manual PDF selection"""
        pass

    def _process_pdfs(self):
        """Open file dialog to select PDFs, then convert them to PNGs"""
        from PyQt6.QtWidgets import QFileDialog

        # Open file dialog to select PDF files
        pdf_files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files to Convert",
            "",
            "PDF Files (*.pdf);;All Files (*.*)"
        )

        if not pdf_files:
            # User cancelled
            return

        # Open ConvertPDFsWindow with selected files
        convert_pdfs_window = ConvertPDFsWindow(pdf_files=pdf_files)
        convert_pdfs_window.show()
        convert_pdfs_window.exec()

    def show_processing_window(self):
        if not self.processing_window or not self.processing_window.isVisible():
            self.processing_window = ConvertImagesWindow()
            self.processing_window.processing_finished.connect(self.on_processing_finished)
        self.hide()
        self.processing_window.show()

    def show_settings_window(self):
        settings_window = EnhancedSettingsWindow(self)
        settings_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        settings_window.setWindowModality(Qt.WindowModality.ApplicationModal)
        settings_window.show()

        # Keep reference to prevent garbage collection
        self._settings_window = settings_window

    def manual_analyze_documents(self):
        """Manually trigger document analysis - opens status window with auto-start"""
        # Initialize analysis service if not already done
        if not hasattr(self, 'analysis_service') or self.analysis_service is None:
            from config_manager import ConfigManager
            from analysis_db import AnalysisDB
            from metadata_db import MetadataDB
            from analysis_service import AnalysisService

            config_manager = ConfigManager()
            analysis_db = AnalysisDB()
            metadata_db = MetadataDB()
            self.analysis_service = AnalysisService(config_manager, analysis_db, metadata_db)

        # Open status window with auto-start
        status_window = AnalysisStatusWindow(
            parent=self,
            analysis_service=self.analysis_service,
            config_manager=self.config_manager,
            auto_start_analysis=True
        )
        status_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        status_window.setModal(False)
        status_window.show()

        # Keep reference to prevent garbage collection
        self._analysis_status_window = status_window

    def show_analysis_status(self):
        """Show the Analysis Status window"""
        # Initialize analysis service if needed
        if not hasattr(self, 'analysis_service') or self.analysis_service is None:
            from config_manager import ConfigManager
            from analysis_db import AnalysisDB
            from metadata_db import MetadataDB
            from analysis_service import AnalysisService

            config_manager = ConfigManager()
            analysis_db = AnalysisDB()
            metadata_db = MetadataDB()
            self.analysis_service = AnalysisService(config_manager, analysis_db, metadata_db)

        status_window = AnalysisStatusWindow(
            parent=self,
            analysis_service=self.analysis_service,
            config_manager=self.config_manager,
            auto_start_analysis=False
        )
        status_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        status_window.setModal(False)
        status_window.show()

        # Keep reference to prevent garbage collection
        self._analysis_status_window = status_window

    def quit_application(self):
        """Handle Quit button click with confirmation"""
        reply = show_question(
            self,
            'Quit Application',
            'Are you sure you want to quit?'
        )

        if reply == QMessageBox.StandardButton.Yes:
            QApplication.quit()

    def on_processing_finished(self):
        if self.processing_window:
            self.processing_window = None
        self.show()

    def _on_movie_frame_changed(self, frame_number):
        """Handle movie frame changes to control initial vs continuous animation"""
        if hasattr(self, '_is_initial_animation') and self._is_initial_animation:
            # Check if we've looped back to frame 0 (completed one cycle)
            if frame_number == 0 and hasattr(self, '_movie_started'):
                # Initial animation complete, stop at first frame
                self.movie.stop()
                self.movie.jumpToFrame(0)
                self._is_initial_animation = False
            else:
                # Mark that movie has started (not first frame anymore)
                self._movie_started = True

    def _update_scanner_animation(self, is_analyzing: bool):
        """
        Control scanner GIF animation based on analysis state.

        Args:
            is_analyzing: True to start animation (continuous loop), False to stop
        """
        if hasattr(self, 'movie') and self.movie.isValid():
            self._is_analyzing = is_analyzing
            self._is_initial_animation = False  # Disable initial animation mode
            self._movie_started = False
            if is_analyzing:
                self.movie.start()  # Continuous loop while analyzing
            else:
                self.movie.stop()
                self.movie.jumpToFrame(0)  # Show first frame when not analyzing

    def _update_scanner_stats(self):
        """
        Update the stats label below the scanner GIF.
        Shows static database statistics when idle.
        """
        if not hasattr(self, 'scanner_stats_label'):
            return

        try:
            db_stats = self.analysis_db.get_analysis_statistics()
            total_files = db_stats.get('total_files', 0)
            cached_files = db_stats.get('cached_files', 0)
            failed_files = db_stats.get('failed_files', 0)

            # Get last analysis time from recent runs
            recent_runs = self.analysis_db.get_recent_runs(limit=1)
            if recent_runs:
                last_run = recent_runs[0]
                last_time_str = self._format_relative_time(last_run['timestamp'])
            else:
                last_time_str = "Never"

            # Determine status based on database state
            if total_files == 0:
                status_color = "#6B7280"  # Gray
                status_text = "Status: No files analyzed"
            elif failed_files > 0:
                status_color = "#DC2626"  # Red
                status_text = f"Status: Complete ({failed_files} errors)"
            else:
                status_color = "#059669"  # Green
                status_text = "Status: Idle"

        except Exception as e:
            # Fallback if database query fails
            total_files = 0
            cached_files = 0
            failed_files = 0
            last_time_str = "Unknown"
            status_color = "#6B7280"
            status_text = "Status: Unknown"

        # Calculate cache percentage
        cache_pct = int((cached_files / total_files * 100)) if total_files > 0 else 0

        # Format numbers with commas
        total_str = f"{total_files:,}"
        cached_str = f"{cached_files:,}"
        errors_str = f"{failed_files:,}"

        # Build status HTML
        html = f"""
        <div style="text-align: center;">
            <div style="color: {status_color}; font-weight: bold; margin-bottom: 8px;">
                {status_text}
            </div>
            <div style="color: white; font-size: 11pt;">
                {total_str} files | {cached_str} cached ({cache_pct}%) | {errors_str} errors
            </div>
            <div style="color: rgba(255, 255, 255, 0.8); font-size: 10pt; margin-top: 5px;">
                Last analysis: {last_time_str}
            </div>
        </div>
        """

        self.scanner_stats_label.setText(html)

    def _format_relative_time(self, iso_timestamp: str) -> str:
        """
        Format ISO timestamp as relative time (e.g., "2 hours ago").

        Args:
            iso_timestamp: ISO format timestamp string

        Returns:
            Relative time string
        """
        try:
            from datetime import datetime, timedelta

            # Parse ISO timestamp
            dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()

            # Calculate difference
            diff = now - dt

            # Format based on duration
            if diff.total_seconds() < 60:
                return "Just now"
            elif diff.total_seconds() < 3600:
                minutes = int(diff.total_seconds() / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif diff.total_seconds() < 86400:
                hours = int(diff.total_seconds() / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif diff.days < 30:
                return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
            else:
                months = diff.days // 30
                return f"{months} month{'s' if months != 1 else ''} ago"
        except Exception:
            return "Unknown"

    def check_for_unanalyzed_files(self, analysis_service):
        """Check for unanalyzed files and show welcome dialog if needed"""
        from analysis_db import AnalysisDB
        import glob

        def log(msg):
            with open("app.log", "a") as f:
                f.write(f"{msg}\n")
                f.flush()  # Ensure log is written immediately

        analysis_db = AnalysisDB()

        # Get scan folder
        scan_folder = self.config_manager.get_setting("DocumentProcessing", "scan_folder")
        log(f"[DEBUG] Scan folder: {scan_folder}")
        if not scan_folder or not os.path.exists(scan_folder):
            log(f"[DEBUG] Scan folder doesn't exist or not set")
            analysis_db.close()
            return

        # Count PNG/JPG files (use set to avoid duplicates)
        image_files_set = set()
        for ext in ['*.png', '*.PNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG']:
            image_files_set.update(glob.glob(os.path.join(scan_folder, ext)))
        image_files = list(image_files_set)

        total_files = len(image_files)
        log(f"[DEBUG] Total files found: {total_files}")
        if total_files == 0:
            log(f"[DEBUG] No files found, returning")
            analysis_db.close()
            return

        # Count analyzed files
        analyzed_count = 0
        for image_path in image_files:
            if analysis_db.get_analysis(image_path):
                analyzed_count += 1

        analysis_db.close()

        unanalyzed_count = total_files - analyzed_count
        log(f"[DEBUG] Analyzed: {analyzed_count}, Unanalyzed: {unanalyzed_count}")

        # Show welcome dialog if many unanalyzed files
        if unanalyzed_count > 0:
            log(f"[DEBUG] Showing dialog for {unanalyzed_count} unanalyzed files")
            log(f"[DEBUG] Window visible: {self.isVisible()}, Window active: {self.isActiveWindow()}")
            try:
                log(f"[DEBUG] ENTERED TRY BLOCK")
                # Estimate time (rough estimate: 3 seconds per page)
                estimated_minutes = (unanalyzed_count * 3) // 60
                time_estimate = f"{estimated_minutes} minutes" if estimated_minutes > 0 else "less than a minute"

                log(f"[DEBUG] Calling activateWindow()")
                # Ensure window is active and has focus before showing dialog
                self.activateWindow()

                log(f"[DEBUG] Calling raise_()")
                self.raise_()

                log(f"[DEBUG] About to call show_question()")
                reply = show_question(
                    self,
                    'Analyze Documents?',
                    f'Found {unanalyzed_count} unanalyzed pages in your scan folder.\n\n'
                    f'Would you like to analyze them now?\n\n'
                    f'Estimated time: {time_estimate}\n\n'
                    f'Analysis enables AI-powered bundle suggestions and automatic document organization.'
                )
                log(f"[DEBUG] Dialog closed, reply: {reply}")

                if reply == QMessageBox.StandardButton.Yes:
                    log(f"[DEBUG] User clicked Yes, starting analysis")
                    # Open status window with auto-start
                    status_window = AnalysisStatusWindow(
                        parent=self,
                        analysis_service=analysis_service,
                        config_manager=self.config_manager,
                        auto_start_analysis=True
                    )
                    status_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                    status_window.setModal(False)
                    status_window.show()
                    self._analysis_status_window = status_window
                else:
                    log(f"[DEBUG] User clicked No, skipping analysis")
            except Exception as e:
                log(f"[ERROR] Exception showing dialog: {e}")
                import traceback
                log(f"[ERROR] Traceback: {traceback.format_exc()}")



class AnalysisWorker(QThread):
    """Worker thread for running analysis in background"""
    progress = pyqtSignal(str, int, int, dict)
    finished = pyqtSignal(dict)

    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self._cancelled = False
        self.current_stats = {
            'analyzed': 0,
            'cached': 0,
            'errors': 0,
            'total_files': 0
        }

    def run(self):
        """Run analysis in background thread"""
        try:
            # Create new database connections in this thread to avoid SQLite thread errors
            from analysis_db import AnalysisDB
            from metadata_db import MetadataDB
            from analysis_service import AnalysisService

            analysis_db = AnalysisDB()
            metadata_db = MetadataDB()
            analysis_service = AnalysisService(self.config_manager, analysis_db, metadata_db)

            def progress_callback(status_text, current, total):
                if self._cancelled:
                    raise InterruptedError("Analysis cancelled by user")
                self.progress.emit(status_text, current, total, self.current_stats)

            stats = analysis_service.scan_all_directories(
                progress_callback=progress_callback,
                incremental=True
            )

            # Close database connections
            analysis_db.close()
            metadata_db.close()

            self.current_stats.update(stats)
            self.finished.emit(stats)

        except InterruptedError:
            self.finished.emit({
                'total_files': self.current_stats.get('total_files', 0),
                'analyzed': self.current_stats.get('analyzed', 0),
                'cached': self.current_stats.get('cached', 0),
                'errors': self.current_stats.get('errors', 0),
                'message': 'Analysis cancelled'
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit({
                'total_files': 0,
                'analyzed': 0,
                'cached': 0,
                'errors': 1,
                'message': f'Analysis error: {str(e)}'
            })

    def cancel(self):
        """Cancel the analysis"""
        self._cancelled = True


class SpecificFilesAnalysisWorker(QThread):
    """Worker thread for analyzing specific files in background"""
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(dict)

    def __init__(self, analysis_service, file_paths):
        super().__init__()
        self.analysis_service = analysis_service
        self.file_paths = file_paths
        self._cancelled = False

    def run(self):
        """Run analysis for specific files in background thread"""
        try:
            def progress_callback(status_text, current, total):
                if self._cancelled:
                    raise InterruptedError("Analysis cancelled by user")
                self.progress.emit(status_text, current, total)

            stats = self.analysis_service.analyze_specific_files(
                file_paths=self.file_paths,
                force_reanalysis=False,
                progress_callback=progress_callback
            )

            self.finished.emit(stats)

        except InterruptedError:
            self.finished.emit({
                'total_files': len(self.file_paths),
                'analyzed': 0,
                'cached': 0,
                'errors': 0,
                'message': 'Analysis cancelled'
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit({
                'total_files': len(self.file_paths),
                'analyzed': 0,
                'cached': 0,
                'errors': 1,
                'message': f'Analysis error: {str(e)}'
            })

    def cancel(self):
        """Cancel the analysis"""
        self._cancelled = True


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = StartupWindow()
    window.show()
    sys.exit(app.exec())
