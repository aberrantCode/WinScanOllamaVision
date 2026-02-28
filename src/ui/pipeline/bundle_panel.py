"""
Stage 3: Bundle panel — review AI bundle suggestions and approve PDFs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from ui.bundle.bundle_review_widget import BundleReviewWidget

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from services.bundling_service import BundlingService
from services.logging_service import get_logger
from ui.theme.theme_manager import ThemeManager


class BundlePanel(QWidget):
    """
    Stage 3: Bundle — review AI bundle suggestions and approve PDFs.

    Embeds BundleReviewWidget directly as a child widget so the operator
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
        self._embedded_workflow: BundleReviewWidget | None = None

        self._content_stack: QStackedWidget | None = None
        self._placeholder_page: QWidget | None = None
        self._bundle_stats_widget: QWidget | None = None
        # Stat labels updated by update_bundle_stats()
        self._stat_bundles_lbl: QLabel | None = None
        self._stat_avg_pages_lbl: QLabel | None = None
        self._stat_doc_types_lbl: QLabel | None = None
        self._stat_completeness_lbl: QLabel | None = None

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

        # ── Stats grid (shown while bundles load / before workflow launches)
        self._bundle_stats_widget = self._build_stats_grid(c)
        ph_layout.addWidget(self._bundle_stats_widget)

        ph_layout.addStretch()
        self._placeholder_page = placeholder
        self._content_stack.addWidget(placeholder)  # index 0

        root.addWidget(self._content_stack, stretch=1)

    def _build_stats_grid(self, c: dict) -> QWidget:
        """Build a 2-column stats grid for the placeholder page."""
        from ui.pipeline.metric_card import create_metric_card

        grid = QWidget()
        grid.setStyleSheet("background-color: transparent;")
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        # Row 1: bundles ready, avg pages
        bundles_card = create_metric_card(c, "Bundles Ready", "—")
        avg_pages_card = create_metric_card(c, "Avg Pages / Doc", "—")
        self._stat_bundles_lbl = bundles_card.findChild(QLabel, "bundles_ready_value")
        self._stat_avg_pages_lbl = avg_pages_card.findChild(QLabel, "avg_pages_/_doc_value")
        row1.addWidget(bundles_card)
        row1.addWidget(avg_pages_card)

        # Row 2: doc types summary, metadata completeness
        doc_types_card = create_metric_card(c, "Document Types", "—")
        completeness_card = create_metric_card(c, "Metadata Complete", "—")
        self._stat_doc_types_lbl = doc_types_card.findChild(QLabel, "document_types_value")
        self._stat_completeness_lbl = completeness_card.findChild(QLabel, "metadata_complete_value")
        row2.addWidget(doc_types_card)
        row2.addWidget(completeness_card)

        outer = QVBoxLayout(grid)
        outer.setContentsMargins(0, 8, 0, 0)
        outer.setSpacing(8)
        outer.addLayout(row1)
        outer.addLayout(row2)
        return grid

    def update_bundle_stats(self, stats: dict) -> None:
        """Populate the stats grid from bundle data. Called when BundlePanel activates."""
        n_bundles = stats.get("total", 0)
        avg_pages = stats.get("avg_pages", 0.0)
        doc_types = stats.get("doc_types", {})
        completeness_pct = stats.get("completeness_pct", 0)

        if self._stat_bundles_lbl:
            self._stat_bundles_lbl.setText(str(n_bundles))
        if self._stat_avg_pages_lbl:
            self._stat_avg_pages_lbl.setText(f"{avg_pages:.1f}" if avg_pages else "—")
        if self._stat_doc_types_lbl:
            if doc_types:
                top = sorted(doc_types.items(), key=lambda x: -x[1])[:3]
                summary = ", ".join(f"{t} ({n})" for t, n in top)
                self._stat_doc_types_lbl.setText(summary)
            else:
                self._stat_doc_types_lbl.setText("—")
        if self._stat_completeness_lbl:
            self._stat_completeness_lbl.setText(f"{completeness_pct}%" if completeness_pct else "—")

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

        # Compute and display pre-load stats
        stats = self._compute_bundle_stats(bundles)
        self.update_bundle_stats(stats)

        self._load_embedded_workflow(bundles)

    def _compute_bundle_stats(self, bundles: list[dict]) -> dict:
        """Derive summary stats from bundle recommendations for the stats grid."""
        total = len(bundles)
        page_counts = [len(b.get("file_paths", [])) for b in bundles]
        avg_pages = sum(page_counts) / total if total else 0.0

        doc_types: dict[str, int] = {}
        fields_filled = 0
        fields_total = 0
        for b in bundles:
            dt = b.get("document_type") or "Unknown"
            doc_types[dt] = doc_types.get(dt, 0) + 1
            for field in ("company", "document_type", "document_date"):
                fields_total += 1
                if b.get(field):
                    fields_filled += 1

        completeness_pct = int(fields_filled / fields_total * 100) if fields_total else 0
        return {
            "total": total,
            "avg_pages": avg_pages,
            "doc_types": doc_types,
            "completeness_pct": completeness_pct,
        }

    def _load_embedded_workflow(self, bundles: list[dict]) -> None:
        """Create (or recreate) the embedded BundleReviewWidget."""
        from ui.bundle.bundle_review_widget import BundleReviewWidget

        # Remove previous workflow widget if present
        if self._embedded_workflow is not None and self._content_stack is not None:
            idx = self._content_stack.indexOf(self._embedded_workflow)
            if idx >= 0:
                self._content_stack.removeWidget(self._embedded_workflow)
            self._embedded_workflow.deleteLater()
            self._embedded_workflow = None

        workflow_bundles = self._prepare_bundles(bundles)

        workflow = BundleReviewWidget(
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
