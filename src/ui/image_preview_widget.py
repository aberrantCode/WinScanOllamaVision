"""
Unified image preview widget with zoom, rotation, and pan controls.

This widget encapsulates all image transformation logic with a configurable
floating toolbar overlay. Designed to be reusable across multiple windows.
"""

from enum import Enum

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.pannable_image_label import PannableImageLabel
from ui.styles import Colors


class ToolbarSize(Enum):
    """Toolbar size options for floating controls."""

    COMPACT = "compact"  # 20x20px buttons, 10pt font (50% of standard)
    STANDARD = "standard"  # 40x40px buttons, 20pt font (100%)


class ToolbarPosition(Enum):
    """Toolbar position options."""

    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"  # Default
    BOTTOM_RIGHT = "bottom_right"


class ImagePreviewWidget(QWidget):
    """
    Unified image preview widget with zoom, rotation, and pan controls.

    Features:
    - Configurable toolbar size (compact or standard)
    - Configurable toolbar position
    - Theme-aware styling
    - Complete image transformation pipeline (rotation -> zoom -> pan)
    - Fit to width/height/window modes
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        toolbar_size: ToolbarSize = ToolbarSize.STANDARD,
        toolbar_position: ToolbarPosition = ToolbarPosition.BOTTOM_CENTER,
        theme_colors: dict[str, str] | None = None,
    ):
        """
        Initialize the image preview widget.

        Args:
            parent: Parent widget
            toolbar_size: Size of toolbar buttons (COMPACT or STANDARD)
            toolbar_position: Position of floating toolbar
            theme_colors: Theme color dictionary (uses defaults if None)
        """
        from services.logging_service import get_logger

        logger = get_logger()

        super().__init__(parent)
        self.toolbar_size = toolbar_size
        self.toolbar_position = toolbar_position
        self.theme_colors = theme_colors or self._get_default_theme()

        logger.info(
            f"ImagePreviewWidget init: toolbar_size={toolbar_size.value}, position={toolbar_position.value}"
        )

        # Image state
        self.base_pixmap: QPixmap | None = None
        self.zoom_level = 100
        self.rotation_angle = 0

        # UI components
        self.image_label: PannableImageLabel | None = None
        self.overlay_controls: QWidget | None = None
        self.zoom_spinner: QSpinBox | None = None

        self._init_ui()

    def _get_default_theme(self) -> dict[str, str]:
        """Get default light theme colors."""
        return {
            "bg_primary": Colors.WHITE,
            "bg_secondary": Colors.GRAY_100,
            "text_primary": Colors.GRAY_900,
            "text_secondary": Colors.GRAY_700,
            "border": Colors.GRAY_300,
            "accent": Colors.PRIMARY,
            "button_bg": Colors.GRAY_100,
            "button_hover": Colors.PRIMARY_PALE,
        }

    def _init_ui(self):
        """Initialize the UI layout with image label and floating toolbar."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create pannable image label
        self.image_label = PannableImageLabel(self)
        self.image_label.pan_changed.connect(self._update_display)
        self.image_label.zoom_requested.connect(self._on_scroll_zoom)
        layout.addWidget(self.image_label)

        # Create floating toolbar overlay
        self.overlay_controls = self._create_overlay_controls()
        self.overlay_controls.setParent(self)

        # CRITICAL: Configure overlay to be visible
        # Don't clip to parent bounds
        self.overlay_controls.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.overlay_controls.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        # Set auto-fill background to ensure it's drawn
        self.overlay_controls.setAutoFillBackground(True)

        self.overlay_controls.hide()  # Hidden until image is set

        # Ensure overlay has correct stacking order
        self.overlay_controls.raise_()

    def _create_overlay_controls(self) -> QWidget:
        """Create floating toolbar with zoom and rotation controls."""
        from services.logging_service import get_logger

        logger = get_logger()

        # Get sizing parameters based on toolbar size
        if self.toolbar_size == ToolbarSize.COMPACT:
            btn_size = 20
            font_size = 10
            spinner_width = 55
            spinner_height = 20
            border_radius = 6
            spacing = 2
            padding = 4
            margin = 4
            logger.info("Creating COMPACT toolbar")
        else:  # STANDARD
            btn_size = 40
            font_size = 20
            spinner_width = 110
            spinner_height = 40
            border_radius = 12
            spacing = 4
            padding = 4
            margin = 8
            logger.info("Creating STANDARD toolbar")

        # Get theme colors
        bg = self.theme_colors["bg_primary"]
        btn_bg = self.theme_colors["button_bg"]
        btn_hover = self.theme_colors["button_hover"]
        text = self.theme_colors["text_primary"]
        border = self.theme_colors["border"]
        accent = self.theme_colors["accent"]

        controls = QWidget()

        # Force minimum size to ensure widget is visible
        if self.toolbar_size == ToolbarSize.COMPACT:
            controls.setMinimumHeight(30)
            controls.setMinimumWidth(250)
        else:
            controls.setMinimumHeight(60)
            controls.setMinimumWidth(500)

        controls.setStyleSheet(f"""
            QWidget {{
                background: {bg};
                border: 2px solid {border};
                border-radius: {border_radius}px;
                padding: {padding}px;
            }}
        """)

        layout = QHBoxLayout(controls)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(spacing)
        layout.setSizeConstraint(QHBoxLayout.SizeConstraint.SetFixedSize)

        # Button style
        btn_style = f"""
            QPushButton {{
                background: {btn_bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                font-size: {font_size}pt;
                font-weight: bold;
                min-width: {btn_size}px;
                max-width: {btn_size}px;
                min-height: {btn_size}px;
                max-height: {btn_size}px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
                border-color: {accent};
            }}
        """

        # Zoom out button
        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.setToolTip("Zoom Out (25%)")
        zoom_out_btn.clicked.connect(self._on_zoom_out)
        layout.addWidget(zoom_out_btn)

        # Zoom spinner
        self.zoom_spinner = QSpinBox()
        self.zoom_spinner.setRange(5, 400)
        self.zoom_spinner.setValue(100)
        self.zoom_spinner.setSuffix("%")
        self.zoom_spinner.setFixedWidth(spinner_width)
        self.zoom_spinner.setFixedHeight(spinner_height)
        self.zoom_spinner.setToolTip("Zoom Level (25-400%)")
        self.zoom_spinner.setStyleSheet(f"""
            QSpinBox {{
                background: {bg};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px;
                font-size: {font_size}pt;
            }}
        """)
        self.zoom_spinner.valueChanged.connect(self._on_zoom_percent_changed)
        layout.addWidget(self.zoom_spinner)

        # Zoom in button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.setToolTip("Zoom In (25%)")
        zoom_in_btn.clicked.connect(self._on_zoom_in)
        layout.addWidget(zoom_in_btn)

        # Fit to width button
        fit_width_btn = QPushButton("W")
        fit_width_btn.setStyleSheet(btn_style)
        fit_width_btn.setToolTip("Fit to Width")
        fit_width_btn.clicked.connect(self.fit_to_width)
        layout.addWidget(fit_width_btn)

        # Fit to height button
        fit_height_btn = QPushButton("H")
        fit_height_btn.setStyleSheet(btn_style)
        fit_height_btn.setToolTip("Fit to Height")
        fit_height_btn.clicked.connect(self.fit_to_height)
        layout.addWidget(fit_height_btn)

        # Fit to window button
        fit_btn = QPushButton("F")
        fit_btn.setStyleSheet(btn_style)
        fit_btn.setToolTip("Fit to Window")
        fit_btn.clicked.connect(self.fit_to_window)
        layout.addWidget(fit_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background: {border};")
        sep.setFixedWidth(2)
        sep.setFixedHeight(btn_size)
        layout.addWidget(sep)

        # Rotate counter-clockwise button
        rotate_ccw_btn = QPushButton("↺")
        rotate_ccw_btn.setStyleSheet(btn_style)
        rotate_ccw_btn.setToolTip("Rotate Counter-Clockwise (90°)")
        rotate_ccw_btn.clicked.connect(self._on_rotate_ccw)
        layout.addWidget(rotate_ccw_btn)

        # Rotate clockwise button
        rotate_cw_btn = QPushButton("↻")
        rotate_cw_btn.setStyleSheet(btn_style)
        rotate_cw_btn.setToolTip("Rotate Clockwise (90°)")
        rotate_cw_btn.clicked.connect(self._on_rotate_cw)
        layout.addWidget(rotate_cw_btn)

        logger.info(f"Overlay controls created with {layout.count()} buttons")
        return controls

    def _position_overlay_controls(self):
        """Position overlay controls based on toolbar_position setting."""
        from services.logging_service import get_logger

        logger = get_logger()

        if not self.overlay_controls:
            logger.warning("_position_overlay_controls: no overlay_controls!")
            return

        widget_width = self.width()
        widget_height = self.height()
        controls_width = self.overlay_controls.width()
        controls_height = self.overlay_controls.height()

        logger.info(
            f"Positioning overlay: widget={widget_width}x{widget_height}, controls={controls_width}x{controls_height}, visible={self.overlay_controls.isVisible()}"
        )

        margin = 10

        # Calculate position based on toolbar_position
        if self.toolbar_position == ToolbarPosition.TOP_LEFT:
            x = margin
            y = margin
        elif self.toolbar_position == ToolbarPosition.TOP_CENTER:
            x = (widget_width - controls_width) // 2
            y = margin
        elif self.toolbar_position == ToolbarPosition.TOP_RIGHT:
            x = widget_width - controls_width - margin
            y = margin
        elif self.toolbar_position == ToolbarPosition.BOTTOM_LEFT:
            x = margin
            y = widget_height - controls_height - margin
        elif self.toolbar_position == ToolbarPosition.BOTTOM_CENTER:
            x = (widget_width - controls_width) // 2
            y = widget_height - controls_height - margin
        else:  # BOTTOM_RIGHT
            x = widget_width - controls_width - margin
            y = widget_height - controls_height - margin

        logger.info(f"Moving overlay to position ({x}, {y})")
        self.overlay_controls.move(x, y)
        logger.info(
            f"After move - actual pos: {self.overlay_controls.pos()}, geometry: {self.overlay_controls.geometry()}"
        )

    def resizeEvent(self, event):  # noqa: N802
        """Handle widget resize to reposition toolbar."""
        super().resizeEvent(event)
        self._position_overlay_controls()

    def showEvent(self, event):  # noqa: N802
        """Handle widget show to position toolbar."""
        super().showEvent(event)
        # If we have a pixmap loaded, ensure overlay is visible
        if self.base_pixmap and self.overlay_controls:
            self.overlay_controls.show()
            self.overlay_controls.raise_()
        self._position_overlay_controls()

    def set_pixmap(self, pixmap: QPixmap, apply_fit: str | None = None):
        """
        Set the base pixmap to display.

        Args:
            pixmap: The base image to display
            apply_fit: Optional fit mode to apply ('width', 'height', 'window')
        """
        from services.logging_service import get_logger

        logger = get_logger()

        self.base_pixmap = pixmap
        self.rotation_angle = 0
        if self.image_label:
            self.image_label.reset_pan()

        logger.info(
            f"set_pixmap called: pixmap size={pixmap.size()}, apply_fit={apply_fit}, widget size={self.size()}"
        )

        # Show and position toolbar
        if self.overlay_controls:
            logger.info(
                f"Showing overlay controls: before_visible={self.overlay_controls.isVisible()}"
            )

            self.overlay_controls.show()
            self.overlay_controls.raise_()
            self.overlay_controls.adjustSize()

            logger.info(f"After adjustSize: overlay_size={self.overlay_controls.size()}")

            self._position_overlay_controls()

            logger.info(
                f"After positioning: pos={self.overlay_controls.pos()}, visible={self.overlay_controls.isVisible()}, geometry={self.overlay_controls.geometry()}"
            )

        # Apply initial fit if requested
        if apply_fit:
            # Use QTimer to defer fit calculation until layout is complete
            if apply_fit == "width":
                QTimer.singleShot(100, self.fit_to_width)
                # Force show toolbar after layout
                QTimer.singleShot(
                    150, lambda: self.overlay_controls.show() if self.overlay_controls else None
                )
                QTimer.singleShot(
                    150, lambda: self.overlay_controls.raise_() if self.overlay_controls else None
                )
            elif apply_fit == "height":
                QTimer.singleShot(100, self.fit_to_height)
            elif apply_fit == "window":
                QTimer.singleShot(100, self.fit_to_window)
        else:
            self._update_display()

    def get_zoom_level(self) -> int:
        """Get current zoom level percentage (25-400)."""
        return self.zoom_level

    def set_zoom_level(self, zoom: int):
        """
        Set zoom level percentage.

        Args:
            zoom: Zoom percentage (25-400)
        """
        zoom = max(5, min(400, zoom))
        if self.zoom_spinner:
            self.zoom_spinner.setValue(zoom)

    def get_rotation_angle(self) -> int:
        """Get current rotation angle in degrees (0, 90, 180, 270)."""
        return self.rotation_angle

    def reset_view(self):
        """Reset zoom to 100%, rotation to 0°, and pan to center."""
        self.rotation_angle = 0
        if self.zoom_spinner:
            self.zoom_spinner.setValue(100)
        if self.image_label:
            self.image_label.reset_pan()
        self._update_display()

    def fit_to_width(self):
        """Fit image to available width."""
        if not self.base_pixmap:
            return

        # Apply rotation to get actual display dimensions
        pixmap = self._apply_rotation(self.base_pixmap)

        # Get available width (subtract margins)
        available_width = self.width() - 40

        # Ensure valid dimensions
        if available_width <= 0 or pixmap.width() <= 0:
            return

        # Calculate zoom to fit width
        zoom_percent = int((available_width / pixmap.width()) * 100)
        zoom_percent = max(5, min(400, zoom_percent))

        self.zoom_spinner.setValue(zoom_percent)

    def fit_to_height(self):
        """Fit image to available height."""
        if not self.base_pixmap:
            return

        # Apply rotation to get actual display dimensions
        pixmap = self._apply_rotation(self.base_pixmap)

        # Get available height (subtract margins and toolbar)
        available_height = self.height() - 80

        # Ensure valid dimensions
        if available_height <= 0 or pixmap.height() <= 0:
            return

        # Calculate zoom to fit height
        zoom_percent = int((available_height / pixmap.height()) * 100)
        zoom_percent = max(5, min(400, zoom_percent))

        self.zoom_spinner.setValue(zoom_percent)

    def fit_to_window(self):
        """Fit image to both width and height."""
        if not self.base_pixmap:
            return

        # Apply rotation to get actual display dimensions
        pixmap = self._apply_rotation(self.base_pixmap)

        # Get available dimensions
        available_width = self.width() - 40
        available_height = self.height() - 80

        # Ensure valid dimensions
        if (
            available_width <= 0
            or available_height <= 0
            or pixmap.width() <= 0
            or pixmap.height() <= 0
        ):
            return

        # Calculate zoom to fit both dimensions (use smaller ratio)
        width_ratio = available_width / pixmap.width()
        height_ratio = available_height / pixmap.height()
        zoom_ratio = min(width_ratio, height_ratio)
        zoom_percent = int(zoom_ratio * 100)
        zoom_percent = max(5, min(400, zoom_percent))

        self.zoom_spinner.setValue(zoom_percent)

    def update_theme(self, theme_colors: dict[str, str]):
        """
        Update widget theme colors.

        Args:
            theme_colors: Dictionary of theme colors
        """
        self.theme_colors = theme_colors
        # Recreate toolbar with new theme
        if self.overlay_controls:
            self.overlay_controls.deleteLater()
        self.overlay_controls = self._create_overlay_controls()
        self.overlay_controls.setParent(self)
        if self.base_pixmap:
            self.overlay_controls.show()
            self._position_overlay_controls()

    # ========== Internal Event Handlers ==========

    def _on_zoom_in(self):
        """Zoom in by 25%."""
        new_zoom = min(400, self.zoom_level + 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_out(self):
        """Zoom out by 25%."""
        new_zoom = max(5, self.zoom_level - 25)
        self.zoom_spinner.setValue(new_zoom)

    def _on_zoom_percent_changed(self, value: int):
        """Handle zoom percentage change from spinner."""
        self.zoom_level = value
        if self.image_label:
            self.image_label.set_zoom_level(value)
        self._update_display()

    def _on_rotate_ccw(self):
        """Rotate counter-clockwise by 90 degrees."""
        self.rotation_angle = (self.rotation_angle - 90) % 360
        self.image_label.reset_pan()
        self._update_display()

    def _on_rotate_cw(self):
        """Rotate clockwise by 90 degrees."""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.image_label.reset_pan()
        self._update_display()

    def _on_scroll_zoom(self, zoom_change: int):
        """
        Handle zoom change from scroll wheel.

        Args:
            zoom_change: Amount to change zoom (e.g., +10 or -10)
        """
        current_zoom = self.zoom_spinner.value() if self.zoom_spinner else self.zoom_level
        new_zoom = max(5, min(400, current_zoom + zoom_change))
        if self.zoom_spinner:
            self.zoom_spinner.setValue(new_zoom)

    # ========== Image Transformation Pipeline ==========

    def _apply_rotation(self, pixmap: QPixmap) -> QPixmap:
        """Apply rotation transformation to pixmap."""
        if self.rotation_angle == 0:
            return pixmap

        transform = QTransform()
        transform.rotate(self.rotation_angle)
        return pixmap.transformed(transform, Qt.TransformationMode.SmoothTransformation)

    def _update_display(self):
        """Update image display with full transformation pipeline."""
        if not self.base_pixmap:
            return

        # Step 1: Apply rotation
        pixmap = self._apply_rotation(self.base_pixmap)

        # Step 2: Apply zoom
        zoom_factor = self.zoom_level / 100.0
        if zoom_factor != 1.0:
            new_width = int(pixmap.width() * zoom_factor)
            new_height = int(pixmap.height() * zoom_factor)
            pixmap = pixmap.scaled(
                new_width,
                new_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        # Step 3: Apply pan (works at any zoom level)
        pan_offset = self.image_label.get_pan_offset()
        if not pan_offset.isNull():
            canvas = QPixmap(pixmap.size())
            canvas.fill(Qt.GlobalColor.white)
            painter = QPainter(canvas)
            painter.drawPixmap(pan_offset, pixmap)
            painter.end()
            pixmap = canvas

        self.image_label.setPixmap(pixmap)
