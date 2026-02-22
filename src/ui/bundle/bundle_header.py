"""Bundle review header widget: bundle progress, stats, confidence badge."""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors


class BundleHeaderWidget(QWidget):
    """Top strip: title, bundle progress, confidence badge, and action stats."""

    def __init__(
        self,
        dark_mode: bool,
        bundle: dict,
        bundle_index: int,
        total_bundles: int,
        accepted: int,
        rejected: int,
        skipped: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._dark_mode = dark_mode
        self._build_ui()
        self.refresh(bundle, bundle_index, total_bundles, accepted, rejected, skipped)

    def _build_ui(self) -> None:
        theme = get_bundle_colors(self._dark_mode)
        self.setStyleSheet(f"background: {theme['bg_secondary']};")
        self.setFixedHeight(70)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(6)

        # Top row: title + stats
        top_row = QHBoxLayout()

        self._title_label = QLabel("📋 Verify Documents")
        self._title_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {theme['text_primary']}; "
            f"text-decoration: none; background: transparent;"
        )
        top_row.addWidget(self._title_label)
        top_row.addStretch()

        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(f"color: {theme['text_secondary']}; font-size: 13px;")
        top_row.addWidget(self._stats_label)
        layout.addLayout(top_row)

        # Bottom row: progress + bundle info + confidence badge
        bottom_row = QHBoxLayout()

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-weight: 600; font-size: 13px; "
            f"text-decoration: none; background: transparent; border: none;"
        )
        bottom_row.addWidget(self._progress_label)
        bottom_row.addStretch()

        self._bundle_info_label = QLabel("")
        self._bundle_info_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-size: 13px; background: transparent;"
        )
        bottom_row.addWidget(self._bundle_info_label)

        self._confidence_badge = QLabel("")
        bottom_row.addWidget(self._confidence_badge)

        layout.addLayout(bottom_row)

    def refresh(
        self,
        bundle: dict,
        bundle_index: int,
        total_bundles: int,
        accepted: int,
        rejected: int,
        skipped: int,
    ) -> None:
        """Update all displayed text and confidence badge."""
        theme = get_bundle_colors(self._dark_mode)

        self._progress_label.setText(f"Bundle {bundle_index + 1} of {total_bundles}")

        doc_type = bundle.get("document_type", "Unknown").title()
        company = bundle.get("company", "Unknown").title()
        pages = len(bundle.get("file_paths", []))
        self._bundle_info_label.setText(f"<b>{doc_type}</b> - {company} ({pages} pages)")

        confidence = bundle.get("confidence_score", 0.0)
        confidence_pct = int(confidence * 100)
        if confidence >= 0.8:
            badge_color = theme["success"]
        elif confidence >= 0.5:
            badge_color = theme["warning"]
        else:
            badge_color = theme["danger"]
        self._confidence_badge.setText(f"{confidence_pct}%")
        self._confidence_badge.setStyleSheet(
            f"background: {badge_color}; color: white; padding: 4px 10px; "
            f"border-radius: 4px; font-weight: 600; font-size: 12px;"
        )

        stats_text = f"✓ {accepted} Accepted  •  ✗ {rejected} Rejected  •  ⏭ {skipped} Skipped"
        self._stats_label.setText(stats_text)

    def apply_theme(self, dark_mode: bool) -> None:
        """Re-apply colour styles for the new theme."""
        self._dark_mode = dark_mode
        theme = get_bundle_colors(dark_mode)
        self.setStyleSheet(f"background: {theme['bg_secondary']};")
        self._title_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {theme['text_primary']}; "
            f"text-decoration: none; background: transparent;"
        )
        self._stats_label.setStyleSheet(f"color: {theme['text_secondary']}; font-size: 13px;")
        self._progress_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-weight: 600; font-size: 13px; "
            f"text-decoration: none; background: transparent; border: none;"
        )
        self._bundle_info_label.setStyleSheet(
            f"color: {theme['text_primary']}; font-size: 13px; background: transparent;"
        )
