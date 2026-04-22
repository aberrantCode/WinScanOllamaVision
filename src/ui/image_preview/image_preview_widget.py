"""
Unified image preview widget with zoom, rotation, and pan controls.

This widget encapsulates all image transformation logic with a configurable
floating toolbar overlay. Designed to be reusable across multiple windows.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import QSpinBox, QVBoxLayout, QWidget

from config.config_manager import ConfigManager
from ui.image_preview.enums import ToolbarPosition, ToolbarSize
from ui.image_preview.pannable_label import PannableImageLabel
from ui.image_preview.rotation_mixin import _RotationPersistenceMixin
from ui.image_preview.toolbar_mixin import _ImageToolbarMixin
from ui.theme.theme_manager import ThemeManager


class ImagePreviewWidget(_ImageToolbarMixin, _RotationPersistenceMixin, QWidget):
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
        config_manager=None,
        analysis_db=None,
    ):
        """
        Initialize the image preview widget.

        Args:
            parent: Parent widget
            toolbar_size: Size of toolbar buttons (COMPACT or STANDARD)
            toolbar_position: Position of floating toolbar
            theme_colors: Theme color dictionary (uses defaults if None)
            config_manager: Optional ConfigManager for rotation persistence settings
            analysis_db: Optional AnalysisDB for rotation persistence
        """
        from services.logging_service import get_logger

        logger = get_logger()

        super().__init__(parent)
        self.toolbar_size = toolbar_size
        self.toolbar_position = toolbar_position
        self.theme_colors = theme_colors or self._get_default_theme()
        self.config_manager = config_manager
        self.analysis_db = analysis_db

        logger.debug(
            f"ImagePreviewWidget init: toolbar_size={toolbar_size.value}, position={toolbar_position.value}"
        )

        # Image state
        self.base_pixmap: QPixmap | None = None
        self.current_file_path: str | None = None
        self.zoom_level = 100
        self.rotation_angle = 0

        # UI components
        self.image_label: PannableImageLabel | None = None
        self.overlay_controls: QWidget | None = None
        self.zoom_spinner: QSpinBox | None = None

        self._init_ui()

    def _get_default_theme(self) -> dict[str, str]:
        """Get theme colors from ThemeManager based on the current app theme."""
        try:
            cm = getattr(self, "config_manager", None) or ConfigManager()
            is_dark = cm.get_setting("Theme", "theme", "dark") == "dark"
        except Exception:
            is_dark = True
        c = ThemeManager.get_colors(is_dark)
        return {
            **c,
            "button_bg": c["bg_tertiary"],
            "button_hover": c["bg_hover"],
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

        # Invariant: both components must be set by the time _init_ui returns
        assert self.image_label is not None, "image_label must be set in _init_ui"
        assert self.zoom_spinner is not None, "zoom_spinner must be set in _create_overlay_controls"

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

    def set_pixmap(
        self, pixmap: QPixmap, apply_fit: str | None = None, file_path: str | None = None
    ):
        """
        Set the base pixmap to display.

        Args:
            pixmap: The base image to display
            apply_fit: Optional fit mode to apply ('width', 'height', 'window')
            file_path: Optional file path for rotation persistence
        """
        from services.logging_service import get_logger

        logger = get_logger()

        self.base_pixmap = pixmap
        self.current_file_path = file_path
        self.rotation_angle = 0
        if self.image_label:
            self.image_label.reset_pan()

        # Load saved rotation if persistence is enabled and file_path provided
        if file_path and self._is_rotation_persistence_enabled():
            saved_rotation = self._load_saved_rotation(file_path)
            if saved_rotation:
                self.rotation_angle = saved_rotation
                logger.info("Loaded saved rotation %s° for %s", saved_rotation, file_path)

        logger.debug(
            "set_pixmap called: pixmap size=%s, apply_fit=%s, file_path=%s, rotation=%s, widget size=%s",
            pixmap.size(),
            apply_fit,
            file_path,
            self.rotation_angle,
            self.size(),
        )

        # Show and position toolbar
        if self.overlay_controls:
            logger.debug(
                "Showing overlay controls: before_visible=%s",
                self.overlay_controls.isVisible(),
            )

            self.overlay_controls.show()
            self.overlay_controls.raise_()
            self.overlay_controls.adjustSize()

            logger.debug("After adjustSize: overlay_size=%s", self.overlay_controls.size())

            self._position_overlay_controls()

            logger.debug(
                "After positioning: pos=%s, visible=%s, geometry=%s",
                self.overlay_controls.pos(),
                self.overlay_controls.isVisible(),
                self.overlay_controls.geometry(),
            )

        # Apply initial fit if requested (deferred to allow layout to complete)
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
            # No fit requested - update display immediately
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
        # Force display update in case zoom value didn't change
        self._update_display()

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
        # Force display update in case zoom value didn't change
        self._update_display()

    def fit_to_window(self):
        """Fit image to both width and height."""
        if not self.base_pixmap:
            return

        # Calculate the zoom needed to fit
        min_zoom = self._calculate_min_zoom()
        zoom_percent = max(min_zoom, min(400, min_zoom))

        self.zoom_spinner.setValue(zoom_percent)
        # Force display update in case zoom value didn't change
        self._update_display()

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
        """Zoom out by 25% (minimum is fit-to-window size)."""
        min_zoom = self._calculate_min_zoom()
        new_zoom = max(min_zoom, self.zoom_level - 25)
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

        # Save rotation if persistence is enabled
        if self.current_file_path and self._is_rotation_persistence_enabled():
            self._save_rotation(self.current_file_path, self.rotation_angle)

    def _on_rotate_cw(self):
        """Rotate clockwise by 90 degrees."""
        self.rotation_angle = (self.rotation_angle + 90) % 360
        self.image_label.reset_pan()
        self._update_display()

        # Save rotation if persistence is enabled
        if self.current_file_path and self._is_rotation_persistence_enabled():
            self._save_rotation(self.current_file_path, self.rotation_angle)

    def _calculate_min_zoom(self) -> int:
        """
        Calculate minimum zoom to fit image within preview widget area.

        Returns:
            Minimum zoom percentage (ensures image never smaller than widget)
        """
        if not self.base_pixmap:
            return 5  # Fallback if no image loaded

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
            return 5

        # Calculate zoom to fit both dimensions (use smaller ratio)
        width_ratio = available_width / pixmap.width()
        height_ratio = available_height / pixmap.height()
        zoom_ratio = min(width_ratio, height_ratio)
        min_zoom_percent = int(zoom_ratio * 100)

        # Ensure minimum is at least 5% but typically will be much higher
        return max(5, min_zoom_percent)

    def _on_scroll_zoom(self, zoom_change: int):
        """
        Handle zoom change from scroll wheel.

        Prevents zooming out beyond the point where image fits in the widget.

        Args:
            zoom_change: Amount to change zoom (e.g., +10 or -10)
        """
        current_zoom = self.zoom_spinner.value() if self.zoom_spinner else self.zoom_level
        min_zoom = self._calculate_min_zoom()
        new_zoom = max(min_zoom, min(400, current_zoom + zoom_change))
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

    # ========== Rotation Persistence ==========

    def _is_rotation_persistence_enabled(self) -> bool:
        """Check if rotation persistence is enabled in settings."""
        if not self.config_manager:
            return False
        return bool(self.config_manager.get_bool("GUI", "persist_rotation", True))

    def _load_saved_rotation(self, file_path: str) -> int:
        """
        Load saved rotation for a file from database.

        Args:
            file_path: Absolute path to image file

        Returns:
            Rotation angle in degrees (0, 90, 180, 270), or 0 if not found
        """
        if not self.analysis_db:
            return 0

        try:
            from db.repositories.rotation_repo import RotationRepository

            rotation_repo = RotationRepository(self.analysis_db.connection)
            return rotation_repo.get(file_path)
        except Exception as e:
            from services.logging_service import get_logger

            logger = get_logger()
            logger.warning(f"Failed to load rotation for {file_path}: {e}")
            return 0

    def _save_rotation(self, file_path: str, rotation_degrees: int) -> None:
        """
        Save rotation for a file to database.

        Args:
            file_path: Absolute path to image file
            rotation_degrees: Rotation angle in degrees
        """
        if not self.analysis_db:
            return

        try:
            from db.repositories.rotation_repo import RotationRepository

            rotation_repo = RotationRepository(self.analysis_db.connection)
            rotation_repo.save(file_path, rotation_degrees)

            from services.logging_service import get_logger

            logger = get_logger()
            logger.info(f"Saved rotation {rotation_degrees}° for {file_path}")
        except Exception as e:
            from services.logging_service import get_logger

            logger = get_logger()
            logger.error(f"Failed to save rotation for {file_path}: {e}", exc_info=True)
