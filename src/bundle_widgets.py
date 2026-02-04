"""
Bundle Suggestion Widgets for Phase 7
Card-based UI for displaying and managing AI-generated document bundle suggestions
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from typing import List, Dict, Any
import os
from styles import get_button_style


class BundleSuggestionCard(QFrame):
    """
    Card widget displaying a bundle suggestion with thumbnails and actions
    """
    accepted = pyqtSignal(dict)  # Emitted when bundle is accepted
    modified = pyqtSignal(dict)  # Emitted when user wants to modify
    rejected = pyqtSignal(dict)  # Emitted when bundle is rejected

    def __init__(self, bundle_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.bundle_data = bundle_data
        self._init_ui()

    def _init_ui(self):
        """Initialize the card UI"""
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)

        # Apply styling based on confidence
        confidence = self.bundle_data.get('confidence_score', 0.0)
        if confidence >= 0.8:
            border_color = "#059669"  # High confidence - green
            confidence_text = "HIGH CONFIDENCE"
            confidence_bg = "#D1FAE5"
        elif confidence >= 0.5:
            border_color = "#F59E0B"  # Medium confidence - amber
            confidence_text = "MEDIUM CONFIDENCE"
            confidence_bg = "#FEF3C7"
        else:
            border_color = "#EF4444"  # Low confidence - red
            confidence_text = "LOW CONFIDENCE"
            confidence_bg = "#FEE2E2"

        self.setStyleSheet(f"""
            BundleSuggestionCard {{
                border: 2px solid {border_color};
                border-radius: 8px;
                background-color: white;
                margin: 5px;
                padding: 10px;
            }}
        """)

        layout = QVBoxLayout(self)

        # Header with metadata and confidence badge
        header_layout = QHBoxLayout()

        # Document metadata
        metadata_layout = QVBoxLayout()

        doc_type = self.bundle_data.get('document_type', 'Unknown')
        company = self.bundle_data.get('company', 'Unknown')
        doc_date = self.bundle_data.get('document_date', 'N/A')
        page_count = len(self.bundle_data.get('file_paths', []))

        title_label = QLabel(f"<b>{doc_type}</b>")
        title_label.setStyleSheet("font-size: 14px;")
        metadata_layout.addWidget(title_label)

        company_label = QLabel(f"Company: {company}")
        company_label.setStyleSheet("font-size: 11px; color: #666;")
        metadata_layout.addWidget(company_label)

        date_label = QLabel(f"Date: {doc_date} • {page_count} page(s)")
        date_label.setStyleSheet("font-size: 11px; color: #666;")
        metadata_layout.addWidget(date_label)

        header_layout.addLayout(metadata_layout)
        header_layout.addStretch()

        # Confidence badge
        confidence_badge = QLabel(confidence_text)
        confidence_badge.setStyleSheet(f"""
            background-color: {confidence_bg};
            color: {border_color};
            font-weight: bold;
            font-size: 10px;
            padding: 5px 10px;
            border-radius: 12px;
        """)
        confidence_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(confidence_badge)

        layout.addLayout(header_layout)

        # Thumbnail strip
        thumbnail_layout = QHBoxLayout()
        thumbnail_layout.setSpacing(5)

        file_paths = self.bundle_data.get('file_paths', [])
        # Show up to 5 thumbnails
        for i, file_path in enumerate(file_paths[:5]):
            if os.path.exists(file_path):
                thumbnail = self._create_thumbnail(file_path, f"Page {i+1}")
                thumbnail_layout.addWidget(thumbnail)

        if len(file_paths) > 5:
            more_label = QLabel(f"+{len(file_paths) - 5} more")
            more_label.setStyleSheet("color: #666; font-size: 10px;")
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumbnail_layout.addWidget(more_label)

        thumbnail_layout.addStretch()
        layout.addLayout(thumbnail_layout)

        # Action buttons
        button_layout = QHBoxLayout()

        accept_button = QPushButton("✓ Accept")
        accept_button.setStyleSheet(get_button_style('success'))
        accept_button.clicked.connect(self._on_accept)
        button_layout.addWidget(accept_button)

        modify_button = QPushButton("✎ Modify")
        modify_button.setStyleSheet(get_button_style('primary'))
        modify_button.clicked.connect(self._on_modify)
        button_layout.addWidget(modify_button)

        reject_button = QPushButton("✗ Reject")
        reject_button.setStyleSheet(get_button_style('danger'))
        reject_button.clicked.connect(self._on_reject)
        button_layout.addWidget(reject_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _create_thumbnail(self, file_path: str, label_text: str) -> QWidget:
        """Create a thumbnail widget for a page"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(2)

        # Thumbnail image
        thumbnail_label = QLabel()
        thumbnail_label.setFixedSize(80, 100)
        thumbnail_label.setStyleSheet("""
            border: 1px solid #CCCCCC;
            background-color: #F8F8F8;
        """)
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    78, 98,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                thumbnail_label.setPixmap(scaled_pixmap)
            else:
                thumbnail_label.setText("No\nPreview")
                thumbnail_label.setStyleSheet("""
                    border: 1px solid #CCCCCC;
                    background-color: #F8F8F8;
                    color: #999;
                    font-size: 9px;
                """)
        except Exception as e:
            thumbnail_label.setText("Error")
            thumbnail_label.setStyleSheet("color: red; font-size: 9px;")

        container_layout.addWidget(thumbnail_label)

        # Page label
        page_label = QLabel(label_text)
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_label.setStyleSheet("font-size: 9px; color: #666;")
        container_layout.addWidget(page_label)

        return container

    def _on_accept(self):
        """Handle accept button click"""
        self.accepted.emit(self.bundle_data)

    def _on_modify(self):
        """Handle modify button click"""
        self.modified.emit(self.bundle_data)

    def _on_reject(self):
        """Handle reject button click"""
        self.rejected.emit(self.bundle_data)


class BundleSuggestionsView(QWidget):
    """
    Container widget for displaying all bundle suggestions
    """
    bundle_accepted = pyqtSignal(dict)
    bundle_modified = pyqtSignal(dict)
    bundle_rejected = pyqtSignal(dict)
    accept_all_high = pyqtSignal()  # Accept all high confidence bundles
    skip_to_manual = pyqtSignal()  # Skip to manual workflow

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bundle_cards = []
        self._init_ui()

    def _init_ui(self):
        """Initialize the view UI"""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("<h2>Document Bundle Suggestions</h2>")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Action buttons
        accept_all_btn = QPushButton("Accept All High Confidence")
        accept_all_btn.setStyleSheet(get_button_style('success'))
        accept_all_btn.clicked.connect(self.accept_all_high.emit)
        header_layout.addWidget(accept_all_btn)

        skip_btn = QPushButton("Review Manually")
        skip_btn.setStyleSheet(get_button_style('secondary'))
        skip_btn.clicked.connect(self.skip_to_manual.emit)
        header_layout.addWidget(skip_btn)

        layout.addLayout(header_layout)

        # Info text
        info_label = QLabel(
            "The AI has analyzed your scanned pages and suggests the following document groupings. "
            "Review each suggestion and choose to accept, modify, or reject."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; margin: 10px 0; font-size: 11px;")
        layout.addWidget(info_label)

        # Scroll area for cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container for cards
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        scroll_area.setWidget(self.cards_container)
        layout.addWidget(scroll_area)

    def set_bundles(self, bundles: List[Dict[str, Any]]):
        """Display bundle suggestions"""
        # Clear existing cards
        for card in self.bundle_cards:
            card.deleteLater()
        self.bundle_cards.clear()

        # Remove stretch before adding new cards
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new cards
        for bundle in bundles:
            card = BundleSuggestionCard(bundle)
            card.accepted.connect(self.bundle_accepted.emit)
            card.modified.connect(self.bundle_modified.emit)
            card.rejected.connect(self.bundle_rejected.emit)
            self.cards_layout.addWidget(card)
            self.bundle_cards.append(card)

        # Add stretch at the end
        self.cards_layout.addStretch()

    def get_bundle_count(self) -> int:
        """Get number of bundle cards displayed"""
        return len(self.bundle_cards)

    def get_high_confidence_bundles(self) -> List[Dict[str, Any]]:
        """Get all high confidence bundles (>= 0.8)"""
        return [
            card.bundle_data
            for card in self.bundle_cards
            if card.bundle_data.get('confidence_score', 0.0) >= 0.8
        ]
