import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QLabel, QLineEdit, QScrollArea, QFrame,
    QMessageBox, QDialog, QDialogButtonBox, QListWidget, QCheckBox,
    QGridLayout, QSizePolicy, QFileDialog
)
from PyQt6.QtGui import QPixmap, QDesktopServices, QMovie, QIcon
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QThread

try:
    import fitz
except ImportError:
    print("Error: PyMuPDF (fitz) is not installed. Please run 'pip install PyMuPDF'.")
    sys.exit(1)

from config_manager import ConfigManager
from ollama_service import OllamaService
from file_processor import FileProcessor

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
            result = self.service_method(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit(e)

class FinalConfirmationDialog(QDialog):
    ACCEPT_DELETE_SOURCES, ACCEPT_KEEP_SOURCES, REJECT_DELETE_PDF = range(3)

    def __init__(self, pdf_path, source_paths, expected, actual, searchable, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScan")
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

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = ConfigManager()
        self.ollama_service = OllamaService(base_url=self.config_manager.get_setting('Ollama', 'base_url'))
        
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScan")
        self.setWindowTitle(f"{self.app_name} - Settings")
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setMinimumWidth(600)
        self._init_ui()
        self._load_ollama_models()

    def _init_ui(self):
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Default Ollama Model:"), 0, 0)
        model_layout = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        model_layout.addWidget(self.model_combo)
        
        self.model_details_button = QPushButton("Details")
        self.model_details_button.clicked.connect(self._open_model_details)
        model_layout.addWidget(self.model_details_button)
        layout.addLayout(model_layout, 0, 1)

        layout.addWidget(QLabel("Scan Folder:"), 1, 0)
        folder_layout = QHBoxLayout()
        self.scan_folder_edit = QLineEdit(self.config_manager.get_setting("DocumentProcessing", "scan_folder"))
        folder_layout.addWidget(self.scan_folder_edit)
        
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._open_folder_picker)
        folder_layout.addWidget(browse_button)
        layout.addLayout(folder_layout, 1, 1)

        layout.addWidget(QLabel("Title Keywords (comma-separated):"), 2, 0)
        self.keywords_edit = QLineEdit(self.config_manager.get_setting("DocumentProcessing", "title_keywords"))
        layout.addWidget(self.keywords_edit, 2, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box, 3, 0, 1, 2)

    def _load_ollama_models(self):
        self.model_combo.clear()
        try:
            local_models = self.ollama_service.list_models()
            model_names = [m['name'] for m in local_models]
            
            suggested_models = ["llava:latest", "qwen2.5-vl", "deepseek-ocr"]
            for model in suggested_models:
                if model not in model_names:
                    model_names.append(model)
            
            self.model_combo.addItems(model_names)
            
            current_model = self.config_manager.get_setting("Ollama", "model")
            if current_model and self.model_combo.findText(current_model) != -1:
                self.model_combo.setCurrentText(current_model)

        except Exception as e:
            QMessageBox.critical(self, "Error Loading Models", str(e))

    def _open_model_details(self):
        selected_model = self.model_combo.currentText()
        if selected_model:
            model_name_only = selected_model.split(':')[0]
            QDesktopServices.openUrl(QUrl(f"https://ollama.com/library/{model_name_only}"))

    def _open_folder_picker(self):
        current_path = self.scan_folder_edit.text()
        if not os.path.isdir(current_path):
            current_path = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Scan Folder", current_path)
        if directory:
            self.scan_folder_edit.setText(directory)

    def save_settings(self):
        self.config_manager.set_setting("Ollama", "model", self.model_combo.currentText())
        self.config_manager.set_setting("DocumentProcessing", "scan_folder", self.scan_folder_edit.text())
        self.config_manager.set_setting("DocumentProcessing", "title_keywords", self.keywords_edit.text())
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved.")
        self.accept()

class PagePreviewWidget(QWidget):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        layout = QHBoxLayout(self)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(True)
        layout.addWidget(self.checkbox)
        image_label = QLabel()
        image_label.setFrameShape(QFrame.Shape.StyledPanel)
        pixmap = QPixmap(image_path)
        scaled_pixmap = pixmap.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation)
        image_label.setPixmap(scaled_pixmap)
        layout.addWidget(image_label)
        layout.addStretch()

    def is_selected(self) -> bool:
        return self.checkbox.isChecked()

class ProcessingWindow(QMainWindow):
    processing_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.ollama_service = OllamaService(base_url=self.config_manager.get_setting('Ollama', 'base_url'))
        self.file_processor = FileProcessor(self.config_manager)
        
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScan")
        self.setWindowTitle(f"{self.app_name} - Processing")
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        width = int(self.config_manager.get_setting('GUI', 'window_width', '1024'))
        height = int(self.config_manager.get_setting('GUI', 'window_height', '768'))
        self.setGeometry(100, 100, width, height)
        self.document_groups_queue = []
        self.current_processing_group = []
        self._init_ui()
        self._load_ollama_models()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        top_bar_layout = QHBoxLayout()
        ollama_label = QLabel("Ollama Model:")
        top_bar_layout.addWidget(ollama_label)
        self.ollama_model_combo = QComboBox()
        self.ollama_model_combo.setMinimumWidth(200)
        self.ollama_model_combo.currentIndexChanged.connect(self._on_ollama_model_selected)
        top_bar_layout.addWidget(self.ollama_model_combo)
        self.pull_model_button = QPushButton("Pull Model")
        self.pull_model_button.clicked.connect(self._pull_selected_model)
        self.pull_model_button.setEnabled(False)
        top_bar_layout.addWidget(self.pull_model_button)
        self.model_details_button = QPushButton("Model Details")
        self.model_details_button.clicked.connect(self._open_model_details)
        self.model_details_button.setEnabled(False)
        top_bar_layout.addWidget(self.model_details_button)
        top_bar_layout.addStretch(1)
        main_layout.addLayout(top_bar_layout)
        doc_info_layout = QHBoxLayout()
        doc_info_layout.addWidget(QLabel("Company:"))
        self.company_edit = QLineEdit()
        doc_info_layout.addWidget(self.company_edit)
        doc_info_layout.addWidget(QLabel("Title:"))
        self.title_edit = QLineEdit()
        doc_info_layout.addWidget(self.title_edit)
        doc_info_layout.addWidget(QLabel("Date:"))
        self.date_edit = QLineEdit()
        doc_info_layout.addWidget(self.date_edit)
        main_layout.addLayout(doc_info_layout)
        self.preview_scroll_area = QScrollArea()
        self.preview_scroll_area.setWidgetResizable(True)
        self.preview_content_widget = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_content_widget)
        self.preview_content_widget.setLayout(self.preview_layout)
        self.preview_scroll_area.setWidget(self.preview_content_widget)
        main_layout.addWidget(self.preview_scroll_area)
        action_buttons_layout = QHBoxLayout()
        self.scan_group_button = QPushButton("Scan & Group New Documents")
        self.scan_group_button.clicked.connect(self._scan_and_group)
        action_buttons_layout.addWidget(self.scan_group_button)
        self.approve_process_button = QPushButton("Approve & Process Document")
        self.approve_process_button.clicked.connect(self._approve_and_process)
        self.approve_process_button.setEnabled(False)
        action_buttons_layout.addWidget(self.approve_process_button)
        main_layout.addLayout(action_buttons_layout)
        self.status_label = QLabel("Ready.")
        main_layout.addWidget(self.status_label)

    def _load_ollama_models(self):
        self.ollama_model_combo.clear()
        self.ollama_model_combo.addItem("Select a model...", userData=None)
        try:
            local_models = self.ollama_service.list_models()
            for model in local_models:
                self.ollama_model_combo.addItem(model['name'], userData={'local': True, 'name': model['name']})
            self.status_label.setText(f"Found {len(local_models)} local Ollama models.")
        except ConnectionError as e:
            QMessageBox.critical(self, "Ollama Connection Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error Loading Models", str(e))
        suggested_models = ["llava:latest", "qwen2.5-vl", "deepseek-ocr"]
        for model_name in suggested_models:
            if not any(self.ollama_model_combo.itemData(i) and self.ollama_model_combo.itemData(i)['name'] == model_name for i in range(self.ollama_model_combo.count())):
                self.ollama_model_combo.addItem(f"{model_name} (remote)", userData={'local': False, 'name': model_name})

    def _on_ollama_model_selected(self):
        selected_data = self.ollama_model_combo.currentData()
        if selected_data:
            self.model_details_button.setEnabled(True)
            if not selected_data['local']:
                self.pull_model_button.setEnabled(True)
            else:
                self.pull_model_button.setEnabled(False)
                self.config_manager.set_setting('Ollama', 'model', selected_data['name'])
        else:
            self.model_details_button.setEnabled(False)
            self.pull_model_button.setEnabled(False)

    def _pull_selected_model(self):
        selected_data = self.ollama_model_combo.currentData()
        if not selected_data or selected_data['local']: return
        model_name = selected_data['name']
        self.pull_model_button.setEnabled(False)
        self.status_label.setText(f"Downloading {model_name}...")
        self.worker_thread = OllamaWorker(self.ollama_service.pull_model, model_name)
        self.worker_thread.finished.connect(self._on_model_pull_finished)
        self.worker_thread.start()
        
    def _on_model_pull_finished(self, result):
        if isinstance(result, Exception):
            QMessageBox.critical(self, "Model Download Error", str(result))
        else:
            QMessageBox.information(self, "Model Download Complete", f"Model {self.ollama_model_combo.currentData()['name']} downloaded successfully.")
            current_selection = self.ollama_model_combo.currentData()['name']
            self._load_ollama_models()
            index = self.ollama_model_combo.findText(current_selection)
            if index != -1: self.ollama_model_combo.setCurrentIndex(index)
        self.pull_model_button.setEnabled(True)

    def _open_model_details(self):
        selected_data = self.ollama_model_combo.currentData()
        if selected_data and selected_data['name']:
            model_name_only = selected_data['name'].split(':')[0]
            QDesktopServices.openUrl(QUrl(f"https://ollama.com/library/{model_name_only}"))

    def _clear_preview_area(self):
        while self.preview_layout.count():
            child = self.preview_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.company_edit.clear()
        self.title_edit.clear()
        self.date_edit.clear()
        self.current_processing_group = []
        self.approve_process_button.setEnabled(False)

    def _scan_and_group(self):
        self.status_label.setText("Scanning for new documents...")
        self.scan_group_button.setEnabled(False)
        try:
            image_files = self.file_processor._get_image_files()
            self.document_groups_queue = self.file_processor.group_files_by_timestamp(image_files)
            if not self.document_groups_queue:
                QMessageBox.information(self, "Scan Complete", "No new documents found.")
                self.status_label.setText("No new documents found.")
            else:
                self.status_label.setText(f"Found {len(self.document_groups_queue)} potential documents.")
                self._load_next_group()
        except Exception as e:
            QMessageBox.critical(self, "Error Scanning", f"An error occurred: {e}")
        finally:
            self.scan_group_button.setEnabled(True)

    def _load_next_group(self):
        self._clear_preview_area()
        if not self.document_groups_queue:
            QMessageBox.information(self, "Processing Complete", "All document groups have been processed.")
            self.processing_finished.emit()
            self.close()
            return
        self.current_processing_group = self.document_groups_queue.pop(0)
        for image_path in self.current_processing_group:
            self.preview_layout.addWidget(PagePreviewWidget(image_path))
        self.status_label.setText(f"Validating group... ({len(self.document_groups_queue)} groups remaining)")
        selected_model = self.config_manager.get_setting('Ollama', 'model')
        if not selected_model:
            QMessageBox.warning(self, "No Model Selected", "Please select a model first.")
            return
        self.worker_thread = OllamaWorker(self.ollama_service.validate_grouping, selected_model, self.current_processing_group)
        self.worker_thread.finished.connect(self._on_grouping_validated)
        self.worker_thread.start()

    def _on_grouping_validated(self, result):
        if isinstance(result, Exception):
            QMessageBox.critical(self, "Grouping Validation Error", f"Ollama failed to validate: {result}")
        elif not result:
            QMessageBox.warning(self, "Grouping Mismatch", "Ollama suggests these pages may not belong together.")
        self.status_label.setText("Extracting document info...")
        selected_model = self.config_manager.get_setting('Ollama', 'model')
        title_keywords = self.config_manager.get_setting('DocumentProcessing', 'title_keywords')
        self.worker_thread = OllamaWorker(self.ollama_service.extract_document_info, selected_model, self.current_processing_group, title_keywords)
        self.worker_thread.finished.connect(self._on_info_extracted)
        self.worker_thread.start()

    def _on_info_extracted(self, result):
        if isinstance(result, Exception):
            QMessageBox.critical(self, "Info Extraction Error", f"Ollama failed to extract info: {result}")
        else:
            self.company_edit.setText(result.get("company", ""))
            self.title_edit.setText(result.get("title", ""))
            self.date_edit.setText(result.get("date", ""))
        self.status_label.setText("Ready for review.")
        self.approve_process_button.setEnabled(True)

    def _approve_and_process(self):
        self.approve_process_button.setEnabled(False)
        selected_pages = [self.preview_layout.itemAt(i).widget().image_path for i in range(self.preview_layout.count()) if self.preview_layout.itemAt(i).widget().is_selected()]
        unselected_pages = [self.preview_layout.itemAt(i).widget().image_path for i in range(self.preview_layout.count()) if not self.preview_layout.itemAt(i).widget().is_selected()]
        if unselected_pages: self.document_groups_queue.insert(0, unselected_pages)
        if not selected_pages:
            QMessageBox.warning(self, "No Pages Selected", "At least one page must be selected.")
            self.approve_process_button.setEnabled(True)
            return
        company = self.company_edit.text() or "UNKNOWN_COMPANY"
        title = self.title_edit.text() or "UNKNOWN_TITLE"
        date = self.date_edit.text() or "UNKNOWN_DATE"
        safe_filename = f"{company} - {title} - {date}.pdf".replace("/", "-").replace("\\", "-").replace(":", "-")
        self.status_label.setText("Extracting text for searchable PDF...")
        selected_model = self.config_manager.get_setting('Ollama', 'model')
        self.worker_thread = OllamaWorker(self.ollama_service.extract_text_and_coords, selected_model, selected_pages)
        self.worker_thread.finished.connect(lambda result: self._on_text_coords_extracted(result, selected_pages, safe_filename))
        self.worker_thread.start()

    def _on_text_coords_extracted(self, result, selected_pages, safe_filename):
        is_searchable = False
        if isinstance(result, Exception):
            QMessageBox.warning(self, "OCR Error", f"Could not extract text for searchable PDF: {result}. PDF will be image-only.")
        elif not result or not result.get("pages"):
            QMessageBox.warning(self, "OCR Warning", "Ollama did not return structured text data. PDF will be image-only.")
        else:
            is_searchable = True
        pdf_path = self.file_processor.create_searchable_pdf(selected_pages, safe_filename, result, is_searchable)
        if not pdf_path or not os.path.exists(pdf_path):
            QMessageBox.critical(self, "PDF Creation Failed", "Failed to create the final PDF.")
            self._load_next_group()
            return
        self._show_final_confirmation(pdf_path, selected_pages, is_searchable)

    def _show_final_confirmation(self, pdf_path, processed_pngs, is_searchable):
        try:
            with fitz.open(pdf_path) as doc: actual_pages = doc.page_count
        except Exception as e:
            QMessageBox.critical(self, "PDF Verification Error", f"Could not verify created PDF: {e}")
            actual_pages = -1
        expected_pages = len(processed_pngs)
        dialog = FinalConfirmationDialog(pdf_path, processed_pngs, expected_pages, actual_pages, is_searchable, self)
        result = dialog.exec()
        if result == FinalConfirmationDialog.ACCEPT_DELETE_SOURCES:
            self.file_processor.delete_files(processed_pngs)
        elif result == FinalConfirmationDialog.REJECT_DELETE_PDF:
            self.file_processor.delete_files([pdf_path])
        self._load_next_group()

class StartupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.app_name = self.config_manager.get_setting("GUI", "app_name", "WinScanOllamaVision")
        self.setWindowTitle(self.app_name)
        
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self.processing_window = None
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel(self.app_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24pt; font-weight: bold; color: #00A8E8;")

        scanner_label = QLabel()
        scanner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # User must place an animated GIF at assets/scanner.gif
        scanner_gif_path = os.path.join("assets", "scanner.gif")
        if os.path.exists(scanner_gif_path):
            movie = QMovie(scanner_gif_path)
            scanner_label.setMovie(movie)
            movie.start()
        else:
            scanner_label.setText("(Place 'scanner.gif' in 'assets' folder)")

        process_button = QPushButton("Process Scans")
        process_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        process_button.setMinimumHeight(50)
        process_button.clicked.connect(self.show_processing_window)

        settings_button = QPushButton("Settings")
        settings_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        settings_button.setMinimumHeight(50)
        settings_button.clicked.connect(self.show_settings_window)

        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(scanner_label)
        layout.addSpacing(20)
        layout.addWidget(process_button)
        layout.addWidget(settings_button)
        
        self.setFixedSize(600, 500)

    def show_processing_window(self):
        if not self.processing_window or not self.processing_window.isVisible():
            self.processing_window = ProcessingWindow()
            self.processing_window.processing_finished.connect(self.on_processing_finished)
        self.hide()
        self.processing_window.show()

    def show_settings_window(self):
        settings_window = SettingsWindow(self)
        settings_window.exec()

    def on_processing_finished(self):
        if self.processing_window:
            self.processing_window = None
        self.show()
