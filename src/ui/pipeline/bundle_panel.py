"""
Stage 3: Bundle panel — review AI bundle suggestions and approve PDFs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from ui.guided_bundle_workflow import GuidedBundleWorkflow

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from services.bundling_service import BundlingService
from services.logging_service import get_logger
from ui.theme_manager import ThemeManager


class BundlePanel(QWidget):
    """
    Stage 3: Bundle — review AI bundle suggestions and approve PDFs.

    Embeds GuidedBundleWorkflow directly as a child widget so the operator
    never leaves the pipeline window.  A QStackedWidget switches between an
    empty-state placeholder and the live review UI.
    """

    back_requested = pyqtSignal()
    next_requested = pyqtSignal()
    bundles_completed = pyqtSignal(dict)  # workflow stats

    def __init__(
        self,
        analysis_db: AnalysisDB,
        metadata_db: MetadataDB,
        config_manager: ConfigManager,
        dark_mode: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.config_manager = config_manager
        self.dark_mode = dark_mode
        self._bundling_service = BundlingService(self.analysis_db)
        self._workflow_stats: dict = {}
        self._embedded_workflow: GuidedBundleWorkflow | None = None

        self._content_stack: QStackedWidget | None = None
        self._placeholder_page: QWidget | None = None

        self._build_ui()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Content area (placeholder or embedded workflow)
        self._content_stack = QStackedWidget()

        # Page 0: placeholder shown before bundles are loaded
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setContentsMargins(24, 24, 24, 24)
        ph_layout.setSpacing(12)

        c = self._c()

        title = QLabel("Bundle — Review AI suggestions and create PDFs")
        title.setStyleSheet(f"font-size: 11pt; font-weight: 600; color: {c['text_primary']};")
        ph_layout.addWidget(title)

        desc = QLabel(
            "The AI has grouped your analyzed images into document bundles. "
            "Navigate to this stage after running analysis to review them inline."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size: 9pt; color: {c['text_secondary']};")
        ph_layout.addWidget(desc)

        self._placeholder_status = QLabel("Loading bundles…")
        self._placeholder_status.setStyleSheet(
            f"font-size: 13pt; font-weight: 700; color: {c['text_primary']}; margin-top: 16px;"
        )
        ph_layout.addWidget(self._placeholder_status)

        ph_layout.addStretch()
        self._placeholder_page = placeholder
        self._content_stack.addWidget(placeholder)  # index 0

        root.addWidget(self._content_stack, stretch=1)

    def refresh_bundle_count(self) -> None:
        """Load bundles from the DB and (re)build the embedded workflow widget."""
        try:
            bundles = self._bundling_service.generate_bundle_recommendations()
        except Exception as e:
            get_logger().warning(f"[Pipeline BundlePanel] could not load bundles: {e}")
            self._placeholder_status.setText("Could not load bundles — see log for details.")
            if self._content_stack:
                self._content_stack.setCurrentIndex(0)
            return

        if not bundles:
            self._placeholder_status.setText(
                "No bundles found. Run analysis first, then return here."
            )
            if self._content_stack:
                self._content_stack.setCurrentIndex(0)
            return

        n = len(bundles)
        self._placeholder_status.setText(f"{n} bundle{'s' if n != 1 else ''} ready to review.")
        self._load_embedded_workflow(bundles)

    def _load_embedded_workflow(self, bundles: list[dict]) -> None:
        """Create (or recreate) the embedded GuidedBundleWorkflow widget."""
        from ui.guided_bundle_workflow import GuidedBundleWorkflow

        # Remove previous workflow widget if present
        if self._embedded_workflow is not None and self._content_stack is not None:
            idx = self._content_stack.indexOf(self._embedded_workflow)
            if idx >= 0:
                self._content_stack.removeWidget(self._embedded_workflow)
            self._embedded_workflow.deleteLater()
            self._embedded_workflow = None

        workflow_bundles = self._prepare_bundles(bundles)

        workflow = GuidedBundleWorkflow(
            bundles=workflow_bundles,
            start_index=0,
            prototype_mode=False,
            analysis_db=self.analysis_db,
            metadata_db=self.metadata_db,
            config_manager=self.config_manager,
            parent=self,
            embedded_mode=True,
        )
        workflow.workflow_completed.connect(self._on_workflow_completed)

        self._embedded_workflow = workflow
        if self._content_stack is None:
            return
        self._content_stack.addWidget(workflow)  # index 1
        self._content_stack.setCurrentWidget(workflow)

    def _on_workflow_completed(self, stats: dict) -> None:
        self._workflow_stats = stats
        self.bundles_completed.emit(stats)

    def _prepare_bundles(self, bundles: list[dict]) -> list[dict]:
        workflow_bundles = []
        for bundle in bundles:
            analyses = bundle.get("analyses", [])
            formatted = []
            for analysis in analyses:
                formatted.append(
                    {
                        "document_type": analysis.get("document_type"),
                        "company": analysis.get("company"),
                        "document_date": analysis.get("document_date"),
                        "page_number": analysis.get("page_number"),
                        "total_pages": analysis.get("total_pages"),
                        "rotation_needed": analysis.get("rotation_needed", "none"),
                        "confidence_score": analysis.get("confidence_score", 0.0),
                        "tax_related": analysis.get("tax_related", False),
                    }
                )
            workflow_bundles.append(
                {
                    "bundle_id": bundle.get("id"),
                    "company": bundle.get("company", ""),
                    "document_type": bundle.get("document_type", ""),
                    "document_date": bundle.get("document_date", ""),
                    "confidence_score": bundle.get("confidence_score", 0.0),
                    "file_paths": bundle.get("file_paths", []),
                    "analyses": formatted,
                }
            )
        return workflow_bundles
