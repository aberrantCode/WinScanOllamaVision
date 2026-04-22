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
        # Stat card labels updated by update_bundle_stats()
        self._stat_bundles_lbl: QLabel | None = None
        self._stat_avg_pages_lbl: QLabel | None = None
        self._stat_doc_types_lbl: QLabel | None = None
        self._stat_completeness_lbl: QLabel | None = None
        self._stat_pages_not_bundled_lbl: QLabel | None = None
        # Stat list containers updated by update_bundle_stats()
        self._stat_doc_type_dist_container: QWidget | None = None
        self._stat_status_dist_container: QWidget | None = None
        # Live review status labels (above analytics, updated via bundle_changed signal)
        self._placeholder_status: QLabel | None = None
        self._status_summary_lbl: QLabel | None = None
        self._bundle_info_lbl: QLabel | None = None
        self._confidence_lbl: QLabel | None = None
        self._build_ui()

    def _c(self) -> dict[str, str]:
        return ThemeManager.get_colors(self.dark_mode)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 8)
        root.setSpacing(8)

        c = self._c()

        # ── Title (mirrors analyze panel header)
        title = QLabel("Bundle — Review AI suggestions and create PDFs")
        title.setStyleSheet(f"font-size: 11pt; font-weight: 600; color: {c['text_primary']};")
        root.addWidget(title)

        # ── Status row: "Reviewing N out of M" (left) + "✓ N Accepted…" (right)
        status_row = QHBoxLayout()
        status_row.setSpacing(8)

        self._placeholder_status = QLabel("Loading bundles…")
        self._placeholder_status.setStyleSheet(f"font-size: 9pt; color: {c['text_secondary']};")
        status_row.addWidget(self._placeholder_status)
        status_row.addStretch()

        self._status_summary_lbl = QLabel("")
        self._status_summary_lbl.setStyleSheet(f"font-size: 9pt; color: {c['text_secondary']};")
        status_row.addWidget(self._status_summary_lbl)

        root.addLayout(status_row)

        # ── Bundle info row: doc + company + pages (left) + confidence badge (right)
        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        self._bundle_info_lbl = QLabel("")
        self._bundle_info_lbl.setStyleSheet(f"font-size: 9pt; color: {c['text_primary']};")
        info_row.addWidget(self._bundle_info_lbl)
        info_row.addStretch()

        self._confidence_lbl = QLabel("")
        info_row.addWidget(self._confidence_lbl)

        root.addLayout(info_row)

        # ── Analytics collapsible section — always visible, collapsed by default
        self._bundle_stats_widget = self._build_stats_grid(c)
        from ui.pipeline.analyze_status_helpers import create_collapsible_section

        c_ext = {**c, "tab_hover_bg": c.get("bg_hover", "#E5E7EB")}
        stats_section = create_collapsible_section(
            c_ext, "Analytics", self._bundle_stats_widget, initially_expanded=False
        )
        root.addWidget(stats_section)

        # ── Content area: empty placeholder until bundles load, then BundleReviewWidget
        self._content_stack = QStackedWidget()

        placeholder = QWidget()
        self._placeholder_page = placeholder
        self._content_stack.addWidget(placeholder)  # index 0

        root.addWidget(self._content_stack, stretch=1)

    def _build_stats_grid(self, c: dict) -> QWidget:
        """Build stats content: metric cards row + list sections row (mirrors analyze panel)."""
        from ui.pipeline.metric_card import create_metric_card

        grid = QWidget()
        grid.setStyleSheet("background-color: transparent;")
        outer = QVBoxLayout(grid)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(8)

        # ── Row 1: metric cards ────────────────────────────────────────
        bundles_card, self._stat_bundles_lbl = create_metric_card(
            c, "Bundles Ready", "—", font_size=16
        )
        avg_pages_card, self._stat_avg_pages_lbl = create_metric_card(
            c, "Avg Pages / Doc", "—", font_size=16
        )
        doc_types_card, self._stat_doc_types_lbl = create_metric_card(
            c, "Document Types", "—", font_size=16
        )
        completeness_card, self._stat_completeness_lbl = create_metric_card(
            c, "Metadata Complete", "—", font_size=16
        )
        not_bundled_card, self._stat_pages_not_bundled_lbl = create_metric_card(
            c, "Pages Not Bundled", "—", font_size=16
        )

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        for card in (
            bundles_card,
            avg_pages_card,
            doc_types_card,
            completeness_card,
            not_bundled_card,
        ):
            cards_row.addWidget(card, stretch=1)
        outer.addLayout(cards_row)

        # ── Row 2: list sections ───────────────────────────────────────

        def _list_section(title_text: str) -> tuple[QWidget, QWidget]:
            """Return (section_widget, items_container) with consistent styling."""
            section = QWidget()
            section.setStyleSheet(
                f"QWidget {{ background-color: {c['bg_secondary']}; border-radius: 8px; }}"
            )
            layout = QVBoxLayout(section)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(8)
            title_lbl = QLabel(title_text)
            title_lbl.setStyleSheet(
                f"color: {c['text_primary']}; font-size: 10pt; font-weight: 600; border: none;"
            )
            layout.addWidget(title_lbl)
            container = QWidget()
            container.setStyleSheet("background-color: transparent; border: none;")
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(4)
            container._stored_layout = container_layout  # type: ignore[attr-defined]
            layout.addWidget(container)
            layout.addStretch()
            return section, container

        doc_type_section, self._stat_doc_type_dist_container = _list_section("Document Types")
        status_section, self._stat_status_dist_container = _list_section("Bundle Status")

        lists_row = QHBoxLayout()
        lists_row.setSpacing(8)
        lists_row.addWidget(doc_type_section, stretch=1)
        lists_row.addWidget(status_section, stretch=1)
        outer.addLayout(lists_row)

        return grid

    def update_bundle_stats(self, stats: dict) -> None:
        """Populate the stats grid from bundle data. Called when BundlePanel activates."""

        from ui.pipeline.analyze_status_helpers import create_distribution_bar

        n_bundles = stats.get("total", 0)
        avg_pages = stats.get("avg_pages", 0.0)
        doc_types: dict[str, int] = stats.get("doc_types", {})
        completeness_pct = stats.get("completeness_pct", 0)
        pages_not_bundled = stats.get("pages_not_bundled", 0)
        status_counts: dict[str, int] = stats.get("status_counts", {})

        # ── Metric cards ──────────────────────────────────────────────
        if self._stat_bundles_lbl:
            self._stat_bundles_lbl.setText(str(n_bundles))
        if self._stat_avg_pages_lbl:
            self._stat_avg_pages_lbl.setText(f"{avg_pages:.1f}" if avg_pages else "—")
        if self._stat_doc_types_lbl:
            self._stat_doc_types_lbl.setText(str(len(doc_types)) if doc_types else "—")
        if self._stat_completeness_lbl:
            self._stat_completeness_lbl.setText(f"{completeness_pct}%" if completeness_pct else "—")
        if self._stat_pages_not_bundled_lbl:
            self._stat_pages_not_bundled_lbl.setText(str(pages_not_bundled))

        # ── Document Types list ───────────────────────────────────────
        if self._stat_doc_type_dist_container is not None:
            layout: QVBoxLayout = self._stat_doc_type_dist_container._stored_layout  # type: ignore[attr-defined]
            while layout.count():
                item = layout.takeAt(0)
                if item:
                    w = item.widget()
                    if w:
                        w.deleteLater()
            total_dt = sum(doc_types.values())
            for label, count in sorted(doc_types.items(), key=lambda x: -x[1])[:5]:
                layout.addWidget(create_distribution_bar(self._c(), label, count, total_dt))

        # ── Bundle Status list ────────────────────────────────────────
        if self._stat_status_dist_container is not None:
            layout2: QVBoxLayout = self._stat_status_dist_container._stored_layout  # type: ignore[attr-defined]
            while layout2.count():
                item = layout2.takeAt(0)
                if item:
                    w = item.widget()
                    if w:
                        w.deleteLater()
            for status_label in ("Accepted", "Rejected", "Skipped", "Not Reviewed"):
                count = status_counts.get(status_label, 0)
                layout2.addWidget(
                    create_distribution_bar(self._c(), status_label, count, n_bundles)
                )

    def refresh_bundle_count(self) -> None:
        """Load bundles from the DB and start the embedded review immediately.

        If the embedded review workflow is already running (e.g. user navigated
        away and back) we jump straight to it rather than rebuilding.
        """
        # If a workflow is already live, go directly to it.
        if self._embedded_workflow is not None and self._content_stack is not None:
            self._content_stack.setCurrentWidget(self._embedded_workflow)
            return

        if self._content_stack:
            self._content_stack.setCurrentIndex(0)

        try:
            bundles = self._bundling_service.generate_bundle_recommendations()
        except Exception as e:
            get_logger().warning(f"[Pipeline BundlePanel] could not load bundles: {e}")
            if self._placeholder_status:
                self._placeholder_status.setText("Could not load bundles — see log for details.")
            return

        if not bundles:
            if self._placeholder_status:
                self._placeholder_status.setText(
                    "No bundles found. Run analysis first, then return here."
                )
            return

        n = len(bundles)
        if self._placeholder_status:
            self._placeholder_status.setText(f"{n} bundle{'s' if n != 1 else ''} ready to review.")

        total_analyzed = 0
        try:
            total_analyzed = len(self.analysis_db.get_analyzed_pages())
        except Exception as e:
            get_logger().warning(f"[Pipeline BundlePanel] could not fetch analyzed page count: {e}")

        stats = self._compute_bundle_stats(bundles, total_analyzed)
        self.update_bundle_stats(stats)

        self._load_embedded_workflow(bundles)

    def _compute_bundle_stats(self, bundles: list[dict], total_analyzed: int = 0) -> dict:
        """Derive summary stats from bundle recommendations for the stats grid."""
        total = len(bundles)
        page_counts = [len(b.get("file_paths", [])) for b in bundles]
        avg_pages = sum(page_counts) / total if total else 0.0
        total_bundled = sum(page_counts)
        pages_not_bundled = max(0, total_analyzed - total_bundled)

        doc_types: dict[str, int] = {}
        fields_filled = 0
        fields_total = 0
        status_counts: dict[str, int] = {
            "Accepted": 0,
            "Rejected": 0,
            "Skipped": 0,
            "Not Reviewed": 0,
        }
        for b in bundles:
            dt = b.get("document_type") or "Unknown"
            doc_types[dt] = doc_types.get(dt, 0) + 1
            for field in ("company", "document_type", "document_date"):
                fields_total += 1
                if b.get(field):
                    fields_filled += 1
            raw_status = str(b.get("status") or b.get("decision") or "").lower()
            if raw_status in ("accepted", "approve", "approved"):
                status_counts["Accepted"] += 1
            elif raw_status in ("rejected", "reject"):
                status_counts["Rejected"] += 1
            elif raw_status in ("skipped", "skip"):
                status_counts["Skipped"] += 1
            else:
                status_counts["Not Reviewed"] += 1

        completeness_pct = int(fields_filled / fields_total * 100) if fields_total else 0
        return {
            "total": total,
            "avg_pages": avg_pages,
            "doc_types": doc_types,
            "completeness_pct": completeness_pct,
            "pages_not_bundled": pages_not_bundled,
            "status_counts": status_counts,
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
        workflow.bundle_changed.connect(self._on_bundle_changed)
        workflow.workflow_completed.connect(self._on_workflow_completed)

        self._embedded_workflow = workflow
        if self._content_stack is None:
            return
        self._content_stack.addWidget(workflow)  # index 1
        self._content_stack.setCurrentWidget(workflow)

        # Signal already fired during __init__ before connection was made; replay it.
        self._on_bundle_changed(
            workflow.current_bundle_index,
            len(workflow.bundles),
            workflow.bundles[workflow.current_bundle_index],
            len(workflow.accepted_bundles),
            len(workflow.rejected_bundles),
            len(workflow.skipped_bundles),
        )

    def _on_bundle_changed(
        self,
        bundle_index: int,
        total_bundles: int,
        bundle: dict,
        accepted: int,
        rejected: int,
        skipped: int,
    ) -> None:
        """Update status labels above the analytics panel when the active bundle changes."""
        if self._placeholder_status:
            self._placeholder_status.setText(f"Reviewing {bundle_index + 1} out of {total_bundles}")

        if self._status_summary_lbl:
            self._status_summary_lbl.setText(
                f"✓ {accepted} Accepted  •  ✗ {rejected} Rejected  •  ⏭ {skipped} Skipped"
            )

        if self._bundle_info_lbl:
            doc_type = (bundle.get("document_type") or "Unknown").title()
            company = (bundle.get("company") or "Unknown").title()
            pages = len(bundle.get("file_paths", []))
            self._bundle_info_lbl.setText(f"<b>{doc_type}</b> — {company} ({pages} pages)")

        if self._confidence_lbl:
            try:
                confidence = float(bundle.get("confidence_score") or 0.0)
            except (ValueError, TypeError):
                confidence = 0.0
            confidence_pct = int(confidence * 100)
            if confidence >= 0.8:
                badge_color = "#10B981"
            elif confidence >= 0.5:
                badge_color = "#F59E0B"
            else:
                badge_color = "#EF4444"
            self._confidence_lbl.setText(f"{confidence_pct}%")
            self._confidence_lbl.setStyleSheet(
                f"background: {badge_color}; color: white; padding: 3px 8px; "
                f"border-radius: 4px; font-weight: 600; font-size: 9pt;"
            )

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
