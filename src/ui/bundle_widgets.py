"""
Bundle Suggestion Widgets for Phase 7
Card-based UI for displaying and managing AI-generated document bundle suggestions
"""

import html
import os
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal"""

    clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event):  # noqa: N802
        self.clicked.emit()
        super().mousePressEvent(event)


class EnlargedPagesDialog(QDialog):
    """Dialog to display enlarged pages from a bundle with navigation"""

    def __init__(self, file_paths: list[str], analysis_db=None, parent=None):
        super().__init__(parent)
        self.file_paths = file_paths
        self.current_page_index = 0
        self.page_widgets: list[QWidget] = []  # Store references to page widgets for scrolling
        # Get analysis_db for metadata tooltips
        if analysis_db is None:
            from db.analysis_db import AnalysisDB

            self.analysis_db = AnalysisDB()
        else:
            self.analysis_db = analysis_db
        self.setWindowTitle("Bundle Pages - Enlarged View")
        self.setMinimumSize(800, 600)
        self._init_ui()

    def _init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout(self)

        # Header with navigation and close button
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel(f"<b>Bundle Pages</b> ({len(self.file_paths)} page(s))")
        title_label.setStyleSheet("font-size: 14px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)

        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #9CA3AF;
            }
        """)
        self.prev_button.clicked.connect(self._go_to_previous)
        self.prev_button.setEnabled(False)  # Disabled on first page
        nav_layout.addWidget(self.prev_button)

        self.page_indicator = QLabel(f"Page 1 of {len(self.file_paths)}")
        self.page_indicator.setStyleSheet("font-size: 12px; padding: 0 10px;")
        nav_layout.addWidget(self.page_indicator)

        self.next_button = QPushButton("Next ▶")
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #9CA3AF;
            }
        """)
        self.next_button.clicked.connect(self._go_to_next)
        self.next_button.setEnabled(len(self.file_paths) > 1)
        nav_layout.addWidget(self.next_button)

        header_layout.addLayout(nav_layout)
        header_layout.addSpacing(20)

        close_button = QPushButton("✕ Close")
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        close_button.clicked.connect(self.close)
        header_layout.addWidget(close_button)

        layout.addLayout(header_layout)

        # Scrollable area for pages
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Container for pages
        pages_container = QWidget()
        self.pages_layout = QHBoxLayout(pages_container)
        self.pages_layout.setSpacing(15)
        self.pages_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Add each page at 400px+ width
        for i, file_path in enumerate(self.file_paths):
            page_widget = self._create_enlarged_page(file_path, i + 1)
            self.pages_layout.addWidget(page_widget)
            self.page_widgets.append(page_widget)

        self.scroll_area.setWidget(pages_container)
        layout.addWidget(self.scroll_area)

    def _create_enlarged_page(self, file_path: str, page_num: int) -> QWidget:
        """Create an enlarged page widget scaled to fit dialog height"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(5)

        # Get metadata for tooltip
        metadata_tooltip = self._format_metadata_tooltip(file_path)

        # Page label
        page_label = QLabel(f"<b>Page {page_num}</b>")
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_label.setStyleSheet("font-size: 12px; color: #333;")
        page_label.setToolTip(metadata_tooltip)
        container_layout.addWidget(page_label)

        # Image label
        image_label = QLabel()
        image_label.setStyleSheet("""
            border: 2px solid #CCCCCC;
            background-color: #F8F8F8;
        """)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setToolTip(metadata_tooltip)

        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Calculate target height for maximized window
                # Leave room for header (~80px) + page label (~30px) + filename (~30px) + margins (~60px) = ~200px
                # For a 1080p display (1920x1080), this gives ~880px for image
                # Use 85% of screen height as target, which works well for most displays
                from PyQt6.QtWidgets import QApplication

                screen = QApplication.primaryScreen()
                if screen:
                    screen_height = screen.availableGeometry().height()
                    target_height = int(screen_height * 0.75)  # 75% of screen height
                else:
                    target_height = 800  # Fallback if screen info unavailable

                # Scale to fit height, maintaining aspect ratio
                scaled_pixmap = pixmap.scaledToHeight(
                    target_height, Qt.TransformationMode.SmoothTransformation
                )
                image_label.setPixmap(scaled_pixmap)
                image_label.setFixedSize(scaled_pixmap.size())
            else:
                image_label.setText("No Preview Available")
                image_label.setMinimumSize(400, 500)
                image_label.setStyleSheet("""
                    border: 2px solid #CCCCCC;
                    background-color: #F8F8F8;
                    color: #999;
                    font-size: 14px;
                """)
        except Exception as e:
            image_label.setText(f"Error loading image:\n{e}")
            image_label.setMinimumSize(400, 500)
            image_label.setStyleSheet("color: red; font-size: 12px;")

        container_layout.addWidget(image_label)

        # Filename label
        filename_label = QLabel(os.path.basename(file_path))
        filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        filename_label.setStyleSheet("font-size: 10px; color: #666;")
        filename_label.setWordWrap(True)
        container_layout.addWidget(filename_label)

        return container

    def _go_to_previous(self):
        """Navigate to previous page"""
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self._scroll_to_current_page()
            self._update_navigation()

    def _go_to_next(self):
        """Navigate to next page"""
        if self.current_page_index < len(self.file_paths) - 1:
            self.current_page_index += 1
            self._scroll_to_current_page()
            self._update_navigation()

    def _scroll_to_current_page(self):
        """Scroll to the current page"""
        if self.current_page_index < len(self.page_widgets):
            target_widget = self.page_widgets[self.current_page_index]
            # Scroll to make the target widget visible
            self.scroll_area.ensureWidgetVisible(target_widget)

    def _update_navigation(self):
        """Update navigation button states and page indicator"""
        self.prev_button.setEnabled(self.current_page_index > 0)
        self.next_button.setEnabled(self.current_page_index < len(self.file_paths) - 1)
        self.page_indicator.setText(f"Page {self.current_page_index + 1} of {len(self.file_paths)}")

    def _format_metadata_tooltip(self, file_path: str) -> str:
        """Format metadata from analysis database as a readable tooltip"""
        try:
            # Get analysis results from database
            analysis = self.analysis_db.get_analysis(file_path)
            if not analysis:
                return "No metadata available"

            # Extract metadata fields
            filename = os.path.basename(file_path)
            company = analysis.get("company") or "N/A"
            doc_type = analysis.get("document_type") or "N/A"
            doc_date = analysis.get("document_date") or "N/A"
            tax_related = "Yes" if analysis.get("tax_related") else "No"
            page_num = analysis.get("page_number") or "N/A"
            total_pages = analysis.get("total_pages") or "N/A"
            confidence = analysis.get("confidence_score", 0.0)
            legibility = analysis.get("legibility") or "N/A"
            rotation = analysis.get("rotation_needed") or "N/A"

            # Format as multi-line tooltip
            tooltip = f"""<b>{html.escape(filename)}</b><br>
<br>
<b>Document Info:</b><br>
• Company: {html.escape(str(company))}<br>
• Type: {html.escape(str(doc_type))}<br>
• Date: {html.escape(str(doc_date))}<br>
• Tax Related: {html.escape(str(tax_related))}<br>
<br>
<b>Page Info:</b><br>
• Page: {html.escape(str(page_num))} of {html.escape(str(total_pages))}<br>
• Legibility: {html.escape(str(legibility))}<br>
• Rotation: {html.escape(str(rotation))}<br>
• Confidence: {confidence:.1%}<br>
"""
            return tooltip
        except Exception as e:
            return f"Error loading metadata: {html.escape(str(e))}"

    def keyPressEvent(self, event):  # noqa: N802
        """Handle keyboard navigation"""
        from PyQt6.QtCore import Qt

        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_Up:
            self._go_to_previous()
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_Down:
            self._go_to_next()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


class BundleSuggestionCard(QFrame):
    """
    Card widget displaying a bundle suggestion with thumbnails and actions
    """

    accepted = pyqtSignal(dict)  # Emitted when bundle is accepted
    modified = pyqtSignal(dict)  # Emitted when user wants to modify
    rejected = pyqtSignal(dict)  # Emitted when bundle is rejected

    def __init__(self, bundle_data: dict[str, Any], parent=None):
        super().__init__(parent)
        self.bundle_data = bundle_data
        # Import here to avoid circular imports
        from db.analysis_db import AnalysisDB

        self.analysis_db = AnalysisDB()
        self._init_ui()

    def _init_ui(self):
        """Initialize the card UI"""
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(2)

        # Apply styling based on confidence
        confidence = self.bundle_data.get("confidence_score", 0.0)
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

        doc_type = self.bundle_data.get("document_type", "Unknown")
        company = self.bundle_data.get("company", "Unknown")
        doc_date = self.bundle_data.get("document_date", "N/A")
        page_count = len(self.bundle_data.get("file_paths", []))

        title_label = QLabel(f"<b>{html.escape(str(doc_type))}</b>")
        title_label.setStyleSheet("font-size: 14px;")
        metadata_layout.addWidget(title_label)

        company_label = QLabel(f"Company: {html.escape(str(company))}")
        company_label.setStyleSheet("font-size: 11px; color: #666;")
        metadata_layout.addWidget(company_label)

        date_label = QLabel(f"Date: {html.escape(str(doc_date))} • {page_count} page(s)")
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

        file_paths = self.bundle_data.get("file_paths", [])
        # Show up to 5 thumbnails
        for i, file_path in enumerate(file_paths[:5]):
            if os.path.exists(file_path):
                thumbnail = self._create_thumbnail(file_path, f"Page {i + 1}")
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
        accept_button.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        accept_button.clicked.connect(self._on_accept)
        button_layout.addWidget(accept_button)

        modify_button = QPushButton("✎ Modify")
        modify_button.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        modify_button.clicked.connect(self._on_modify)
        button_layout.addWidget(modify_button)

        reject_button = QPushButton("✗ Reject")
        reject_button.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #B91C1C;
            }
        """)
        reject_button.clicked.connect(self._on_reject)
        button_layout.addWidget(reject_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def _create_thumbnail(self, file_path: str, label_text: str) -> QWidget:
        """Create a thumbnail widget for a page with metadata tooltip and click-to-enlarge"""
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(2)

        # Thumbnail image (clickable)
        thumbnail_label = ClickableLabel()
        thumbnail_label.setFixedSize(80, 100)
        thumbnail_label.setStyleSheet("""
            ClickableLabel {
                border: 1px solid #CCCCCC;
                background-color: #F8F8F8;
            }
            ClickableLabel:hover {
                border: 2px solid #2563EB;
                background-color: #EFF6FF;
            }
        """)
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Get metadata for tooltip
        metadata_tooltip = self._format_metadata_tooltip(file_path)
        combined_tooltip = (
            f"{metadata_tooltip}<br><br><i>Click to enlarge all pages in this bundle</i>"
        )
        thumbnail_label.setToolTip(combined_tooltip)

        # Connect click to show enlarged pages
        thumbnail_label.clicked.connect(lambda: self._show_enlarged_pages())

        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    78,
                    98,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
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
        except Exception:
            thumbnail_label.setText("Error")
            thumbnail_label.setStyleSheet("color: red; font-size: 9px;")

        container_layout.addWidget(thumbnail_label)

        # Page label
        page_label = QLabel(label_text)
        page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        page_label.setStyleSheet("font-size: 9px; color: #666;")
        page_label.setToolTip(combined_tooltip)  # Also add tooltip to label
        container_layout.addWidget(page_label)

        return container

    def _format_metadata_tooltip(self, file_path: str) -> str:
        """Format metadata from analysis database as a readable tooltip"""
        try:
            # Get analysis results from database
            analysis = self.analysis_db.get_analysis(file_path)
            if not analysis:
                return "No metadata available"

            # Extract metadata fields
            filename = os.path.basename(file_path)
            company = analysis.get("company") or "N/A"
            doc_type = analysis.get("document_type") or "N/A"
            doc_date = analysis.get("document_date") or "N/A"
            tax_related = "Yes" if analysis.get("tax_related") else "No"
            page_num = analysis.get("page_number") or "N/A"
            total_pages = analysis.get("total_pages") or "N/A"
            confidence = analysis.get("confidence_score", 0.0)
            legibility = analysis.get("legibility") or "N/A"
            rotation = analysis.get("rotation_needed") or "N/A"

            # Format as multi-line tooltip
            tooltip = f"""<b>{html.escape(filename)}</b><br>
<br>
<b>Document Info:</b><br>
• Company: {html.escape(str(company))}<br>
• Type: {html.escape(str(doc_type))}<br>
• Date: {html.escape(str(doc_date))}<br>
• Tax Related: {html.escape(str(tax_related))}<br>
<br>
<b>Page Info:</b><br>
• Page: {html.escape(str(page_num))} of {html.escape(str(total_pages))}<br>
• Legibility: {html.escape(str(legibility))}<br>
• Rotation: {html.escape(str(rotation))}<br>
• Confidence: {confidence:.1%}<br>
"""
            return tooltip
        except Exception as e:
            return f"Error loading metadata: {html.escape(str(e))}"

    def _on_accept(self):
        """Handle accept button click"""
        self.accepted.emit(self.bundle_data)

    def _on_modify(self):
        """Handle modify button click"""
        self.modified.emit(self.bundle_data)

    def _on_reject(self):
        """Handle reject button click"""
        self.rejected.emit(self.bundle_data)

    def _show_enlarged_pages(self):
        """Show enlarged view of all pages in this bundle (maximized and fit to height)"""
        file_paths = self.bundle_data.get("file_paths", [])
        if not file_paths:
            return

        dialog = EnlargedPagesDialog(file_paths, self.analysis_db, self)
        dialog.showMaximized()
        dialog.exec()


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
        accept_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        accept_all_btn.clicked.connect(self.accept_all_high.emit)
        header_layout.addWidget(accept_all_btn)

        skip_btn = QPushButton("Review Manually")
        skip_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4B5563;
            }
        """)
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

    def set_bundles(self, bundles: list[dict[str, Any]]):
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

    def get_high_confidence_bundles(self) -> list[dict[str, Any]]:
        """Get all high confidence bundles (>= 0.8)"""
        return [
            card.bundle_data
            for card in self.bundle_cards
            if card.bundle_data.get("confidence_score", 0.0) >= 0.8
        ]
