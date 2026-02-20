"""
Document Pipeline Window — unified Import → Analyze → Bundle → Export workflow.
"""

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from ui.pipeline.analyze_panel import AnalyzePanel
from ui.pipeline.bundle_panel import BundlePanel
from ui.pipeline.export_panel import ExportPanel
from ui.pipeline.import_panel import ImportPanel
from ui.pipeline.stages import (
    STAGE_ANALYZE,
    STAGE_BUNDLE,
    STAGE_EXPORT,
    STAGE_IMPORT,
    PipelineHeaderWidget,
)
from ui.styles import Colors
from ui.theme_manager import ThemeManager


class DocumentPipelineWindow(QMainWindow):
    """
    Unified Import → Analyze → Bundle → Export window.

    Owns shared database instances and coordinates the four stage panels
    through a QStackedWidget, driven by the PipelineHeaderWidget rail.
    """

    def __init__(
        self,
        analysis_db: AnalysisDB | None = None,
        metadata_db: MetadataDB | None = None,
        config_manager: ConfigManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._owns_analysis_db = analysis_db is None
        self._owns_metadata_db = metadata_db is None
        self.analysis_db = analysis_db or AnalysisDB()
        self.metadata_db = metadata_db or MetadataDB()
        self.config_manager = config_manager or ConfigManager()

        theme = self.config_manager.get_setting("Theme", "theme", "dark")
        self.dark_mode = theme == "dark"

        self._current_stage = STAGE_IMPORT
        self._completed_stages: set[int] = set()

        self._build_ui()
        self._apply_theme()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        self.setWindowTitle("Document Pipeline")
        self.resize(1200, 800)
        self.setMinimumSize(900, 640)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Pipeline header rail
        self.header = PipelineHeaderWidget()
        self.header.set_stage(STAGE_IMPORT)
        self.header.stage_clicked.connect(self._go_to_stage)
        root.addWidget(self.header)

        # Thin separator under header
        self._header_sep = QFrame()
        self._header_sep.setFixedHeight(2)
        root.addWidget(self._header_sep)

        # ── Stage panels
        self.stack = QStackedWidget()

        self.import_panel = ImportPanel(
            analysis_db=self.analysis_db,
            config_manager=self.config_manager,
            dark_mode=self.dark_mode,
        )
        self.analyze_panel = AnalyzePanel(
            config_manager=self.config_manager,
            analysis_db=self.analysis_db,
            metadata_db=self.metadata_db,
            dark_mode=self.dark_mode,
        )

        self.bundle_panel = BundlePanel(
            analysis_db=self.analysis_db,
            metadata_db=self.metadata_db,
            config_manager=self.config_manager,
            dark_mode=self.dark_mode,
        )
        self.bundle_panel.bundles_completed.connect(self._on_bundles_completed)

        self.export_panel = ExportPanel(
            config_manager=self.config_manager,
            dark_mode=self.dark_mode,
        )

        self.stack.addWidget(self.import_panel)
        self.stack.addWidget(self.analyze_panel)
        self.stack.addWidget(self.bundle_panel)
        self.stack.addWidget(self.export_panel)

        root.addWidget(self.stack, stretch=1)

        # ── Shared footer (full window width, matches header style)
        self._footer_sep = QFrame()
        self._footer_sep.setFixedHeight(2)
        root.addWidget(self._footer_sep)

        self._footer_bar = QWidget()
        footer_layout = QHBoxLayout(self._footer_bar)
        footer_layout.setContentsMargins(16, 6, 16, 8)
        footer_layout.setSpacing(8)

        self._back_btn = QPushButton("← Back")
        self._back_btn.setFixedHeight(30)
        self._back_btn.clicked.connect(self._on_back_clicked)
        footer_layout.addWidget(self._back_btn)

        footer_layout.addStretch()

        self._fwd_btn = QPushButton("Next: Analyze →")
        self._fwd_btn.setFixedHeight(30)
        self._fwd_btn.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.PRIMARY}; color: white; "
            f"border: none; border-radius: 4px; padding: 4px 16px; font-weight: 600; }}"
            f"QPushButton:hover {{ background-color: {Colors.PRIMARY_HOVER}; }}"
        )
        self._fwd_btn.clicked.connect(self._on_next_clicked)
        footer_layout.addWidget(self._fwd_btn)

        root.addWidget(self._footer_bar)
        self._update_footer_buttons(self._current_stage)

    def _apply_theme(self) -> None:
        self.setStyleSheet(ThemeManager.get_stylesheet(self.dark_mode))
        header_bg = "#111C2E" if self.dark_mode else "#F0F2F5"
        sep_color = "#0E1727" if self.dark_mode else "#F8F9FA"
        self.header.set_bg_color(header_bg)
        self._header_sep.setStyleSheet(f"background-color: {sep_color}; border: none;")
        self._footer_sep.setStyleSheet(f"background-color: {sep_color}; border: none;")
        self._footer_bar.setStyleSheet(f"background-color: {header_bg};")

    def _go_to_stage(self, stage: int) -> None:
        stage = max(STAGE_IMPORT, min(STAGE_EXPORT, stage))

        # Mark the current stage complete when moving forward
        if stage > self._current_stage:
            self._completed_stages.add(self._current_stage)

        self._current_stage = stage
        self.stack.setCurrentIndex(stage)
        self.header.set_stage(stage, self._completed_stages)
        self._update_footer_buttons(stage)

        # Trigger stage-specific refresh
        if stage == STAGE_IMPORT:
            self.import_panel.refresh()
        elif stage == STAGE_ANALYZE:
            self.analyze_panel.refresh()
        elif stage == STAGE_BUNDLE:
            self.bundle_panel.refresh_bundle_count()

    def _on_back_clicked(self) -> None:
        self._go_to_stage(self._current_stage - 1)

    def _on_next_clicked(self) -> None:
        self._go_to_stage(self._current_stage + 1)

    def _update_footer_buttons(self, stage: int) -> None:
        back_labels = {
            STAGE_IMPORT: None,
            STAGE_ANALYZE: "← Back",
            STAGE_BUNDLE: "← Back",
            STAGE_EXPORT: "← Back to Bundle",
        }
        next_labels = {
            STAGE_IMPORT: "Next: Analyze →",
            STAGE_ANALYZE: "Next: Bundle →",
            STAGE_BUNDLE: "Next: Export →",
            STAGE_EXPORT: None,
        }
        back_label = back_labels.get(stage)
        next_label = next_labels.get(stage)
        self._back_btn.setText(back_label or "← Back")
        self._back_btn.setVisible(back_label is not None)
        self._fwd_btn.setText(next_label or "Next →")
        self._fwd_btn.setVisible(next_label is not None)

    def _on_bundles_completed(self, stats: dict) -> None:
        self.export_panel.update_stats(stats)

    def closeEvent(self, event) -> None:  # noqa: N802
        if hasattr(self, "analyze_panel"):
            self.analyze_panel.shutdown()

        if self._owns_analysis_db:
            self.analysis_db.close()
        if self._owns_metadata_db:
            self.metadata_db.close()

        super().closeEvent(event)
