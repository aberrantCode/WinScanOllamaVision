"""
Stage 4: Export panel — confirm completion and open output directory.
"""

import contextlib
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from ui.theme.styles import show_warning
from ui.theme.theme_manager import ThemeManager


class ExportPanel(QWidget):
    """
    Stage 4: Export — confirm completion.

    Displays a full session summary: metric cards (images processed, PDFs
    created, pages analyzed, bundles rejected, errors, success rate), an
    output path label, and a PDF details table listing every accepted bundle.
    """

    back_requested = pyqtSignal()

    def __init__(
        self,
        config_manager: ConfigManager,
        dark_mode: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_manager = config_manager
        self.dark_mode = dark_mode
        self._stats: dict = {}

        # Metric card value labels (populated in _build_ui, updated in update_stats)
        self._metric_images: QLabel | None = None
        self._metric_pdfs: QLabel | None = None
        self._metric_pages: QLabel | None = None
        self._metric_rejected: QLabel | None = None
        self._metric_errors: QLabel | None = None
        self._metric_success: QLabel | None = None
        self._output_dir_lbl: QLabel | None = None
        self._pdf_table: QTableWidget | None = None
        # Keep backward-compat reference (some callers may use it)
        self.summary_lbl: QLabel | None = None

        self._build_ui()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(12)

        c = self._c()

        title = QLabel("Export — Session complete")
        title.setStyleSheet(f"font-size: 11pt; font-weight: 600; color: {c['text_primary']};")
        root.addWidget(title)

        # ── Session Summary header
        summary_header = QLabel("Session Summary")
        summary_header.setStyleSheet(
            f"font-size: 10pt; font-weight: 600; color: {c['text_secondary']};"
        )
        root.addWidget(summary_header)

        # ── Metric cards row
        from ui.pipeline.metric_card import create_metric_card

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        def _card(title_text: str, default: str) -> QLabel:
            card = create_metric_card(c, title_text, default)
            cards_row.addWidget(card)
            # The value label object name is derived from the title
            key = title_text.lower().replace(" ", "_") + "_value"
            lbl = card.findChild(QLabel, key)
            return lbl  # type: ignore[return-value]

        self._metric_images = _card("Images Processed", "0")
        self._metric_pdfs = _card("PDFs Created", "0")
        self._metric_pages = _card("Pages Analyzed", "0")
        self._metric_rejected = _card("Bundles Rejected", "0")
        self._metric_errors = _card("Errors", "0")
        self._metric_success = _card("Success Rate", "—")

        root.addLayout(cards_row)

        # ── Output directory label
        self._output_dir_lbl = QLabel("Output: —")
        self._output_dir_lbl.setWordWrap(True)
        self._output_dir_lbl.setStyleSheet(f"font-size: 9pt; color: {c['text_tertiary']};")
        root.addWidget(self._output_dir_lbl)

        # Keep summary_lbl as a thin wrapper so any old callers still work
        self.summary_lbl = self._output_dir_lbl

        # ── PDF details table
        table_header = QLabel("PDF Details")
        table_header.setStyleSheet(
            f"font-size: 10pt; font-weight: 600; color: {c['text_secondary']}; margin-top: 4px;"
        )
        root.addWidget(table_header)

        self._pdf_table = QTableWidget()
        self._pdf_table.setColumnCount(6)
        self._pdf_table.setHorizontalHeaderLabels(
            ["PDF Filename", "Company", "Type", "Date", "Pages", "Created"]
        )
        hdr = self._pdf_table.horizontalHeader()
        if hdr:
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self._pdf_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._pdf_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._pdf_table.setAlternatingRowColors(True)
        vh = self._pdf_table.verticalHeader()
        if vh:
            vh.setVisible(False)
        self._pdf_table.setStyleSheet(
            f"QTableWidget {{ background-color: {c['bg_secondary']};"
            f" color: {c['text_primary']}; gridline-color: {c['border']}; }}"
            f"QHeaderView::section {{ background-color: {c['bg_tertiary']};"
            f" color: {c['text_secondary']}; padding: 4px; border: none; }}"
        )
        root.addWidget(self._pdf_table, stretch=1)

        # ── Open output directory button (always at bottom)
        open_dir_btn = QPushButton("Open Output Directory")
        open_dir_btn.setFixedHeight(32)
        open_dir_btn.setFixedWidth(200)
        open_dir_btn.clicked.connect(self._open_output_dir)
        root.addWidget(open_dir_btn, alignment=Qt.AlignmentFlag.AlignLeft)

    def update_stats(self, stats: dict) -> None:
        """Populate metric cards and PDF table from workflow stats dict."""
        self._stats = stats

        accepted = stats.get("accepted", 0)
        rejected = stats.get("rejected", 0)
        images_processed = stats.get("images_processed", stats.get("total_files", 0))
        pages_analyzed = stats.get("pages_analyzed", accepted)
        errors = stats.get("errors", 0)
        total_processed = accepted + rejected
        success_rate = int(accepted / total_processed * 100) if total_processed > 0 else 0

        # Update metric cards
        if self._metric_images:
            self._metric_images.setText(str(images_processed))
        if self._metric_pdfs:
            self._metric_pdfs.setText(str(accepted))
        if self._metric_pages:
            self._metric_pages.setText(str(pages_analyzed))
        if self._metric_rejected:
            self._metric_rejected.setText(str(rejected))
        if self._metric_errors:
            self._metric_errors.setText(str(errors))
        if self._metric_success:
            self._metric_success.setText(f"{success_rate}%" if total_processed > 0 else "—")

        # Resolve output directory
        output_dir = self._resolve_output_dir()
        if self._output_dir_lbl:
            self._output_dir_lbl.setText(f"Output: {output_dir}" if output_dir else "Output: —")

        # Populate PDF table
        pdf_rows: list[dict] = stats.get("pdf_files", [])
        self._populate_pdf_table(pdf_rows)

    def _resolve_output_dir(self) -> str:
        """Return a human-readable output directory string."""
        output_dir = ""
        with contextlib.suppress(Exception):
            strategy = self.config_manager.get_setting(
                "OutputDirectory", "strategy", "same_as_source"
            )
            if strategy == "global_custom":
                output_dir = str(
                    self.config_manager.get_setting("OutputDirectory", "global_custom_path", "")
                )
            elif strategy == "same_as_source":
                name = self.config_manager.get_setting(
                    "OutputDirectory", "subdirectory_name", "PDFs"
                )
                output_dir = f"<source dir>/{name}"
            elif strategy == "beside_source":
                output_dir = "Beside source files"
        return output_dir

    def _populate_pdf_table(self, rows: list[dict]) -> None:
        """Fill the PDF details table from a list of accepted bundle dicts."""
        if not self._pdf_table:
            return
        self._pdf_table.setRowCount(0)
        for row in rows:
            r = self._pdf_table.rowCount()
            self._pdf_table.insertRow(r)

            def _cell(text: str) -> QTableWidgetItem:
                item = QTableWidgetItem(text or "—")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                return item

            self._pdf_table.setItem(r, 0, _cell(str(row.get("pdf_filename", ""))))
            self._pdf_table.setItem(r, 1, _cell(str(row.get("company", ""))))
            self._pdf_table.setItem(r, 2, _cell(str(row.get("document_type", ""))))
            self._pdf_table.setItem(r, 3, _cell(str(row.get("document_date", ""))))
            pages = row.get("pages", row.get("total_pages", ""))
            self._pdf_table.setItem(r, 4, _cell(str(pages) if pages else "—"))
            self._pdf_table.setItem(r, 5, _cell(str(row.get("created_at", ""))))

    def _open_output_dir(self) -> None:
        try:
            strategy = self.config_manager.get_setting(
                "OutputDirectory", "strategy", "same_as_source"
            )
            if strategy == "global_custom":
                output_dir = str(
                    self.config_manager.get_setting("OutputDirectory", "global_custom_path", "")
                )
                if output_dir and os.path.isdir(output_dir):
                    os.startfile(output_dir)
                else:
                    show_warning(
                        self,
                        "Directory Not Found",
                        "Output directory is not configured or does not exist.",
                    )
            else:
                show_warning(
                    self,
                    "Output Location Varies",
                    "Output location depends on each bundle's source directory.",
                )
        except Exception as e:
            show_warning(self, "Error", f"Could not open directory:\n{e}")
