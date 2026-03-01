"""Reusable metric card widget for pipeline dashboard panels."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout


def create_metric_card(theme_colors, title: str, value: str, font_size: int = 26) -> QFrame:
    """Create a metric card with title and value"""
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
        font-size: {font_size}pt;
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
