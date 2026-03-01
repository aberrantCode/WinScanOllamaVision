"""
UI builder functions for the Collection Status tab of the Analyze panel.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.pipeline.metric_card import create_metric_card
from ui.theme.styles import (
    get_distribution_bar_style,
    get_progress_bar_style,
)


def create_completeness_bar(theme_colors, key: str, label: str) -> QWidget:
    """Create a metadata completeness progress bar"""
    container = QWidget()
    container.setStyleSheet("background-color: transparent; border: none;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    text_label = QLabel(f"{label}: 0%")
    text_label.setObjectName(f"{key}_completeness_label")
    text_label.setStyleSheet(
        f"color: {theme_colors['text_tertiary']}; font-size: 9pt; border: none;"
    )
    layout.addWidget(text_label)

    bar = QProgressBar()
    bar.setObjectName(f"{key}_completeness_bar")
    bar.setMaximum(100)
    bar.setValue(0)
    bar.setTextVisible(False)
    bar.setFixedHeight(10)
    bar.setStyleSheet(get_progress_bar_style(0))
    layout.addWidget(bar)

    container.label = text_label  # type: ignore[attr-defined]
    container.bar = bar  # type: ignore[attr-defined]

    return container


def create_quality_metrics_widget(theme_colors) -> tuple:
    """Create quality metrics section content.

    Returns: (widget, avg_conf_label, error_rate_label, completeness_bars_dict)
    The returned labels are the *value* labels inside their metric cards.
    """
    widget = QWidget()
    widget.setStyleSheet(f"""
        QWidget {{
            background-color: {theme_colors["bg_secondary"]};
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)

    # Scalar metrics as compact cards
    cards_row = QHBoxLayout()
    cards_row.setSpacing(8)
    avg_conf_card = create_metric_card(theme_colors, "Avg Confidence", "—", font_size=16)
    error_rate_card = create_metric_card(theme_colors, "Error Rate", "—", font_size=16)
    avg_confidence_label = avg_conf_card.findChild(QLabel, "avg_confidence_value")
    error_rate_label = error_rate_card.findChild(QLabel, "error_rate_value")
    cards_row.addWidget(avg_conf_card)
    cards_row.addWidget(error_rate_card)
    layout.addLayout(cards_row)

    completeness_label = QLabel("Metadata Completeness")
    completeness_label.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 10pt; font-weight: 600;"
        " margin-top: 4px; border: none;"
    )
    layout.addWidget(completeness_label)

    completeness_bars = {}
    metadata_fields = [
        ("company", "Company"),
        ("document_type", "Document Type"),
        ("document_date", "Document Date"),
        ("page_number", "Page Number"),
    ]
    for key, label in metadata_fields:
        bar_widget = create_completeness_bar(theme_colors, key, label)
        completeness_bars[key] = bar_widget
        layout.addWidget(bar_widget)

    return widget, avg_confidence_label, error_rate_label, completeness_bars


def create_distribution_bar(theme_colors, label: str, count: int, total: int) -> QWidget:
    """Create a distribution bar for document insights"""
    container = QWidget()
    container.setStyleSheet("background-color: transparent; border: none;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    percentage = (count / total * 100) if total > 0 else 0

    text_label = QLabel(f"{label}: {count} ({percentage:.1f}%)")
    text_label.setStyleSheet(
        f"color: {theme_colors['text_tertiary']}; font-size: 9pt; border: none;"
    )
    layout.addWidget(text_label)

    bar = QProgressBar()
    bar.setMaximum(100)
    bar.setValue(int(percentage))
    bar.setTextVisible(False)
    bar.setFixedHeight(10)
    bar.setStyleSheet(get_distribution_bar_style())
    layout.addWidget(bar)

    return container


def create_document_insights_widget_split(theme_colors) -> tuple:
    """Create document insights section WITHOUT company distribution.

    Returns: (widget, docs_created_label, pages_archived_label, avg_pages_label,
              bundle_acceptance_label, type_dist_container)
    The returned labels are the *value* labels inside their metric cards.
    """
    widget = QWidget()
    widget.setStyleSheet(f"""
        QWidget {{
            background-color: {theme_colors["bg_secondary"]};
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)

    # Row 1: Docs Created, Pages Archived
    row1 = QHBoxLayout()
    row1.setSpacing(8)
    docs_card = create_metric_card(theme_colors, "Docs Created", "0", font_size=16)
    pages_card = create_metric_card(theme_colors, "Pages Archived", "0", font_size=16)
    docs_created_label = docs_card.findChild(QLabel, "docs_created_value")
    pages_archived_label = pages_card.findChild(QLabel, "pages_archived_value")
    row1.addWidget(docs_card)
    row1.addWidget(pages_card)
    layout.addLayout(row1)

    # Row 2: Avg Pages / Doc, Bundle Acceptance
    row2 = QHBoxLayout()
    row2.setSpacing(8)
    avg_card = create_metric_card(theme_colors, "Avg Pages / Doc", "—", font_size=16)
    bundle_card = create_metric_card(theme_colors, "Bundle Acceptance", "—", font_size=16)
    avg_pages_label = avg_card.findChild(QLabel, "avg_pages_/_doc_value")
    bundle_acceptance_label = bundle_card.findChild(QLabel, "bundle_acceptance_value")
    row2.addWidget(avg_card)
    row2.addWidget(bundle_card)
    layout.addLayout(row2)

    type_dist_title = QLabel("Document Types")
    type_dist_title.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 10pt; font-weight: 600;"
        " margin-top: 4px; border: none;"
    )
    layout.addWidget(type_dist_title)

    type_distribution_container = QWidget()
    type_distribution_layout = QVBoxLayout(type_distribution_container)
    type_distribution_layout.setContentsMargins(0, 0, 0, 0)
    type_distribution_layout.setSpacing(4)
    layout.addWidget(type_distribution_container)
    type_distribution_container._stored_layout = type_distribution_layout  # type: ignore[attr-defined]

    return (
        widget,
        docs_created_label,
        pages_archived_label,
        avg_pages_label,
        bundle_acceptance_label,
        type_distribution_container,
    )


def create_company_insights_widget(theme_colors) -> tuple:
    """Create company insights section (company distribution only)
    Returns: (widget, company_dist_container)
    """
    widget = QWidget()
    widget.setStyleSheet(f"""
        QWidget {{
            background-color: {theme_colors["bg_secondary"]};
            border-radius: 8px;
        }}
    """)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)

    company_dist_title = QLabel("Top 5 Companies:")
    company_dist_title.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; border: none;"
    )
    layout.addWidget(company_dist_title)

    company_distribution_container = QWidget()
    company_distribution_layout = QVBoxLayout(company_distribution_container)
    company_distribution_layout.setContentsMargins(0, 0, 0, 0)
    company_distribution_layout.setSpacing(6)
    layout.addWidget(company_distribution_container)
    company_distribution_container._stored_layout = company_distribution_layout  # type: ignore[attr-defined]

    return (widget, company_distribution_container)


def create_collapsible_section(
    theme_colors, title: str, content: QWidget, initially_expanded: bool = True
) -> QWidget:
    """Create a collapsible section with expand/collapse functionality"""
    container = QWidget()
    container.setStyleSheet("background-color: transparent; border: none;")
    container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    main_layout = QVBoxLayout(container)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    header = QFrame()
    header.setCursor(Qt.CursorShape.PointingHandCursor)
    header.setStyleSheet(f"""
        QFrame {{
            background-color: {theme_colors["bg_tertiary"]};
            border: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        }}
        QFrame:hover {{
            background-color: {theme_colors["tab_hover_bg"]};
        }}
    """)
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(12, 8, 12, 8)

    title_label = QLabel(title)
    title_label.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600;"
        " background-color: transparent; border: none;"
    )
    header_layout.addWidget(title_label)
    header_layout.addStretch()

    toggle_btn = QPushButton("▼" if initially_expanded else "▶")
    toggle_btn.setObjectName("toggle_btn")
    toggle_btn.setFixedSize(24, 24)
    toggle_btn.setStyleSheet("""
        QPushButton {
            background-color: transparent;
            border: none;
            font-size: 12pt;
            padding: 0px;
        }
    """)
    header_layout.addWidget(toggle_btn)

    content_frame = QFrame()
    content_frame.setStyleSheet(f"""
        QFrame {{
            background-color: {theme_colors["bg_secondary"]};
            border: none;
            border-top-left-radius: 0px;
            border-top-right-radius: 0px;
            border-bottom-left-radius: 8px;
            border-bottom-right-radius: 8px;
        }}
    """)
    content_layout = QVBoxLayout(content_frame)
    content_layout.setContentsMargins(12, 8, 12, 12)
    content_layout.setSpacing(0)
    content_layout.addWidget(content)
    content_frame.setVisible(initially_expanded)

    def toggle_section():
        is_visible = content_frame.isVisible()
        content_frame.setVisible(not is_visible)
        toggle_btn.setText("▶" if is_visible else "▼")
        container.updateGeometry()

    toggle_btn.clicked.connect(toggle_section)
    # Clicking anywhere on the header toggles the section
    header.mousePressEvent = lambda event: toggle_section()  # type: ignore[assignment]

    main_layout.addWidget(header)
    main_layout.addWidget(content_frame)

    return container
