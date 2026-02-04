"""
Collection Status Tab Helper Methods
Contains all UI creation methods for the Collection Status tab of Analysis Status Window
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt
from styles import (
    Colors, get_button_style, get_metric_card_style, get_progress_bar_style,
    get_collapsible_section_style, get_action_items_panel_style,
    get_distribution_bar_style, show_information
)


def create_metric_card(theme_colors, title: str, value: str) -> QFrame:
    """Create a metric card with title and value"""
    card = QFrame()
    card.setStyleSheet(get_metric_card_style())
    card_layout = QVBoxLayout(card)
    card_layout.setSpacing(8)

    # Title label
    title_label = QLabel(title)
    title_label.setStyleSheet(f"""
        color: {theme_colors['text_tertiary']};
        font-size: 10pt;
        font-weight: 600;
        background-color: transparent;
    """)
    card_layout.addWidget(title_label)

    # Value label
    value_label = QLabel(value)
    value_label.setObjectName(f"{title.lower().replace(' ', '_')}_value")
    value_label.setStyleSheet(f"""
        color: {theme_colors['text_primary']};
        font-size: 24pt;
        font-weight: bold;
        background-color: transparent;
    """)
    card_layout.addWidget(value_label)

    return card


def create_funnel_widget(theme_colors) -> tuple:
    """Create analysis completion funnel with progress bars
    Returns: (widget, funnel_bars_dict)
    """
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {theme_colors['bg_secondary']};
            border: 1px solid {theme_colors['border']};
            border-radius: 8px;
            padding: 16px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setSpacing(12)

    # Title
    title = QLabel("Analysis Completion Funnel")
    title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {theme_colors['text_primary']}; background-color: transparent;")
    layout.addWidget(title)

    # Store funnel bars for updating
    funnel_bars = {}

    # Create 5 progress bars
    funnel_stages = [
        ("files_detected", "Files Detected"),
        ("files_analyzed", "Files Analyzed"),
        ("high_confidence", "High Confidence Results"),
        ("pages_bundled", "Pages Bundled"),
        ("documents_archived", "Documents Archived")
    ]

    for key, label in funnel_stages:
        bar_container = QWidget()
        bar_layout = QVBoxLayout(bar_container)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(4)

        # Label with count and percentage
        bar_label = QLabel(f"{label}: 0 (0%)")
        bar_label.setObjectName(f"{key}_label")
        bar_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent;")
        bar_layout.addWidget(bar_label)

        # Progress bar
        bar = QProgressBar()
        bar.setObjectName(f"{key}_bar")
        bar.setMaximum(100)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(16)
        bar.setStyleSheet(get_progress_bar_style(0))
        bar_layout.addWidget(bar)

        funnel_bars[key] = {'label': bar_label, 'bar': bar}
        layout.addWidget(bar_container)

    return frame, funnel_bars


def create_speed_eta_widget(theme_colors) -> tuple:
    """Create processing speed and ETA display
    Returns: (widget, speed_label, eta_label)
    """
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {theme_colors['bg_secondary']};
            border: 1px solid {theme_colors['border']};
            border-radius: 8px;
            padding: 12px 16px;
        }}
    """)
    layout = QHBoxLayout(frame)
    layout.setSpacing(20)

    # Speed label
    speed_label = QLabel("Processing Speed: -- pages/min")
    speed_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent;")
    layout.addWidget(speed_label)

    layout.addStretch()

    # ETA label
    eta_label = QLabel("ETA: --")
    eta_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent;")
    layout.addWidget(eta_label)

    return frame, speed_label, eta_label


def create_action_item_row(theme_colors, text: str, button_text: str, callback) -> QWidget:
    """Create a single action item row with text and button"""
    row = QWidget()
    row.setStyleSheet("background-color: transparent;")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(12)

    # Text label
    text_label = QLabel(text)
    text_label.setObjectName("action_text")
    text_label.setWordWrap(True)
    text_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent;")
    row_layout.addWidget(text_label, 1)

    # Action button
    button = QPushButton(button_text)
    button.setObjectName("action_button")
    button.setStyleSheet(get_button_style('primary'))
    button.clicked.connect(callback)
    button.setFixedWidth(150)
    row_layout.addWidget(button)

    return row


def create_action_items_widget(theme_colors, action_callbacks) -> tuple:
    """Create action items panel with suggested actions
    Returns: (widget, action_items_list)
    """
    frame = QFrame()
    frame.setStyleSheet(get_action_items_panel_style())
    layout = QVBoxLayout(frame)
    layout.setSpacing(12)

    # Title
    title = QLabel("Action Items")
    title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {theme_colors['text_primary']}; background-color: transparent;")
    layout.addWidget(title)

    # Store action items for dynamic updates
    action_items = []

    # Create action item rows
    items_data = [
        ("No files detected. Click to start analysis.", "Start Analysis", action_callbacks['start_analysis']),
        ("0 bundles suggested. Click to review.", "Review Bundles", action_callbacks['review_bundles']),
        ("0 errors detected. Click to view.", "View Errors", action_callbacks['view_errors']),
        ("Analysis complete. Create bundles for documents.", "Create Bundles", action_callbacks['create_bundles'])
    ]

    for text_template, button_text, callback in items_data:
        item_widget = create_action_item_row(theme_colors, text_template, button_text, callback)
        action_items.append(item_widget)
        layout.addWidget(item_widget)

    return frame, action_items


def create_completeness_bar(theme_colors, key: str, label: str) -> QWidget:
    """Create a metadata completeness progress bar"""
    container = QWidget()
    container.setStyleSheet("background-color: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    # Label
    text_label = QLabel(f"{label}: 0%")
    text_label.setObjectName(f"{key}_completeness_label")
    text_label.setStyleSheet(f"color: {theme_colors['text_tertiary']}; font-size: 9pt;")
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
    container.label = text_label
    container.bar = bar

    return container


def create_quality_metrics_widget(theme_colors) -> tuple:
    """Create quality metrics section content
    Returns: (widget, avg_conf_label, error_rate_label, completeness_bars_dict)
    """
    widget = QWidget()
    widget.setStyleSheet("background-color: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)

    # Average confidence
    avg_confidence_label = QLabel("Average Confidence: --")
    avg_confidence_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt;")
    layout.addWidget(avg_confidence_label)

    # Error rate
    error_rate_label = QLabel("Error Rate: --")
    error_rate_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt;")
    layout.addWidget(error_rate_label)

    # Metadata completeness section
    completeness_label = QLabel("Metadata Completeness:")
    completeness_label.setStyleSheet(f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; margin-top: 8px;")
    layout.addWidget(completeness_label)

    # Store completeness bars
    completeness_bars = {}

    # Create completeness bars for each metadata field
    metadata_fields = [
        ("company", "Company"),
        ("document_type", "Document Type"),
        ("document_date", "Document Date"),
        ("page_number", "Page Number")
    ]

    for key, label in metadata_fields:
        bar_widget = create_completeness_bar(theme_colors, key, label)
        completeness_bars[key] = bar_widget
        layout.addWidget(bar_widget)

    return widget, avg_confidence_label, error_rate_label, completeness_bars


def create_distribution_bar(theme_colors, label: str, count: int, total: int) -> QWidget:
    """Create a distribution bar for document insights"""
    container = QWidget()
    container.setStyleSheet("background-color: transparent;")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)

    percentage = (count / total * 100) if total > 0 else 0

    # Label with count
    text_label = QLabel(f"{label}: {count} ({percentage:.1f}%)")
    text_label.setStyleSheet(f"color: {theme_colors['text_tertiary']}; font-size: 9pt;")
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


def create_document_insights_widget(theme_colors) -> tuple:
    """Create document insights section content
    Returns: (widget, docs_created_label, pages_archived_label, avg_pages_label,
              bundle_acceptance_label, type_dist_container, company_dist_container)
    """
    widget = QWidget()
    widget.setStyleSheet("background-color: transparent;")
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
    bundle_acceptance_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt;")
    layout.addWidget(bundle_acceptance_label)

    # Type distribution
    type_dist_title = QLabel("Document Type Distribution:")
    type_dist_title.setStyleSheet(f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; margin-top: 12px;")
    layout.addWidget(type_dist_title)

    type_distribution_container = QWidget()
    type_distribution_layout = QVBoxLayout(type_distribution_container)
    type_distribution_layout.setContentsMargins(0, 0, 0, 0)
    type_distribution_layout.setSpacing(6)
    layout.addWidget(type_distribution_container)
    type_distribution_container.layout = type_distribution_layout  # Store reference

    # Company distribution
    company_dist_title = QLabel("Top 5 Companies:")
    company_dist_title.setStyleSheet(f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; margin-top: 12px;")
    layout.addWidget(company_dist_title)

    company_distribution_container = QWidget()
    company_distribution_layout = QVBoxLayout(company_distribution_container)
    company_distribution_layout.setContentsMargins(0, 0, 0, 0)
    company_distribution_layout.setSpacing(6)
    layout.addWidget(company_distribution_container)
    company_distribution_container.layout = company_distribution_layout  # Store reference

    return (widget, docs_created_label, pages_archived_label, avg_pages_label,
            bundle_acceptance_label, type_distribution_container, company_distribution_container)


def create_collapsible_section(theme_colors, title: str, content: QWidget) -> QWidget:
    """Create a collapsible section with expand/collapse functionality"""
    container = QWidget()
    container.setStyleSheet("background-color: transparent;")
    main_layout = QVBoxLayout(container)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    # Header frame (clickable)
    header = QFrame()
    header.setCursor(Qt.CursorShape.PointingHandCursor)
    header.setStyleSheet(get_collapsible_section_style())
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(16, 12, 16, 12)

    # Title label
    title_label = QLabel(title)
    title_label.setStyleSheet(f"color: {theme_colors['text_primary']}; font-size: 11pt; font-weight: 600; background-color: transparent;")
    header_layout.addWidget(title_label)

    header_layout.addStretch()

    # Toggle button
    toggle_btn = QPushButton("▼")
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

    # Content widget
    content.setVisible(True)  # Start expanded

    # Toggle function
    def toggle_section():
        is_visible = content.isVisible()
        content.setVisible(not is_visible)
        toggle_btn.setText("▶" if is_visible else "▼")

    header.mousePressEvent = lambda event: toggle_section()
    toggle_btn.clicked.connect(toggle_section)

    main_layout.addWidget(header)
    main_layout.addWidget(content)

    return container


def create_analysis_progress_frame(theme_colors, is_dark_mode, stop_callback, abort_callback) -> tuple:
    """Create real-time analysis progress display
    Returns: (frame, current_file_label, progress_bar, stats_label, elapsed_label, stop_btn, abort_btn)
    """
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background-color: {'#2D4A6E' if is_dark_mode else '#F0F9FF'};
            border: 2px solid {'#4A6FA5' if is_dark_mode else '#BFDBFE'};
            border-radius: 10px;
            padding: 16px;
        }}
    """)
    layout = QVBoxLayout(frame)
    layout.setSpacing(10)

    # Title
    title = QLabel("Analysis in Progress")
    title.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {Colors.PRIMARY if not is_dark_mode else '#90CAF9'}; background-color: transparent;")
    layout.addWidget(title)

    # Current file
    current_file_label = QLabel("Current: --")
    current_file_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent;")
    current_file_label.setWordWrap(True)
    layout.addWidget(current_file_label)

    # Progress bar
    progress_bar = QProgressBar()
    progress_bar.setStyleSheet(f"""
        QProgressBar {{
            border: 1px solid {theme_colors['border']};
            border-radius: 6px;
            background-color: {theme_colors['input_bg']};
            height: 24px;
            text-align: center;
            color: {theme_colors['text_primary']};
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
    stats_label.setStyleSheet(f"color: {theme_colors['text_secondary']}; font-size: 10pt; background-color: transparent;")
    stats_layout.addWidget(stats_label)

    stats_layout.addStretch()

    elapsed_label = QLabel("Elapsed: 0s")
    elapsed_label.setStyleSheet(f"color: {theme_colors['text_tertiary']}; font-size: 9pt; background-color: transparent;")
    stats_layout.addWidget(elapsed_label)

    layout.addLayout(stats_layout)

    # Buttons
    buttons_layout = QHBoxLayout()

    stop_button = QPushButton("Stop Analysis")
    stop_button.setStyleSheet(get_button_style('secondary'))
    stop_button.clicked.connect(stop_callback)
    buttons_layout.addWidget(stop_button)

    abort_button = QPushButton("Abort Analysis")
    abort_button.setStyleSheet(get_button_style('danger'))
    abort_button.clicked.connect(abort_callback)
    buttons_layout.addWidget(abort_button)

    buttons_layout.addStretch()

    layout.addLayout(buttons_layout)

    return frame, current_file_label, progress_bar, stats_label, elapsed_label, stop_button, abort_button
