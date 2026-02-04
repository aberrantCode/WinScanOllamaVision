"""
UI Styles and Themes (Phase 9)
Modern color palette and QSS stylesheets for WinScanLLM
"""

# ===== COLOR PALETTE =====

class Colors:
    """Modern color palette for UI components"""

    # Primary colors
    PRIMARY = "#2563EB"  # Modern Blue
    PRIMARY_HOVER = "#1E40AF"  # Darker blue for hover
    PRIMARY_LIGHT = "#3B82F6"  # Lighter blue for accents
    PRIMARY_PALE = "#DBEAFE"  # Very light blue for backgrounds

    # Success colors
    SUCCESS = "#059669"  # Emerald
    SUCCESS_HOVER = "#047857"  # Darker emerald
    SUCCESS_LIGHT = "#10B981"  # Lighter emerald
    SUCCESS_PALE = "#D1FAE5"  # Very light emerald

    # Danger colors
    DANGER = "#DC2626"  # Red
    DANGER_HOVER = "#B91C1C"  # Darker red
    DANGER_LIGHT = "#EF4444"  # Lighter red
    DANGER_PALE = "#FEE2E2"  # Very light red

    # Warning colors
    WARNING = "#F59E0B"  # Amber
    WARNING_HOVER = "#D97706"  # Darker amber
    WARNING_LIGHT = "#FBBF24"  # Lighter amber
    WARNING_PALE = "#FEF3C7"  # Very light amber

    # Neutral colors
    GRAY_900 = "#111827"  # Very dark gray (text)
    GRAY_800 = "#1F2937"
    GRAY_700 = "#374151"
    GRAY_600 = "#4B5563"
    GRAY_500 = "#6B7280"
    GRAY_400 = "#9CA3AF"
    GRAY_300 = "#D1D5DB"
    GRAY_200 = "#E5E7EB"
    GRAY_100 = "#F3F4F6"
    GRAY_50 = "#F9FAFB"

    # Special colors
    WHITE = "#FFFFFF"
    BLACK = "#000000"
    BACKGROUND = "#F9FAFB"  # Light gray background
    BORDER = "#E5E7EB"  # Border color


# ===== BUTTON STYLES =====

def get_primary_button_style():
    """Modern primary button with hover lift effect"""
    return f"""
        QPushButton {{
            background-color: {Colors.PRIMARY};
            color: {Colors.WHITE};
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 11pt;
            font-weight: 600;
            min-height: 40px;
        }}
        QPushButton:hover {{
            background-color: {Colors.PRIMARY_HOVER};
            padding-top: 10px;
            padding-bottom: 14px;
        }}
        QPushButton:pressed {{
            background-color: {Colors.PRIMARY_HOVER};
            padding-top: 13px;
            padding-bottom: 11px;
        }}
        QPushButton:disabled {{
            background-color: {Colors.GRAY_300};
            color: {Colors.GRAY_500};
        }}
    """


def get_success_button_style():
    """Success button (green) with hover effect"""
    return f"""
        QPushButton {{
            background-color: {Colors.SUCCESS};
            color: {Colors.WHITE};
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 11pt;
            font-weight: 600;
            min-height: 40px;
        }}
        QPushButton:hover {{
            background-color: {Colors.SUCCESS_HOVER};
            padding-top: 10px;
            padding-bottom: 14px;
        }}
        QPushButton:pressed {{
            background-color: {Colors.SUCCESS_HOVER};
            padding-top: 13px;
            padding-bottom: 11px;
        }}
        QPushButton:disabled {{
            background-color: {Colors.GRAY_300};
            color: {Colors.GRAY_500};
        }}
    """


def get_danger_button_style():
    """Danger button (red) with hover effect"""
    return f"""
        QPushButton {{
            background-color: {Colors.DANGER};
            color: {Colors.WHITE};
            border: none;
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 11pt;
            font-weight: 600;
            min-height: 40px;
        }}
        QPushButton:hover {{
            background-color: {Colors.DANGER_HOVER};
            padding-top: 10px;
            padding-bottom: 14px;
        }}
        QPushButton:pressed {{
            background-color: {Colors.DANGER_HOVER};
            padding-top: 13px;
            padding-bottom: 11px;
        }}
        QPushButton:disabled {{
            background-color: {Colors.GRAY_300};
            color: {Colors.GRAY_500};
        }}
    """


def get_secondary_button_style():
    """Secondary button (gray outline) with hover effect"""
    return f"""
        QPushButton {{
            background-color: {Colors.WHITE};
            color: {Colors.GRAY_700};
            border: 2px solid {Colors.GRAY_300};
            border-radius: 8px;
            padding: 12px 24px;
            font-size: 11pt;
            font-weight: 600;
            min-height: 40px;
        }}
        QPushButton:hover {{
            background-color: {Colors.GRAY_50};
            border-color: {Colors.GRAY_400};
            padding-top: 10px;
            padding-bottom: 14px;
        }}
        QPushButton:pressed {{
            background-color: {Colors.GRAY_100};
            border-color: {Colors.GRAY_500};
            padding-top: 13px;
            padding-bottom: 11px;
        }}
        QPushButton:disabled {{
            background-color: {Colors.GRAY_100};
            color: {Colors.GRAY_400};
            border-color: {Colors.GRAY_200};
        }}
    """


def get_icon_button_style():
    """Small icon button for toolbar actions"""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {Colors.GRAY_600};
            border: none;
            border-radius: 6px;
            padding: 8px;
            font-size: 14pt;
            min-width: 40px;
            min-height: 40px;
        }}
        QPushButton:hover {{
            background-color: {Colors.GRAY_100};
            color: {Colors.GRAY_900};
        }}
        QPushButton:pressed {{
            background-color: {Colors.GRAY_200};
        }}
        QPushButton:disabled {{
            color: {Colors.GRAY_300};
        }}
    """


# ===== CARD STYLES =====

def get_card_style():
    """Modern card with shadow and rounded corners"""
    return f"""
        QFrame {{
            background-color: {Colors.WHITE};
            border: 1px solid {Colors.BORDER};
            border-radius: 12px;
            padding: 16px;
        }}
    """


def get_thumbnail_card_style():
    """Thumbnail card with hover effect"""
    return f"""
        QWidget {{
            background-color: {Colors.WHITE};
            border: 2px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 4px;
        }}
        QWidget:hover {{
            border-color: {Colors.PRIMARY};
            background-color: {Colors.PRIMARY_PALE};
        }}
    """


# ===== INPUT STYLES =====

def get_input_style():
    """Modern text input with focus state"""
    return f"""
        QLineEdit, QPlainTextEdit, QTextEdit {{
            background-color: {Colors.WHITE};
            border: 2px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 10pt;
            color: {Colors.GRAY_900};
        }}
        QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
            border-color: {Colors.PRIMARY};
            background-color: {Colors.PRIMARY_PALE};
        }}
        QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled {{
            background-color: {Colors.GRAY_100};
            color: {Colors.GRAY_500};
            border-color: {Colors.GRAY_200};
        }}
    """


def get_dropdown_style():
    """Modern dropdown with hover state"""
    return f"""
        QComboBox {{
            background-color: {Colors.WHITE};
            border: 2px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 10px 12px;
            font-size: 10pt;
            color: {Colors.GRAY_900};
            min-height: 36px;
        }}
        QComboBox:hover {{
            border-color: {Colors.GRAY_400};
        }}
        QComboBox:focus {{
            border-color: {Colors.PRIMARY};
        }}
        QComboBox::drop-down {{
            border: none;
            padding-right: 8px;
        }}
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid {Colors.GRAY_600};
            margin-right: 6px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {Colors.WHITE};
            border: 2px solid {Colors.BORDER};
            border-radius: 8px;
            selection-background-color: {Colors.PRIMARY_PALE};
            selection-color: {Colors.PRIMARY};
            padding: 4px;
        }}
    """


# ===== LAYOUT STYLES =====

def get_header_style():
    """Modern header bar style"""
    return f"""
        QWidget {{
            background-color: {Colors.WHITE};
            border-bottom: 2px solid {Colors.BORDER};
            padding: 16px 24px;
        }}
    """


def get_status_bar_style():
    """Status bar at bottom of window"""
    return f"""
        QLabel {{
            background-color: {Colors.GRAY_50};
            color: {Colors.GRAY_700};
            padding: 12px 24px;
            font-size: 10pt;
            border-top: 1px solid {Colors.BORDER};
        }}
    """


def get_panel_style():
    """Side panel style"""
    return f"""
        QWidget {{
            background-color: {Colors.GRAY_50};
            border-right: 1px solid {Colors.BORDER};
            padding: 16px;
        }}
    """


# ===== LABEL STYLES =====

def get_heading_style(level=1):
    """Heading styles (h1, h2, h3)"""
    sizes = {1: "24pt", 2: "18pt", 3: "14pt"}
    weights = {1: "bold", 2: "bold", 3: "600"}
    return f"""
        QLabel {{
            font-size: {sizes.get(level, "14pt")};
            font-weight: {weights.get(level, "600")};
            color: {Colors.GRAY_900};
            padding: 8px 0;
        }}
    """


def get_body_text_style():
    """Normal body text"""
    return f"""
        QLabel {{
            font-size: 10pt;
            color: {Colors.GRAY_700};
            line-height: 1.5;
        }}
    """


def get_caption_style():
    """Small caption text"""
    return f"""
        QLabel {{
            font-size: 9pt;
            color: {Colors.GRAY_500};
        }}
    """


# ===== BADGE STYLES =====

def get_success_badge_style():
    """Success badge (green pill)"""
    return f"""
        QLabel {{
            background-color: {Colors.SUCCESS_PALE};
            color: {Colors.SUCCESS};
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 9pt;
            font-weight: 600;
        }}
    """


def get_warning_badge_style():
    """Warning badge (amber pill)"""
    return f"""
        QLabel {{
            background-color: {Colors.WARNING_PALE};
            color: {Colors.WARNING};
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 9pt;
            font-weight: 600;
        }}
    """


def get_danger_badge_style():
    """Danger badge (red pill)"""
    return f"""
        QLabel {{
            background-color: {Colors.DANGER_PALE};
            color: {Colors.DANGER};
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 9pt;
            font-weight: 600;
        }}
    """


# ===== MAIN APPLICATION STYLE =====

def get_main_app_stylesheet():
    """
    Comprehensive application stylesheet.
    Apply this to QApplication for global styling.
    """
    return f"""
        /* Global defaults */
        * {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}

        QMainWindow, QDialog, QWidget {{
            background-color: {Colors.BACKGROUND};
            color: {Colors.GRAY_900};
        }}

        /* Scrollbars */
        QScrollBar:vertical {{
            background-color: {Colors.GRAY_100};
            width: 12px;
            border-radius: 6px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {Colors.GRAY_400};
            border-radius: 6px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {Colors.GRAY_500};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            background-color: {Colors.GRAY_100};
            height: 12px;
            border-radius: 6px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {Colors.GRAY_400};
            border-radius: 6px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {Colors.GRAY_500};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        /* Tooltips */
        QToolTip {{
            background-color: {Colors.GRAY_900};
            color: {Colors.WHITE};
            border: none;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 9pt;
        }}

        /* Checkbox */
        QCheckBox {{
            spacing: 8px;
            color: {Colors.GRAY_700};
        }}
        QCheckBox::indicator {{
            width: 20px;
            height: 20px;
            border: 2px solid {Colors.BORDER};
            border-radius: 4px;
            background-color: {Colors.WHITE};
        }}
        QCheckBox::indicator:hover {{
            border-color: {Colors.PRIMARY};
        }}
        QCheckBox::indicator:checked {{
            background-color: {Colors.PRIMARY};
            border-color: {Colors.PRIMARY};
            image: url(none);
        }}

        /* Spinbox */
        QSpinBox {{
            background-color: {Colors.WHITE};
            border: 2px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 10pt;
            color: {Colors.GRAY_900};
        }}
        QSpinBox:focus {{
            border-color: {Colors.PRIMARY};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            background-color: {Colors.GRAY_100};
            border: none;
            border-radius: 4px;
            width: 20px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {Colors.GRAY_200};
        }}

        /* Progress Bar */
        QProgressBar {{
            background-color: {Colors.GRAY_200};
            border: none;
            border-radius: 8px;
            height: 8px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {Colors.PRIMARY};
            border-radius: 8px;
        }}
    """


# ===== UTILITY FUNCTIONS =====

def apply_shadow_effect(widget):
    """Apply drop shadow effect to widget (PyQt6)"""
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect
    from PyQt6.QtGui import QColor

    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(12)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 25))
    widget.setGraphicsEffect(shadow)


def apply_lift_animation(widget):
    """Apply lift animation on hover (requires custom event handling)"""
    # Note: This requires implementing enterEvent and leaveEvent in the widget
    # Example usage in widget class:
    # def enterEvent(self, event):
    #     self.setStyleSheet(hover_style)
    # def leaveEvent(self, event):
    #     self.setStyleSheet(normal_style)
    pass


def get_themed_message_box_style():
    """Get stylesheet for themed message boxes"""
    return f"""
        QMessageBox {{
            background-color: {Colors.WHITE};
        }}
        QMessageBox QLabel {{
            color: {Colors.GRAY_900};
            background-color: transparent;
            font-size: 13px;
        }}
        QMessageBox QPushButton {{
            background-color: {Colors.PRIMARY};
            color: {Colors.WHITE};
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 600;
            min-width: 80px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {Colors.PRIMARY_HOVER};
        }}
        QMessageBox QPushButton:pressed {{
            background-color: {Colors.PRIMARY_HOVER};
        }}
    """


def show_information(parent, title, text):
    """Show themed information message box"""
    from PyQt6.QtWidgets import QMessageBox
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Information)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStyleSheet(get_themed_message_box_style())
    msg_box.exec()


def show_warning(parent, title, text):
    """Show themed warning message box"""
    from PyQt6.QtWidgets import QMessageBox
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStyleSheet(get_themed_message_box_style())
    msg_box.exec()


def show_critical(parent, title, text):
    """Show themed critical/error message box"""
    from PyQt6.QtWidgets import QMessageBox
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStyleSheet(get_themed_message_box_style())
    msg_box.exec()


def show_question(parent, title, text):
    """Show themed question message box with Yes/No buttons"""
    from PyQt6.QtWidgets import QMessageBox
    msg_box = QMessageBox(parent)
    msg_box.setIcon(QMessageBox.Icon.Question)
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg_box.setStyleSheet(get_themed_message_box_style())
    return msg_box.exec()
