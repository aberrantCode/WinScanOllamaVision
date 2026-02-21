"""
Collection Status Tab Helper Methods
Contains all UI creation methods for the Collection Status tab of Analysis Status Window
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.styles import (
    Colors,
    get_button_style,
    get_distribution_bar_style,
    get_progress_bar_style,
)


def create_metric_card(theme_colors, title: str, value: str) -> QFrame:
    """Create a metric card with title and value"""
    from PyQt6.QtWidgets import QSizePolicy

    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background-color: {theme_colors["bg_tertiary"]};
            border: 1px solid {theme_colors["border"]};
            border-radius: 8px;
        }}
    """)
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 12, 12, 12)
    card_layout.setSpacing(2)

    # Value first — the answer — large and primary
    value_label = QLabel(value)
    value_label.setObjectName(f"{title.lower().replace(' ', '_')}_value")
    value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    value_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    value_label.setStyleSheet(f"""
        color: {theme_colors["text_primary"]};
        font-size: 26pt;
        font-weight: 700;
        background-color: transparent;
        border: none;
    """)
    card_layout.addWidget(value_label)

    # Title below — context — small and quiet
    title_label = QLabel(title)
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setWordWrap(True)
    title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    title_label.setStyleSheet(f"""
        color: {theme_colors["text_tertiary"]};
        font-size: 8pt;
        font-weight: 500;
        background-color: transparent;
        border: none;
        letter-spacing: 0.5px;
    """)
    card_layout.addWidget(title_label)

    return card


def create_funnel_widget(theme_colors) -> tuple:
    """Create analysis completion funnel with progress bars
    Returns: (widget, funnel_bars_dict)
    """
    frame = QFrame()
    frame.setStyleSheet("""
        QFrame {
            background-color: transparent;
            border: none;
            padding: 16px;
        }
    """)
    layout = QVBoxLayout(frame)
    layout.setSpacing(12)

    # Title - no border
    title = QLabel("Pipeline Progress")
    title.setStyleSheet(
        f"font-size: 11pt; font-weight: 600; color: {theme_colors['text_primary']}; background-color: transparent; border: none;"
    )
    layout.addWidget(title)

    # Store funnel bars for updating
    funnel_bars = {}

    # Create 5 progress bars with funnel effect (progressively narrower)
    funnel_stages = [
        ("files_detected", "Detected", 100),  # 100% width
        ("files_analyzed", "Analyzed", 85),  # 85% width
        ("high_confidence", "High Confidence", 70),  # 70% width
        ("pages_bundled", "Bundled", 55),  # 55% width
        ("documents_archived", "Archived", 40),  # 40% width
    ]

    for key, stage_name, width_percent in funnel_stages:
        # Outer container for centering
        outer_container = QWidget()
        outer_container.setStyleSheet("background-color: transparent; border: none;")
        outer_layout = QHBoxLayout(outer_container)
        outer_layout.setContentsMargins(0, 0, 0, 2)  # Reduced spacing between items
        outer_layout.setSpacing(0)

        # Add stretch on both sides for centering
        outer_layout.addStretch()

        # Inner container with progressively smaller width
        bar_container = QWidget()
        bar_container.setStyleSheet("background-color: transparent; border: none;")
        bar_layout = QVBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(4)

        # Label with count and percentage - no border
        bar_label = QLabel(f"{stage_name}: 0 (0%)")
        bar_label.setObjectName(f"{key}_label")
        bar_label.setStyleSheet(
            f"color: {theme_colors['text_secondary']}; font-size: 11pt; font-weight: 600; background-color: transparent; border: none;"
        )
        bar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar_layout.addWidget(bar_label)

        # Progress bar
        bar = QProgressBar()
        bar.setObjectName(f"{key}_bar")
        bar.setMaximum(100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(20)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {theme_colors["bg_tertiary"]};
                border: 1px solid {theme_colors["border"]};
                border-radius: 10px;
            }}
            QProgressBar::chunk {{
                background-color: #3B82F6;
                border-radius: 10px;
            }}
        """)
        bar_layout.addWidget(bar)

        # Set maximum width based on funnel position (progressively narrower)
        max_width = int(400 * (width_percent / 100))
        bar_container.setMaximumWidth(max_width)

        outer_layout.addWidget(bar_container)
        outer_layout.addStretch()

        funnel_bars[key] = {"label": bar_label, "bar": bar, "stage_name": stage_name}
        layout.addWidget(outer_container)

    return frame, funnel_bars


def create_speed_eta_widget(theme_colors) -> tuple:
    """Create processing speed and ETA display
    Returns: (widget, speed_label, eta_label)
    """
    frame = QFrame()
    frame.setStyleSheet("""
        QFrame {
            background-color: transparent;
            border: none;
            padding: 12px 16px;
        }
    """)
    layout = QHBoxLayout(frame)
    layout.setSpacing(20)

    # Speed label
    speed_label = QLabel("Processing Speed: -- pages/min")
    speed_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent; border: none;"
    )
    layout.addWidget(speed_label)

    layout.addStretch()

    # ETA label
    eta_label = QLabel("ETA: --")
    eta_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent; border: none;"
    )
    layout.addWidget(eta_label)

    return frame, speed_label, eta_label


def create_action_item_row(theme_colors, text: str, button_text: str, callback) -> QWidget:
    """Create a single action item row with text and button"""
    row = QWidget()
    row.setStyleSheet("background-color: transparent; border: none;")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(12)

    # Text label
    text_label = QLabel(text)
    text_label.setObjectName("action_text")
    text_label.setWordWrap(True)
    text_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent; border: none;"
    )
    row_layout.addWidget(text_label, 1)

    # Action button
    button = QPushButton(button_text)
    button.setObjectName("action_button")
    button.setStyleSheet(get_button_style("primary"))
    button.clicked.connect(callback)
    button.setFixedWidth(150)
    row_layout.addWidget(button)

    return row


def create_action_items_widget(theme_colors, action_callbacks) -> tuple:
    """Create action items panel with suggested actions
    Returns: (widget, action_items_list)
    """
    frame = QFrame()
    frame.setStyleSheet("""
        QFrame {
            background-color: transparent;
            border: none;
            padding: 16px;
        }
    """)
    layout = QVBoxLayout(frame)
    layout.setSpacing(12)

    # Title
    title = QLabel("Action Items")
    title.setStyleSheet(
        f"font-size: 11pt; font-weight: 600; color: {theme_colors['text_primary']}; background-color: transparent; border: none;"
    )
    layout.addWidget(title)

    # Store action items for dynamic updates
    action_items = []

    # Create action item rows
    items_data = [
        (
            "No files detected in configured directories.",
            "Start Analysis",
            action_callbacks["start_analysis"],
        ),
        ("0 errors detected.", "View Errors", action_callbacks["view_errors"]),
        (
            "Analysis complete.",
            "Create Bundles",
            action_callbacks["create_bundles"],
        ),
    ]

    for text_template, button_text, callback in items_data:
        item_widget = create_action_item_row(theme_colors, text_template, button_text, callback)
        action_items.append(item_widget)
        layout.addWidget(item_widget)

    return frame, action_items


def create_completeness_bar(theme_colors, key: str, label: str) -> QWidget:
    """Create a metadata completeness progress bar"""
    container = QWidget()
    container.setStyleSheet("background-color: transparent; border: none;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    # Label
    text_label = QLabel(f"{label}: 0%")
    text_label.setObjectName(f"{key}_completeness_label")
    text_label.setStyleSheet(
        f"color: {theme_colors['text_tertiary']}; font-size: 9pt; border: none;"
    )
    layout.addWidget(text_label)

    # Progress bar
    bar = QProgressBar()
    bar.setObjectName(f"{key}_completeness_bar")
    bar.setMaximum(100)
    bar.setValue(0)
    bar.setTextVisible(False)
    bar.setFixedHeight(12)
    bar.setStyleSheet(get_progress_bar_style(0))
    layout.addWidget(bar)

    # Store references
    container.label = text_label  # type: ignore[attr-defined]
    container.bar = bar  # type: ignore[attr-defined]

    return container


def create_quality_metrics_widget(theme_colors) -> tuple:
    """Create quality metrics section content
    Returns: (widget, avg_conf_label, error_rate_label, completeness_bars_dict)
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

    # Average confidence
    avg_confidence_label = QLabel("Average Confidence: --")
    avg_confidence_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; border: none;"
    )
    layout.addWidget(avg_confidence_label)

    # Error rate
    error_rate_label = QLabel("Error Rate: --")
    error_rate_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt;")
    layout.addWidget(error_rate_label)

    # Metadata completeness section
    completeness_label = QLabel("Metadata Completeness:")
    completeness_label.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; margin-top: 8px; border: none;"
    )
    layout.addWidget(completeness_label)

    # Store completeness bars
    completeness_bars = {}

    # Create completeness bars for each metadata field
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
    layout.setSpacing(4)

    percentage = (count / total * 100) if total > 0 else 0

    # Label with count
    text_label = QLabel(f"{label}: {count} ({percentage:.1f}%)")
    text_label.setStyleSheet(
        f"color: {theme_colors['text_tertiary']}; font-size: 9pt; border: none;"
    )
    layout.addWidget(text_label)

    # Progress bar
    bar = QProgressBar()
    bar.setMaximum(100)
    bar.setValue(int(percentage))
    bar.setTextVisible(False)
    bar.setFixedHeight(10)
    bar.setStyleSheet(get_distribution_bar_style())
    layout.addWidget(bar)

    return container


def create_document_insights_widget_split(theme_colors) -> tuple:
    """Create document insights section WITHOUT company distribution
    Returns: (widget, docs_created_label, pages_archived_label, avg_pages_label,
              bundle_acceptance_label, type_dist_container)
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

    # Summary labels
    docs_created_label = QLabel("Documents Created: 0")
    docs_created_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; border: none;"
    )
    layout.addWidget(docs_created_label)

    pages_archived_label = QLabel("Pages Archived: 0")
    pages_archived_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; border: none;"
    )
    layout.addWidget(pages_archived_label)

    avg_pages_label = QLabel("Avg Pages per Document: --")
    avg_pages_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; border: none;"
    )
    layout.addWidget(avg_pages_label)

    bundle_acceptance_label = QLabel("Bundle Acceptance Rate: --")
    bundle_acceptance_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; border: none;"
    )
    layout.addWidget(bundle_acceptance_label)

    # Type distribution
    type_dist_title = QLabel("Document Type Distribution:")
    type_dist_title.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; margin-top: 12px; border: none;"
    )
    layout.addWidget(type_dist_title)

    type_distribution_container = QWidget()
    type_distribution_layout = QVBoxLayout(type_distribution_container)
    type_distribution_layout.setContentsMargins(0, 0, 0, 0)
    type_distribution_layout.setSpacing(6)
    layout.addWidget(type_distribution_container)
    type_distribution_container.layout = type_distribution_layout  # type: ignore[method-assign,assignment]

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

    # Company distribution
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
    company_distribution_container.layout = company_distribution_layout  # type: ignore[method-assign,assignment]

    return (widget, company_distribution_container)


def create_document_insights_widget(theme_colors) -> tuple:
    """Create document insights section content
    Returns: (widget, docs_created_label, pages_archived_label, avg_pages_label,
              bundle_acceptance_label, type_dist_container, company_dist_container)
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

    # Summary labels
    docs_created_label = QLabel("Documents Created: 0")
    docs_created_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt;")
    layout.addWidget(docs_created_label)

    pages_archived_label = QLabel("Pages Archived: 0")
    pages_archived_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt;")
    layout.addWidget(pages_archived_label)

    avg_pages_label = QLabel("Avg Pages per Document: --")
    avg_pages_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt;")
    layout.addWidget(avg_pages_label)

    bundle_acceptance_label = QLabel("Bundle Acceptance Rate: --")
    bundle_acceptance_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; border: none;"
    )
    layout.addWidget(bundle_acceptance_label)

    # Type distribution
    type_dist_title = QLabel("Document Type Distribution:")
    type_dist_title.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; margin-top: 12px; border: none;"
    )
    layout.addWidget(type_dist_title)

    type_distribution_container = QWidget()
    type_distribution_layout = QVBoxLayout(type_distribution_container)
    type_distribution_layout.setContentsMargins(0, 0, 0, 0)
    type_distribution_layout.setSpacing(6)
    layout.addWidget(type_distribution_container)
    type_distribution_container.layout = type_distribution_layout  # type: ignore[method-assign,assignment]

    # Company distribution
    company_dist_title = QLabel("Top 5 Companies:")
    company_dist_title.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; margin-top: 12px; border: none;"
    )
    layout.addWidget(company_dist_title)

    company_distribution_container = QWidget()
    company_distribution_layout = QVBoxLayout(company_distribution_container)
    company_distribution_layout.setContentsMargins(0, 0, 0, 0)
    company_distribution_layout.setSpacing(6)
    layout.addWidget(company_distribution_container)
    company_distribution_container.layout = company_distribution_layout  # type: ignore[method-assign,assignment]

    return (
        widget,
        docs_created_label,
        pages_archived_label,
        avg_pages_label,
        bundle_acceptance_label,
        type_distribution_container,
        company_distribution_container,
    )


def create_collapsible_section(
    theme_colors, title: str, content: QWidget, initially_expanded: bool = True
) -> QWidget:
    """Create a collapsible section with expand/collapse functionality"""
    from PyQt6.QtWidgets import QSizePolicy

    container = QWidget()
    container.setStyleSheet("background-color: transparent; border: none;")
    # Allow container to shrink when collapsed
    container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

    main_layout = QVBoxLayout(container)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)  # No spacing - seamless connection

    # Header frame (clickable) - rounded top, sharp bottom for seamless connection
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
    header_layout.setContentsMargins(12, 8, 12, 8)  # Reduced from 16,12,16,12

    # Title label - no border
    title_label = QLabel(title)
    title_label.setStyleSheet(
        f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; background-color: transparent; border: none;"
    )
    header_layout.addWidget(title_label)

    header_layout.addStretch()

    # Toggle button
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

    # Wrap content in a seamless frame with solid background
    # Sharp top corners connect to header, rounded bottom corners
    from PyQt6.QtWidgets import QFrame as QFrameWidget

    content_frame = QFrameWidget()
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
    content_layout.setContentsMargins(12, 8, 12, 12)  # Padding for content
    content_layout.setSpacing(0)
    content_layout.addWidget(content)

    # Content visibility
    content_frame.setVisible(initially_expanded)

    # Toggle function - adjust container size when toggling
    def toggle_section():
        is_visible = content_frame.isVisible()
        content_frame.setVisible(not is_visible)
        toggle_btn.setText("▶" if is_visible else "▼")
        # Update container size hint
        container.updateGeometry()

    header.mousePressEvent = lambda event: toggle_section()  # type: ignore[method-assign,assignment]
    toggle_btn.clicked.connect(toggle_section)

    main_layout.addWidget(header)
    main_layout.addWidget(content_frame)

    return container


def create_analysis_progress_frame(
    theme_colors, is_dark_mode, stop_callback, abort_callback
) -> tuple:
    """Create real-time analysis progress display
    Returns: (frame, current_file_label, progress_bar, stats_label, elapsed_label, stop_btn, abort_btn)
    """
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {"#2D4A6E" if is_dark_mode else "#F0F9FF"};
            border: 2px solid {"#4A6FA5" if is_dark_mode else "#BFDBFE"};
            border-radius: 10px;
            padding: 16px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setSpacing(10)

    # Title
    title = QLabel("Analysis in Progress")
    title.setStyleSheet(
        f"font-size: 11pt; font-weight: 600; color: {Colors.PRIMARY}; background-color: transparent; border: none;"
    )
    layout.addWidget(title)

    # Current file
    current_file_label = QLabel("Current: --")
    current_file_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent; border: none;"
    )
    current_file_label.setWordWrap(True)
    layout.addWidget(current_file_label)

    # Progress bar
    progress_bar = QProgressBar()
    progress_bar.setStyleSheet(f"""
        QProgressBar {{
            border: 1px solid {theme_colors["border"]};
            border-radius: 6px;
            background-color: {theme_colors["bg_secondary"]};
            height: 24px;
            text-align: center;
            color: {theme_colors["text_primary"]};
            font-weight: 600;
        }}
        QProgressBar::chunk {{
            background-color: {Colors.PRIMARY};
            border-radius: 6px;
        }}
    """)
    layout.addWidget(progress_bar)

    # Stats row
    stats_layout = QHBoxLayout()
    stats_label = QLabel("Analyzed: 0 | Cached: 0 | Errors: 0")
    stats_label.setStyleSheet(
        f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent; border: none;"
    )
    stats_layout.addWidget(stats_label)

    stats_layout.addStretch()

    elapsed_label = QLabel("Elapsed: 0s")
    elapsed_label.setStyleSheet(
        f"color: {theme_colors['text_tertiary']}; font-size: 9pt; background-color: transparent; border: none;"
    )
    stats_layout.addWidget(elapsed_label)

    layout.addLayout(stats_layout)

    # Buttons
    buttons_layout = QHBoxLayout()

    stop_button = QPushButton("Stop Analysis")
    stop_button.setStyleSheet(get_button_style("secondary"))
    stop_button.clicked.connect(stop_callback)
    buttons_layout.addWidget(stop_button)

    abort_button = QPushButton("Abort Analysis")
    abort_button.setStyleSheet(get_button_style("danger"))
    abort_button.clicked.connect(abort_callback)
    buttons_layout.addWidget(abort_button)

    buttons_layout.addStretch()

    layout.addLayout(buttons_layout)

    return (
        frame,
        current_file_label,
        progress_bar,
        stats_label,
        elapsed_label,
        stop_button,
        abort_button,
    )
