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

try:
    import fitz
except ImportError:
    print("Error: PyMuPDF (fitz) is not installed. Please run 'pip install PyMuPDF'.")
    sys.exit(1)

from config_manager import ConfigManager
from ollama_service import OllamaService
from file_processor import FileProcessor
from field_history import FieldHistory
from metadata_db import MetadataDB
from settings_window_enhanced import EnhancedSettingsWindow
from bundle_widgets import BundleSuggestionsView
from bundling_service import BundlingService
from analysis_db import AnalysisDB

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

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        timeout = float(self.config_manager.get_setting('Ollama', 'timeout', '300'))
        self.ollama_service = OllamaService(
            base_url=self.config_manager.get_setting('Ollama', 'base_url'),
            timeout=timeout
        )
        
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        self.setWindowTitle(f"{self.app_name} - Settings")
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setMinimumWidth(600)
        self._init_ui()
        self._load_ollama_models()

    def _init_ui(self):
        layout = QGridLayout(self)

        # Apply stylesheet for proper control backgrounds
        self.setStyleSheet("""
            QLineEdit, QComboBox, QPlainTextEdit {
                background-color: white;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 5px;
                color: black;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border: 2px solid #0078D7;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #666;
                margin-right: 5px;
            }
        """)

        layout.addWidget(QLabel("Default Ollama Model:"), 0, 0)
        model_layout = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        model_layout.addWidget(self.model_combo)
        
        self.model_details_button = QPushButton("Details")
        self.model_details_button.clicked.connect(self._open_model_details)
        model_layout.addWidget(self.model_details_button)

        self.download_model_button = QPushButton("Download")
        self.download_model_button.clicked.connect(self._pull_selected_model)
        self.download_model_button.setEnabled(False)
        model_layout.addWidget(self.download_model_button)

        self.delete_model_button = QPushButton("Delete")
        self.delete_model_button.clicked.connect(self._delete_selected_model)
        self.delete_model_button.setEnabled(False)
        self.delete_model_button.setVisible(False)
        self.delete_model_button.setStyleSheet("QPushButton { background-color: #D13438; color: white; }")
        model_layout.addWidget(self.delete_model_button)

        layout.addLayout(model_layout, 0, 1)

        self.model_combo.currentIndexChanged.connect(self._on_ollama_model_selected)

        layout.addWidget(QLabel("Scan Folder:"), 1, 0)
        folder_layout = QHBoxLayout()
        self.scan_folder_edit = QLineEdit(self.config_manager.get_setting("DocumentProcessing", "scan_folder"))
        folder_layout.addWidget(self.scan_folder_edit)

        # Browse button with folder icon
        browse_button = QPushButton()
        browse_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        browse_button.setToolTip("Browse for folder")
        browse_button.clicked.connect(self._open_folder_picker)
        folder_layout.addWidget(browse_button)

        # Open folder in explorer button
        open_folder_button = QPushButton()
        open_folder_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowRight))
        open_folder_button.setToolTip("Open folder in Explorer")
        open_folder_button.clicked.connect(self._open_scan_folder_in_explorer)
        folder_layout.addWidget(open_folder_button)

        layout.addLayout(folder_layout, 1, 1)

        layout.addWidget(QLabel("Title Keywords (comma-separated):"), 2, 0)
        self.keywords_edit = QLineEdit(self.config_manager.get_setting("DocumentProcessing", "title_keywords"))
        layout.addWidget(self.keywords_edit, 2, 1)

        # Document Pages Prompt (for validation)
        layout.addWidget(QLabel("Document Pages Prompt:"), 3, 0, Qt.AlignmentFlag.AlignTop)
        self.pages_prompt_edit = ExpandablePromptEdit()
        pages_prompt_default = """You are an expert document analyst. Examine the provided images. Determine if all pages belong to the *same continuous physical document*. Respond ONLY with 'YES' if all pages are from the same document, or 'NO' if they are not. Do not add any other text or explanation."""
        pages_prompt = self.config_manager.get_setting("Prompts", "document_pages", pages_prompt_default)
        self.pages_prompt_edit.setPlainText(pages_prompt)
        layout.addWidget(self.pages_prompt_edit, 3, 1)

        # Document Metadata Prompt (for extraction)
        layout.addWidget(QLabel("Document Metadata Prompt:"), 4, 0, Qt.AlignmentFlag.AlignTop)
        self.metadata_prompt_edit = ExpandablePromptEdit()
        metadata_prompt_default = """You are an expert at extracting key information from scanned documents.
Analyze the provided images to identify the following:
1. **Source Company:** The name of the organization that issued the document. Look at headers, footers, logos, or return addresses.
2. **Document Title:** The main purpose or type of the document (e.g., Invoice, Statement, Bill, Receipt, Report, Contract, Agreement).
3. **Relevant Date:** The primary date associated with the document (e.g., issue date, statement date, invoice date, contract date). Prioritize the most prominent and relevant date.

Respond ONLY in JSON format. Your JSON should contain three keys: 'company', 'title', and 'date'.
If any information cannot be found, use null for its value.

Example: { "company": "Acme Corp", "title": "Invoice", "date": "2023-10-26" }"""
        metadata_prompt = self.config_manager.get_setting("Prompts", "document_metadata", metadata_prompt_default)
        self.metadata_prompt_edit.setPlainText(metadata_prompt)
        layout.addWidget(self.metadata_prompt_edit, 4, 1)

        # Auto-Approval Settings
        layout.addWidget(QLabel("Enable Automatic Approvals:"), 5, 0)
        self.auto_approval_checkbox = QCheckBox()
        auto_approval_enabled = self.config_manager.get_setting("AutoApproval", "enable_automatic_approvals", "false")
        self.auto_approval_checkbox.setChecked(auto_approval_enabled.lower() == "true")
        self.auto_approval_checkbox.stateChanged.connect(self._on_auto_approval_toggled)
        layout.addWidget(self.auto_approval_checkbox, 5, 1)

        self.approval_delay_label = QLabel("Automatic Approval Delay (seconds):")
        layout.addWidget(self.approval_delay_label, 6, 0)
        self.approval_delay_spinbox = QSpinBox()
        self.approval_delay_spinbox.setMinimum(3)
        self.approval_delay_spinbox.setMaximum(60)
        self.approval_delay_spinbox.setValue(int(self.config_manager.get_setting("AutoApproval", "automatic_approval_delay", "5")))
        layout.addWidget(self.approval_delay_spinbox, 6, 1)

        # Set initial visibility based on checkbox state
        is_checked = self.auto_approval_checkbox.isChecked()
        self.approval_delay_label.setVisible(is_checked)
        self.approval_delay_spinbox.setVisible(is_checked)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box, 7, 0, 1, 2)

    def _load_ollama_models(self):
        self.model_combo.clear()
        self.model_combo.addItem("Select a vision model...", userData=None)

        try:
            # Get local models and filter for vision models only
            local_models_data = self.ollama_service.list_models()

            # Debug: Check structure of returned models
            if local_models_data and len(local_models_data) > 0:
                print(f"DEBUG: First model structure: {local_models_data[0]}")
                print(f"DEBUG: Model keys: {local_models_data[0].keys() if isinstance(local_models_data[0], dict) else 'Not a dict'}")

            # Extract model names (handle different possible structures)
            local_vision_models = set()
            for m in local_models_data:
                # Try different possible key names
                model_name = m.get('name') or m.get('model') or str(m)
                if model_name and self.ollama_service.is_vision_model(model_name):
                    local_vision_models.add(model_name)

            # Start with local vision models
            all_vision_models = list(local_vision_models)

            # Add suggested vision models that aren't already local
            # Note: Ollama uses inconsistent naming (some with hyphens, some without)
            suggested_vision_models = [
                "llava:latest", "llava:13b", "llava:7b",
                "llava-llama3:latest", "llava-phi3:latest",
                "qwen3-vl:latest", "qwen2.5vl:latest", "qwen2-vl:latest",  # Fixed: qwen2.5vl has NO hyphen
                "moondream:latest", "bakllava:latest",
                "cogvlm:latest", "phi3-vision:latest",
                "minicpm-v:latest", "internvl:latest"
            ]
            for model in suggested_vision_models:
                if model not in all_vision_models:
                    all_vision_models.append(model)

            # Populate dropdown
            self.model_combo.blockSignals(True)
            for model_name in sorted(all_vision_models):
                is_local = model_name in local_vision_models
                display_text = model_name if is_local else f"{model_name} (not downloaded)"
                self.model_combo.addItem(display_text, userData={'local': is_local, 'name': model_name})
            self.model_combo.blockSignals(False)

            # Select current model from settings if it's a vision model
            current_model = self.config_manager.get_setting("Ollama", "model")
            if current_model and self.ollama_service.is_vision_model(current_model):
                for i in range(self.model_combo.count()):
                    if self.model_combo.itemData(i) and self.model_combo.itemData(i)['name'] == current_model:
                        self.model_combo.setCurrentIndex(i)
                        break
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Models", str(e))

        self._on_ollama_model_selected()

    def _on_ollama_model_selected(self):
        selected_data = self.model_combo.currentData()
        if selected_data:
            self.model_details_button.setEnabled(True)
            is_local = selected_data['local']

            # Show download button for non-local models, delete button for local models
            if is_local:
                self.download_model_button.setVisible(False)
                self.download_model_button.setEnabled(False)
                self.delete_model_button.setVisible(True)
                self.delete_model_button.setEnabled(True)
            else:
                self.download_model_button.setVisible(True)
                self.download_model_button.setEnabled(True)
                self.delete_model_button.setVisible(False)
                self.delete_model_button.setEnabled(False)
        else:
            self.model_details_button.setEnabled(False)
            self.download_model_button.setEnabled(False)
            self.download_model_button.setVisible(True)
            self.delete_model_button.setEnabled(False)
            self.delete_model_button.setVisible(False)

    def _set_controls_enabled(self, enabled):
        """Enable or disable all controls during download with visual feedback"""
        # Define opacity for disabled state
        opacity = 1.0 if enabled else 0.5
        disabled_style = "" if enabled else "QWidget:disabled { color: #888; background-color: #f0f0f0; }"

        controls = [
            self.model_combo,
            self.model_details_button,
            self.download_model_button,
            self.delete_model_button,
            self.scan_folder_edit,
            self.keywords_edit,
            self.pages_prompt_edit,
            self.metadata_prompt_edit
        ]

        for control in controls:
            control.setEnabled(enabled)
            # Apply visual styling
            if hasattr(control, 'setStyleSheet'):
                current_style = control.styleSheet()
                # Remove any previous disabled styling
                current_style = current_style.replace("QWidget:disabled { color: #888; background-color: #f0f0f0; }", "")
                if not enabled:
                    control.setStyleSheet(current_style + disabled_style)
                else:
                    control.setStyleSheet(current_style)

            # Set opacity for visual feedback
            if hasattr(control, 'setGraphicsEffect'):
                effect = QGraphicsOpacityEffect()
                effect.setOpacity(opacity)
                control.setGraphicsEffect(effect if not enabled else None)

        # Find and disable browse buttons
        for button in self.findChildren(QPushButton):
            if button.toolTip() in ["Browse for folder", "Open folder in Explorer"]:
                button.setEnabled(enabled)
                if hasattr(button, 'setGraphicsEffect'):
                    effect = QGraphicsOpacityEffect()
                    effect.setOpacity(opacity)
                    button.setGraphicsEffect(effect if not enabled else None)

    def _pull_selected_model(self):
        selected_data = self.model_combo.currentData()
        if not selected_data or selected_data['local']:
            return

        model_name = selected_data['name']

        # Disable all controls during download
        self._set_controls_enabled(False)

        # Create and show progress bar in the settings window
        from PyQt6.QtWidgets import QProgressBar, QLabel
        if not hasattr(self, 'download_progress_bar'):
            # Add progress bar to layout
            layout = self.layout()
            self.download_progress_label = QLabel(f"Downloading {model_name}...")
            self.download_progress_bar = QProgressBar()
            self.download_progress_bar.setMinimum(0)
            self.download_progress_bar.setMaximum(0)  # Indeterminate
            self.download_cancel_button = QPushButton("Cancel Download")
            self.download_cancel_button.clicked.connect(self._cancel_model_download)

            # Insert before button box (which is at row 5)
            row_count = layout.rowCount()
            layout.addWidget(self.download_progress_label, row_count, 0, 1, 2)
            layout.addWidget(self.download_progress_bar, row_count + 1, 0, 1, 2)
            layout.addWidget(self.download_cancel_button, row_count + 2, 0, 1, 2)
        else:
            self.download_progress_label.setText(f"Downloading {model_name}...")

        self.download_progress_label.setVisible(True)
        self.download_progress_bar.setVisible(True)
        self.download_cancel_button.setVisible(True)

        self.worker = OllamaWorker(self.ollama_service.pull_model, model_name)
        self.worker.finished.connect(self._on_model_pull_finished)
        self.worker.start()

    def _cancel_model_download(self):
        """Cancel the ongoing model download"""
        if hasattr(self, 'worker') and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Cancel Download",
                "Are you sure you want to cancel the download?\n\nPartial download will be discarded.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.worker.terminate()
                self.worker.wait()

                # Hide progress controls
                if hasattr(self, 'download_progress_label'):
                    self.download_progress_label.setVisible(False)
                    self.download_progress_bar.setVisible(False)
                    self.download_cancel_button.setVisible(False)

                # Re-enable controls
                self._set_controls_enabled(True)
                self._on_ollama_model_selected()  # Restore button states

                QMessageBox.information(self, "Download Cancelled", "Model download was cancelled.")

    def _on_model_pull_finished(self, result):
        # Hide progress controls
        if hasattr(self, 'download_progress_label'):
            self.download_progress_label.setVisible(False)
            self.download_progress_bar.setVisible(False)
            self.download_cancel_button.setVisible(False)

        # Re-enable all controls
        self._set_controls_enabled(True)

        if isinstance(result, Exception):
            QMessageBox.critical(self, "Model Download Error",
                f"Failed to download model.\n\nError: {result}\n\n"
                f"Troubleshooting:\n"
                f"• Check your internet connection\n"
                f"• Verify Ollama service is running\n"
                f"• Try downloading manually: ollama pull <model-name>"
            )
        else:
            QMessageBox.information(self, "Download Complete",
                f"Model downloaded successfully!\n\n"
                f"The model is now available for use."
            )
            self._load_ollama_models()

        # Restore button states
        self._on_ollama_model_selected()

    def _open_model_details(self):
        selected_data = self.model_combo.currentData()
        if selected_data and selected_data['name']:
            model_name_only = selected_data['name'].split(':')[0]
            QDesktopServices.openUrl(QUrl(f"https://ollama.com/library/{model_name_only}"))

    def _delete_selected_model(self):
        """Delete the selected model from local Ollama installation"""
        selected_data = self.model_combo.currentData()
        if not selected_data or not selected_data['local']:
            return

        model_name = selected_data['name']

        # Confirm deletion
        reply = QMessageBox.question(
            self, "Delete Model",
            f"Are you sure you want to delete the model '{model_name}'?\n\n"
            f"This will remove the model from your local Ollama installation.\n"
            f"You can download it again later if needed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Call Ollama API to delete the model
                url = f"{self.ollama_service.base_url}/api/delete"
                payload = {"name": model_name}
                response = self.ollama_service.session.delete(url, json=payload)
                response.raise_for_status()

                QMessageBox.information(
                    self, "Model Deleted",
                    f"Model '{model_name}' has been deleted successfully."
                )

                # Reload model list
                self._load_ollama_models()

            except Exception as e:
                QMessageBox.critical(
                    self, "Delete Error",
                    f"Failed to delete model.\n\nError: {e}\n\n"
                    f"You can also delete it manually using:\n"
                    f"ollama rm {model_name}"
                )

    def _open_scan_folder_in_explorer(self):
        """Open the scan folder in Windows Explorer"""
        folder_path = self.scan_folder_edit.text()

        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(
                self, "Invalid Folder",
                "The specified folder does not exist.\n\n"
                "Please select a valid folder first."
            )
            return

        try:
            # Open folder in Windows Explorer
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            elif os.name == 'posix':  # macOS/Linux
                import subprocess
                if sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', folder_path])
                else:  # Linux
                    subprocess.run(['xdg-open', folder_path])
        except Exception as e:
            QMessageBox.critical(
                self, "Error Opening Folder",
                f"Failed to open folder in Explorer.\n\nError: {e}"
            )

    def _open_folder_picker(self):
        current_path = self.scan_folder_edit.text()
        if not os.path.isdir(current_path):
            current_path = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Scan Folder", current_path)
        if directory:
            self.scan_folder_edit.setText(directory)

    def _on_auto_approval_toggled(self, state):
        """Show/hide approval delay label and spinbox based on checkbox state"""
        is_checked = state == Qt.CheckState.Checked.value
        self.approval_delay_label.setVisible(is_checked)
        self.approval_delay_spinbox.setVisible(is_checked)

    def save_settings(self):
        self.config_manager.set_setting("Ollama", "model", self.model_combo.currentText())
        self.config_manager.set_setting("DocumentProcessing", "scan_folder", self.scan_folder_edit.text())
        self.config_manager.set_setting("DocumentProcessing", "title_keywords", self.keywords_edit.text())

        # Save custom prompts
        self.config_manager.set_setting("Prompts", "document_pages", self.pages_prompt_edit.toPlainText())
        self.config_manager.set_setting("Prompts", "document_metadata", self.metadata_prompt_edit.toPlainText())

        # Save auto-approval settings
        self.config_manager.set_setting("AutoApproval", "enable_automatic_approvals", "true" if self.auto_approval_checkbox.isChecked() else "false")
        self.config_manager.set_setting("AutoApproval", "automatic_approval_delay", str(self.approval_delay_spinbox.value()))

        QMessageBox.information(self, "Settings Saved", "Your settings have been saved.")
        self.accept()

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

    def __init__(self):
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
        self.pdf_files = []
        self.selected_pdfs = []
        self.extraction_results = []

        self._init_ui()
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
        QMessageBox.information(
            self,
            "Open Convert Scans",
            "Close this window and click 'Convert Scans' to process the extracted images."
        )
        self.close()

    def _go_next(self):
        """Navigate to next step"""
        if self.current_step == 1:
            if not self.selected_pdfs:
                QMessageBox.warning(self, "No PDFs Selected", "Please select at least one PDF to extract.")
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
        self.field_history = FieldHistory()
        self.metadata_db = MetadataDB()  # Initialize metadata database for caching

        # Phase 7: Bundle suggestion services
        self.analysis_db = AnalysisDB()
        self.bundling_service = BundlingService(self.analysis_db)

        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanLLM")
        self.setWindowTitle(f"{self.app_name} - Convert Images")
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        width = int(self.config_manager.get_setting('GUI', 'window_width', '1024'))
        height = int(self.config_manager.get_setting('GUI', 'window_height', '768'))
        self.setGeometry(100, 100, width, height)

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
        self.step_title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #0078D7;")
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
        self.content_layout = QHBoxLayout()

        # LEFT PANEL (changes per step)
        self.left_panel = QWidget()
        self.left_panel_layout = QVBoxLayout(self.left_panel)
        self.left_panel_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.addWidget(self.left_panel)

        # CENTER: Large Page Preview with Zoom Controls
        # Create a container for the preview and zoom buttons
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        self.large_preview_label = QLabel()
        self.large_preview_label.setFrameShape(QFrame.Shape.Box)
        self.large_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.large_preview_label.setStyleSheet("background-color: #f0f0f0; border: 2px solid #ccc;")
        self.large_preview_label.setMinimumSize(400, 500)
        self.large_preview_label.setScaledContents(False)

        # Install event filter for mouse wheel zoom
        self.large_preview_label.installEventFilter(self)
        self.large_preview_label.setMouseTracking(True)

        preview_layout.addWidget(self.large_preview_label)

        # Create zoom control buttons (overlaid on top-right)
        self._setup_zoom_controls()

        self.content_layout.addWidget(preview_container, stretch=1)

        # RIGHT PANEL (changes per step)
        self.right_panel = QWidget()
        self.right_panel_layout = QVBoxLayout(self.right_panel)
        self.right_panel_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.addWidget(self.right_panel)

        self.main_layout.addLayout(self.content_layout)

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
        """Setup keyboard shortcuts for zoom and other actions (Phase 8)"""
        from PyQt6.QtGui import QShortcut, QKeySequence

        # Zoom shortcuts
        zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        zoom_in_shortcut.activated.connect(self._zoom_in)

        zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        zoom_out_shortcut.activated.connect(self._zoom_out)

        zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        zoom_reset_shortcut.activated.connect(lambda: self._set_zoom_mode_to_fit_window())

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
            QMessageBox.warning(
                self,
                "Rotation Failed",
                f"Could not save rotation: {e}"
            )
            print(f"[Rotation] Error: {e}")
            import traceback
            traceback.print_exc()

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
            "font-size: 72pt; color: #0078D7; background: transparent;"
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
        """Step 1: Document Stitching - page-by-page inclusion with spinner and buttons"""
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

        # LEFT PANEL: Hide it for Step 1
        self.left_panel.setVisible(False)

        # RIGHT PANEL: Show for buttons
        self.right_panel.setVisible(True)

        # RIGHT PANEL: Dynamic Include/Exclude/Abort buttons
        self.right_panel.setFixedWidth(200)

        button_container = QWidget()
        button_layout = QVBoxLayout(button_container)
        button_layout.addStretch(1)

        # Cancel Request button (cancels current Ollama operation) - TOP POSITION
        self.cancel_request_button = QPushButton("Cancel\nRequest")
        self.cancel_request_button.setStyleSheet(
            "QPushButton { background-color: #FFA500; color: white; "
            "font-size: 10pt; padding: 10px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #FF8C00; }"
        )
        self.cancel_request_button.clicked.connect(self._on_cancel_ollama_step1)
        self.cancel_request_button.setVisible(False)
        button_layout.addWidget(self.cancel_request_button)

        button_layout.addSpacing(10)

        # Approve button (ends stitching and moves to Step 2)
        self.exclude_button = QPushButton("Approve")
        self.exclude_button.setStyleSheet(
            "QPushButton { background-color: #0078D7; color: white; "
            "font-size: 11pt; padding: 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #005A9E; }"
        )
        self.exclude_button.clicked.connect(self._on_finish_group)
        self.exclude_button.setVisible(False)
        button_layout.addWidget(self.exclude_button)

        button_layout.addSpacing(10)

        # Import Scans button (initially shown)
        self.start_scan_button = QPushButton("Import Scans")
        self.start_scan_button.setStyleSheet(
            "QPushButton { background-color: #0078D7; color: white; "
            "font-size: 13pt; padding: 20px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #005A9E; }"
        )
        self.start_scan_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.start_scan_button.clicked.connect(self._scan_and_group)
        button_layout.addWidget(self.start_scan_button)

        button_layout.addSpacing(10)

        # Include button (hidden initially, dynamically shown/hidden)
        self.include_button = QPushButton("Include")
        self.include_button.setStyleSheet(
            "QPushButton { background-color: #107C10; color: white; "
            "font-size: 12pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #0e6b0e; }"
        )
        self.include_button.clicked.connect(self._on_include_current_page)
        self.include_button.setVisible(False)
        button_layout.addWidget(self.include_button)

        button_layout.addSpacing(10)

        # Exclude button (remove current page from group and mark as excluded)
        self.exclude_page_button = QPushButton("Exclude")
        self.exclude_page_button.setStyleSheet(
            "QPushButton { background-color: #D13438; color: white; "
            "font-size: 11pt; padding: 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #a02a2e; }"
        )
        self.exclude_page_button.clicked.connect(self._on_exclude_current_page)
        self.exclude_page_button.setVisible(False)
        button_layout.addWidget(self.exclude_page_button)

        button_layout.addSpacing(10)

        # Abort button (gray, exits entire workflow)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setStyleSheet(
            "QPushButton { background-color: #8A8A8A; color: white; "
            "font-size: 11pt; padding: 12px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #6A6A6A; }"
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
        companies = self.field_history.get_companies()
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
        titles = self.field_history.get_titles()
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
            "QPushButton { background-color: #0078D7; color: white; "
            "font-size: 12pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #005A9E; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        self.continue_button.clicked.connect(self._on_continue_to_step3)
        self.continue_button.setEnabled(False)
        button_layout.addWidget(self.continue_button)

        button_layout.addSpacing(10)

        # Cancel Request button (stops Ollama, allows manual completion)
        self.cancel_ollama_button = QPushButton("Cancel\nRequest")
        self.cancel_ollama_button.setStyleSheet(
            "QPushButton { background-color: #8A8A8A; color: white; "
            "font-size: 10pt; padding: 12px; border-radius: 5px; text-align: center; }"
            "QPushButton:hover { background-color: #6A6A6A; }"
        )
        self.cancel_ollama_button.clicked.connect(self._on_cancel_ollama)
        self.cancel_ollama_button.setEnabled(False)
        button_layout.addWidget(self.cancel_ollama_button)

        button_layout.addSpacing(10)

        # Close Window button (return to main window)
        self.abort_button = QPushButton("Close\nWindow")
        self.abort_button.setStyleSheet(
            "QPushButton { background-color: #D13438; color: white; "
            "font-size: 10pt; padding: 12px; border-radius: 5px; text-align: center; }"
            "QPushButton:hover { background-color: #a02a2e; }"
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
            "QPushButton { background-color: #8A8A8A; color: white; "
            "font-size: 9pt; padding: 8px; border-radius: 5px; }"
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
            "QPushButton { background-color: #107C10; color: white; "
            "font-size: 12pt; padding: 15px; border-radius: 5px; }"
        )
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
            QMessageBox.warning(
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
            QMessageBox.critical(self, "Reordering Error", f"Failed to auto-reorder pages: {e}")

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
            QMessageBox.information(self, "No Selection", "Please select a page to move.")
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
        reply = QMessageBox.question(
            self, "Reset Order",
            "Reset to original page order from stitching step?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.current_group = self.original_page_order.copy()
            self._refresh_page_order_list()
            self.status_label.setText("Page order reset to original.")

    def _on_approve_page_order(self):
        """User approves page order - move to Step 4"""
        if not self.current_group:
            QMessageBox.warning(self, "No Pages", "No pages to finalize.")
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
        reply = QMessageBox.question(
            self, "Return to Stitching?",
            "Going back will discard any metadata edits. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
        reply = QMessageBox.question(
            self, "Content-Based Ordering",
            "No page numbers detected. Would you like Ollama to analyze content flow and suggest page order?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
            QMessageBox.warning(
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
            QMessageBox.critical(
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
            "QPushButton { background-color: #107C10; color: white; "
            "font-size: 11pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #0e6b0e; }"
        )
        self.accept_delete_button.clicked.connect(lambda: self._finalize_document(delete_sources=True))
        button_layout.addWidget(self.accept_delete_button)

        button_layout.addSpacing(10)

        # Accept & Keep Sources
        self.accept_keep_button = QPushButton("✓ Accept & Keep Sources")
        self.accept_keep_button.setStyleSheet(
            "QPushButton { background-color: #0078D7; color: white; "
            "font-size: 11pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #005A9E; }"
        )
        self.accept_keep_button.clicked.connect(lambda: self._finalize_document(delete_sources=False))
        button_layout.addWidget(self.accept_keep_button)

        button_layout.addSpacing(10)

        # Reject & Delete PDF
        self.reject_button = QPushButton("✗ Reject & Delete PDF")
        self.reject_button.setStyleSheet(
            "QPushButton { background-color: #D13438; color: white; "
            "font-size: 11pt; padding: 15px; border-radius: 5px; }"
            "QPushButton:hover { background-color: #a02a2e; }"
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
        self.spinner_label.setStyleSheet("font-size: 16pt; color: #0078D7;")
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
            QMessageBox.information(
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
                QMessageBox.warning(
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
                QMessageBox.critical(
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
                QMessageBox.critical(
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
            QMessageBox.critical(
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
                QMessageBox.information(self, "Scan Complete", "No PNG files found in scan folder.")
                self.status_label.setText("No files found.")
                # Return to loading UI (could add a reset/retry button here)
                return

            # Check model selection
            selected_model = self.config_manager.get_setting('Ollama', 'model')
            if not selected_model:
                QMessageBox.warning(self, "No Model Selected", "Please select a model from the dropdown above.")
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

            # Phase 7: Start with bundle suggestions (Step 0)
            self.status_label.setText(f"Found {len(self.all_files)} file(s). Generating bundle suggestions...")
            self._load_and_show_bundle_suggestions()

        except Exception as e:
            QMessageBox.critical(self, "Error Scanning", f"An error occurred: {e}")
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
                QMessageBox.information(self, "No Files", "No files to process.")
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
            page_number = result.get('page_number') if isinstance(result, dict) else None
            total_pages = result.get('total_pages') if isinstance(result, dict) else None
            page_position = result.get('page_position') if isinstance(result, dict) else None
            confidence = result.get('confidence', 'low') if isinstance(result, dict) else 'low'
            company = result.get('company') if isinstance(result, dict) else None
            document_type = result.get('document_type') if isinstance(result, dict) else None
            document_date = result.get('document_date') if isinstance(result, dict) else None
            additional = result.get('additional', {}) if isinstance(result, dict) else {}

            # Build response summary
            response_parts = [f"Result: {'YES' if belongs else 'NO'}"]
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

            # Safety check: ensure status_label still exists
            if hasattr(self, 'status_label') and self.status_label:
                try:
                    self.status_label.setText(
                        f"✗ Ollama suggests excluding this page. "
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

            files_remaining = len(self.all_files) - self.current_file_index
            self.status_label.setText(f"✓ Page included. Group has {len(self.current_group)} page(s). ({files_remaining} remaining)")

            # Load next page
            if self.current_file_index < len(self.all_files):
                self._load_next_page_for_stitching()
            else:
                # No more files - need to explicitly end stitching
                self.status_label.setText("All pages processed. Click Exclude to finish stitching.")

    def _on_finish_group(self):
        """User clicked Finish Group button - finalize current group and move to Step 2"""
        # End stitching and move to Step 2 (without modifying current page state)
        if not self.current_group:
            QMessageBox.information(self, "No Pages", "No pages in current group.")
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

        # Update buttons based on new state
        self._update_step1_buttons_for_state('excluded')

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
                QMessageBox.information(self, "No Pages", "No pages in current group.")
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

        reply = QMessageBox.question(
            self, "Abort Document Stitching",
            "Are you sure you want to abort?\n\nAll progress will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
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
        reply = QMessageBox.question(
            self, "Refresh Metadata",
            f"Clear cached metadata for this page and request fresh analysis from Ollama?\n\n{os.path.basename(current_page)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
        self.large_preview_label.setStyleSheet("background-color: #ffffff; border: 2px solid #0078D7;")

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
                    "QLabel { background-color: #107C10; color: white; "
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
                    "QLabel { background-color: #D13438; color: white; "
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
                    "QLabel { background-color: #8A8A8A; color: white; "
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
                            "QLabel { background-color: #107C10; color: white; "
                            "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                            "padding: 2px; }"
                        )
                    elif new_state == 'excluded':
                        overlay.setText("✗")
                        overlay.setStyleSheet(
                            "QLabel { background-color: #D13438; color: white; "
                            "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                            "padding: 2px; }"
                        )
                    else:  # pending
                        overlay.setText("?")
                        overlay.setStyleSheet(
                            "QLabel { background-color: #8A8A8A; color: white; "
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
                "QLabel { background-color: #107C10; color: white; "
                "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                "padding: 2px; }"
            )
        elif state == 'excluded':
            overlay.setText("✗")
            overlay.setStyleSheet(
                "QLabel { background-color: #D13438; color: white; "
                "font-size: 20pt; font-weight: bold; border-radius: 15px; "
                "padding: 2px; }"
            )
        else:  # pending
            overlay.setText("?")
            overlay.setStyleSheet(
                "QLabel { background-color: #8A8A8A; color: white; "
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
                        "border: 6px solid #0078D7; "
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
            QMessageBox.warning(self, "No Model Selected", "Please select a model.")
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
            QMessageBox.warning(
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
            QMessageBox.warning(self, "Missing Information", "Please enter a Company name.")
            return

        if not title:
            QMessageBox.warning(self, "Missing Information", "Please enter a Document Title.")
            return

        # Save to history
        self.field_history.add_company(company)
        self.field_history.add_title(title)

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
        reply = QMessageBox.question(
            self, "Abort Processing",
            "Are you sure you want to abort? All progress will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    # ===== STEP 3: DOCUMENT FINALIZATION HANDLERS =====

    def _create_pdf_for_preview(self):
        """Create PDF and display preview"""
        if not self.current_group or not self.extracted_metadata:
            QMessageBox.warning(self, "Error", "No document data to create PDF.")
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
            QMessageBox.critical(self, "PDF Creation Error", f"Failed to create PDF.\n\nError: {e}")
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
            QMessageBox.warning(self, "Error", "No PDF created yet.")
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
            QMessageBox.critical(self, "Finalization Error", f"Error: {e}")

    def _on_reject_pdf(self):
        """User clicked Reject - delete PDF and return"""
        if hasattr(self, 'created_pdf_path') and os.path.exists(self.created_pdf_path):
            try:
                os.remove(self.created_pdf_path)
                self.status_label.setText("PDF rejected and deleted.")
            except Exception as e:
                QMessageBox.warning(self, "Delete Error", f"Could not delete PDF: {e}")

        reply = QMessageBox.question(
            self, "PDF Rejected",
            "PDF has been rejected. Start over with this document?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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

    def _load_and_show_bundle_suggestions(self):
        """Generate and display bundle suggestions (Step 0)"""
        try:
            # Hide regular workflow UI
            if hasattr(self, 'content_layout') and self.content_layout.parentWidget():
                self.content_layout.parentWidget().setVisible(False)
            if hasattr(self, 'thumbnail_scroll'):
                self.thumbnail_scroll.setVisible(False)

            # Update step indicator
            self.step_title_label.setText("AI Bundle Suggestions")
            self.step_indicator_label.setText("Step 0 of 5")

            # Generate bundle suggestions using BundlingService
            print(f"[Bundle Suggestions] Generating recommendations for {len(self.all_files)} files...")
            bundles = self.bundling_service.generate_bundle_recommendations(self.all_files)

            if bundles and len(bundles) > 0:
                # Show bundle suggestions view
                self.bundle_suggestions_view.set_bundles(bundles)
                self.bundle_suggestions_view.setVisible(True)
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
            QMessageBox.warning(
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
            QMessageBox.information(
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
                    self.bundle_suggestions_view.set_bundles(bundles)
                    self.status_label.setText(f"Updated: {len(bundles)} suggestion(s) for {len(remaining_files)} remaining page(s).")
                else:
                    # No more bundles, ask if user wants to process manually
                    self._check_remaining_pages_after_bundles()
            else:
                # All files bundled
                self._check_remaining_pages_after_bundles()

    def _on_bundle_modified(self, bundle_data):
        """Handle bundle modification - load into stitching workflow"""
        print(f"[Bundle] Modify requested: {bundle_data.get('document_type')}")
        file_paths = bundle_data.get('file_paths', [])
        if file_paths:
            self.all_files = file_paths
            self.current_file_index = 0
            self.current_group = list(file_paths)
            self.extracted_metadata['suggestion'] = {
                'company': bundle_data.get('company'),
                'title': bundle_data.get('document_type'),
                'date': bundle_data.get('document_date')
            }
            self.current_step = WorkflowStep.STITCHING
            self._on_skip_to_manual_workflow()

    def _on_bundle_rejected(self, bundle_data):
        """Handle bundle rejection"""
        print(f"[Bundle] Rejected: {bundle_data.get('document_type')}")
        QMessageBox.information(
            self, "Bundle Rejected",
            f"Rejected bundle for '{bundle_data.get('document_type')}'."
        )

    def _on_accept_all_high_confidence(self):
        """Accept all high confidence bundles automatically"""
        high_confidence_bundles = self.bundle_suggestions_view.get_high_confidence_bundles()
        if not high_confidence_bundles:
            QMessageBox.information(
                self, "No High Confidence Bundles",
                "There are no high confidence bundles (>= 80%) to accept."
            )
            return

        reply = QMessageBox.question(
            self, "Accept All High Confidence",
            f"Accept {len(high_confidence_bundles)} high confidence bundle(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
            QMessageBox.information(
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
            reply = QMessageBox.question(
                self,
                "Remaining Pages",
                f"There are {len(remaining_files)} page(s) remaining that were not bundled.\n\n"
                "Would you like to process them manually?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
                QMessageBox.information(
                    self,
                    "All Pages Bundled",
                    "All pages have been bundled! Proceeding to finalization."
                )
                self._transition_to_finalization()
            else:
                self.status_label.setText("No documents to finalize.")

    def _transition_to_finalization(self):
        """Transition to finalization step after bundle acceptance"""
        # Hide bundle suggestions
        self.bundle_suggestions_view.setVisible(False)

        # Update step indicator
        self.current_step = WorkflowStep.FINALIZATION
        self.step_title_label.setText("Document Finalization")
        self.step_indicator_label.setText("Step 4 of 5")

        # Show regular workflow UI for finalization
        if hasattr(self, 'content_layout') and self.content_layout.parentWidget():
            self.content_layout.parentWidget().setVisible(True)

        # Move to finalization step (this method should exist from earlier phases)
        self._show_finalization_step()

    def _on_skip_to_manual_workflow(self):
        """Skip bundle suggestions and go to manual stitching"""
        print("[Bundle] Skipping to manual workflow")

        # Hide bundle suggestions view
        self.bundle_suggestions_view.setVisible(False)

        # Show regular workflow UI
        if hasattr(self, 'content_layout') and self.content_layout.parentWidget():
            self.content_layout.parentWidget().setVisible(True)
        if hasattr(self, 'thumbnail_scroll'):
            self.thumbnail_scroll.setVisible(True)

        # Transition to stitching step
        self.current_step = WorkflowStep.STITCHING
        self.step_title_label.setText("Document Stitching")
        self.step_indicator_label.setText("Step 1 of 5")  # Phase 7: Updated to reflect bundle suggestions

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
        self._init_ui()
    
    def _init_ui(self):
        # Set background color for better visibility
        self.setStyleSheet("background-color: #0078D7; color: white;")

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(self.app_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28pt; font-weight: bold; color: white; padding: 20px;")
        main_layout.addWidget(title)

        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        scanner_label = QLabel()
        scanner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
                    # Scale to fit nicely in the window (max 400x400)
                    max_dimension = 400
                    if original_size.width() > max_dimension or original_size.height() > max_dimension:
                        scale_factor = min(max_dimension / original_size.width(), max_dimension / original_size.height())
                        scaled_size = QSize(int(original_size.width() * scale_factor), int(original_size.height() * scale_factor))
                    else:
                        scaled_size = original_size

                    self.movie.setScaledSize(scaled_size)
                    scanner_label.setMovie(self.movie)
                    scanner_label.setFixedSize(scaled_size)
                    self.movie.setSpeed(20)  # 20% of original speed (5x slower)
                    self.movie.start()
                else:
                    # Fallback: use default size
                    default_size = QSize(400, 400)
                    self.movie.setScaledSize(default_size)
                    scanner_label.setMovie(self.movie)
                    scanner_label.setFixedSize(default_size)
                    self.movie.start()
            else:
                scanner_label.setText("Error loading GIF: Invalid movie format")
                scanner_label.setStyleSheet("color: white; font-size: 14pt;")
        else:
            scanner_label.setText(f"GIF not found at:\n{scanner_gif_path}")
            scanner_label.setStyleSheet("color: white; font-size: 12pt;")

        content_layout.addWidget(scanner_label, 1)
            
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()

        process_button = QPushButton("Convert Scans")
        process_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        process_button.setMinimumHeight(60)
        process_button.setStyleSheet("QPushButton { background-color: #005A9E; color: white; border-radius: 5px; padding: 10px; }")
        process_button.clicked.connect(self.show_processing_window)
        button_layout.addWidget(process_button)

        self.extract_button = QPushButton("Convert PDFs")
        self.extract_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.extract_button.setMinimumHeight(60)
        self.extract_button.setEnabled(True)
        self.extract_button.setStyleSheet("QPushButton { background-color: #005A9E; color: white; border-radius: 5px; padding: 10px; }")
        self.extract_button.clicked.connect(self._process_pdfs)
        button_layout.addWidget(self.extract_button)

        settings_button = QPushButton("Change Settings")
        settings_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        settings_button.setMinimumHeight(60)
        settings_button.setStyleSheet("QPushButton { background-color: #005A9E; color: white; border-radius: 5px; padding: 10px; }")
        settings_button.clicked.connect(self.show_settings_window)
        button_layout.addWidget(settings_button)

        quit_button = QPushButton("Quit")
        quit_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        quit_button.setMinimumHeight(60)
        quit_button.setStyleSheet("QPushButton { background-color: #8B0000; color: white; border-radius: 5px; padding: 10px; }")
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
        scan_folder = self.config_manager.get_setting("DocumentProcessing", "scan_folder")
        if not os.path.isdir(scan_folder):
            self.extract_button.setEnabled(False)
            return
        
        pdf_files = [f for f in os.listdir(scan_folder) if f.lower().endswith('.pdf')]
        self.extract_button.setEnabled(len(pdf_files) > 0)

    def _process_pdfs(self):
        """Open the Convert PDFs window"""
        convert_pdfs_window = ConvertPDFsWindow()
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
        settings_window.exec()

    def quit_application(self):
        """Handle Quit button click with confirmation"""
        reply = QMessageBox.question(
            self,
            'Quit Application',
            'Are you sure you want to quit?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            QApplication.quit()

    def on_processing_finished(self):
        if self.processing_window:
            self.processing_window = None
        self.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = StartupWindow()
    window.show()
    sys.exit(app.exec())
