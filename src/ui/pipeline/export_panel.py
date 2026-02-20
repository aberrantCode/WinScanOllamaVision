"""
Stage 4: Export panel — confirm completion and open output directory.
"""

import contextlib
import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from config.config_manager import ConfigManager
from ui.styles import show_warning
from ui.theme_manager import ThemeManager


class ExportPanel(QWidget):
    """
    Stage 4: Export — confirm completion.

    Displays a session summary: how many PDFs were accepted and where
    they were written. Offers to open the output directory.
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

        self.summary_lbl: QLabel | None = None
        self._build_ui()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(12)

        title = QLabel("Export — Session complete")
        title.setStyleSheet(
            f"font-size: 11pt; font-weight: 600; color: {self._c()['text_primary']};"
        )
        root.addWidget(title)

        self.summary_lbl = QLabel(
            "No bundles have been accepted in this session yet.\n"
            "Go back to Bundle to review suggestions."
        )
        self.summary_lbl.setWordWrap(True)
        self.summary_lbl.setStyleSheet(f"font-size: 10pt; color: {self._c()['text_secondary']};")
        root.addWidget(self.summary_lbl)

        # Open output directory
        open_dir_btn = QPushButton("Open Output Directory")
        open_dir_btn.setFixedHeight(32)
        open_dir_btn.setFixedWidth(200)
        open_dir_btn.clicked.connect(self._open_output_dir)
        root.addWidget(open_dir_btn)

        root.addStretch()

    def update_stats(self, stats: dict) -> None:
        self._stats = stats
        accepted = stats.get("accepted", 0)
        rejected = stats.get("rejected", 0)

        output_dir = ""
        with contextlib.suppress(Exception):
            output_dir = str(self.config_manager.get_setting("OutputDirectory", "path", ""))

        lines = [
            f"PDFs accepted: {accepted}",
            f"Bundles rejected: {rejected}",
        ]
        if output_dir:
            lines.append(f"\nOutput directory:\n{output_dir}")

        if self.summary_lbl:
            self.summary_lbl.setText("\n".join(lines))

    def _open_output_dir(self) -> None:
        try:
            output_dir = str(self.config_manager.get_setting("OutputDirectory", "path", ""))
            if output_dir and os.path.isdir(output_dir):
                os.startfile(output_dir)
            else:
                show_warning(self, "Directory Not Found", "Output directory is not configured.")
        except Exception as e:
            show_warning(self, "Error", f"Could not open directory:\n{e}")
