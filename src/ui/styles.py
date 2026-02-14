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
    WARNING_LIGHT = "#FFFBEB"  # Very light amber for warning backgrounds


# ===== BUTTON STYLES =====


def get_button_style(color="primary"):
    """
    Global button style matching dialog default button (same as refresh button).

    Args:
        color: 'primary' (blue), 'success' (green), 'danger' (red), 'secondary' (gray)
    """
    colors = {
        "primary": (Colors.PRIMARY, Colors.PRIMARY_HOVER),
        "success": (Colors.SUCCESS, Colors.SUCCESS_HOVER),
        "danger": (Colors.DANGER, Colors.DANGER_HOVER),
        "secondary": (Colors.GRAY_200, Colors.GRAY_300),
    }
    bg, hover = colors.get(color, colors["primary"])
    text = Colors.WHITE if color in ["primary", "success", "danger"] else Colors.GRAY_900

    return f"""
        QPushButton {{
            background-color: {bg};
            color: {text};
            border: none;
            border-radius: 5px;
            padding: 8px 16px;
            font-size: 10pt;
            min-width: 100px;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
        QPushButton:disabled {{
            background-color: #9CA3AF;
        }}
    """


def get_primary_button_style():
    """Modern primary button with hover lift effect"""
    return f"""
        QPushButton {{
            background-color: {Colors.PRIMARY};
            color: {Colors.WHITE};
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.PRIMARY_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Colors.PRIMARY_HOVER};
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
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.SUCCESS_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Colors.SUCCESS_HOVER};
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
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.DANGER_HOVER};
        }}
        QPushButton:pressed {{
            background-color: {Colors.DANGER_HOVER};
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
            border-radius: 4px;
            padding: 8px 16px;
            font-size: 11pt;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background-color: {Colors.GRAY_50};
            border-color: {Colors.GRAY_400};
        }}
        QPushButton:pressed {{
            background-color: {Colors.GRAY_100};
            border-color: {Colors.GRAY_500};
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


# ===== ANALYSIS STATUS WINDOW STYLES =====


def get_metric_card_style():
    """Metric card for displaying statistics with border and padding"""
    return f"""
        QFrame {{
            background-color: {Colors.WHITE};
            border: 2px solid {Colors.BORDER};
            border-radius: 10px;
            padding: 16px;
        }}
        QFrame:hover {{
            border-color: {Colors.PRIMARY_LIGHT};
        }}
    """


def get_progress_bar_style(percentage: float) -> str:
    """
    Progress bar with color coding based on percentage.
    Green for >80%, yellow for 60-80%, red for <60%.

    Args:
        percentage: Value from 0-100 to determine color
    """
    if percentage >= 80:
        chunk_color = Colors.SUCCESS
    elif percentage >= 60:
        chunk_color = Colors.WARNING
    else:
        chunk_color = Colors.DANGER

    return f"""
        QProgressBar {{
            background-color: {Colors.GRAY_200};
            border: none;
            border-radius: 10px;
            height: 20px;
            text-align: center;
            color: {Colors.GRAY_900};
            font-weight: 600;
            font-size: 10pt;
        }}
        QProgressBar::chunk {{
            background-color: {chunk_color};
            border-radius: 10px;
        }}
    """


def get_collapsible_section_style():
    """Header bar style for collapsible sections with expand/collapse functionality"""
    return f"""
        QFrame {{
            background-color: {Colors.GRAY_100};
            border: 1px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 12px 16px;
        }}
        QFrame:hover {{
            background-color: {Colors.GRAY_200};
        }}
        QLabel {{
            background-color: transparent;
            color: {Colors.GRAY_900};
            font-size: 11pt;
            font-weight: 600;
            border: none;
        }}
        QPushButton {{
            background-color: transparent;
            border: none;
            color: {Colors.GRAY_700};
            font-size: 14pt;
            padding: 0px;
            min-width: 24px;
            max-width: 24px;
            min-height: 24px;
            max-height: 24px;
        }}
        QPushButton:hover {{
            color: {Colors.PRIMARY};
        }}
    """


def get_action_items_panel_style():
    """Warning panel style for action items with light yellow background"""
    return f"""
        QFrame {{
            background-color: {Colors.WARNING_LIGHT};
            border: 2px solid {Colors.WARNING};
            border-radius: 10px;
            padding: 16px;
        }}
        QLabel {{
            background-color: transparent;
            color: {Colors.GRAY_900};
        }}
    """


def get_distribution_bar_style():
    """Smaller progress bar style for distribution visualizations"""
    return f"""
        QProgressBar {{
            background-color: {Colors.GRAY_200};
            border: none;
            border-radius: 6px;
            height: 12px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background-color: {Colors.PRIMARY};
            border-radius: 6px;
        }}
    """


def get_grid_toolbar_style():
    """Toolbar frame style with panel background and proper spacing"""
    return f"""
        QFrame {{
            background-color: {Colors.GRAY_50};
            border: 1px solid {Colors.BORDER};
            border-radius: 8px;
            padding: 8px 12px;
        }}
        QLabel {{
            background-color: transparent;
            color: {Colors.GRAY_700};
            font-size: 10pt;
            border: none;
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

        /* Standardize button sizing across the app */
        QPushButton {{
            min-height: 40px;
            padding: 8px 12px;
            border-radius: 6px;
        }}
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
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QGraphicsDropShadowEffect

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
    """Get stylesheet for themed message boxes based on current theme"""
    from config.config_manager import ConfigManager

    config = ConfigManager()
    current_theme = config.get_setting("Theme", "theme", "light")

    if current_theme == "dark":
        # Dark theme colors
        bg_color = Colors.GRAY_800
        text_color = Colors.WHITE
        button_bg = Colors.PRIMARY
        button_hover = Colors.PRIMARY_HOVER
    else:
        # Light theme colors (default)
        bg_color = Colors.WHITE
        text_color = Colors.GRAY_900
        button_bg = Colors.PRIMARY
        button_hover = Colors.PRIMARY_HOVER

    return f"""
        QMessageBox {{
            background-color: {bg_color};
        }}
        QMessageBox QLabel {{
            color: {text_color};
            background-color: transparent;
            font-size: 13px;
        }}
        QMessageBox QPushButton {{
            background-color: {button_bg};
            color: {Colors.WHITE};
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-weight: 600;
            min-width: 80px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {button_hover};
        }}
        QMessageBox QPushButton:pressed {{
            background-color: {button_hover};
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
