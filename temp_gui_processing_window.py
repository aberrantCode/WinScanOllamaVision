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
        safe_filename = f"{company} - {title} - {date}.pdf".replace("/", "-").replace("\", "-").replace(":", "-")
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
