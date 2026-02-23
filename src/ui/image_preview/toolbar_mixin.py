# mypy: disable-error-code=attr-defined
"""_ImageToolbarMixin — creates and positions the floating overlay toolbar."""

from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)

from ui.image_preview.enums import ToolbarPosition, ToolbarSize


class _ImageToolbarMixin:
    """Mixin providing overlay toolbar creation and positioning for ImagePreviewWidget."""

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

    def _position_overlay_controls(self) -> None:
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
            f"Positioning overlay: widget={widget_width}x{widget_height}, "
            f"controls={controls_width}x{controls_height}, "
            f"visible={self.overlay_controls.isVisible()}"
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
            f"After move - actual pos: {self.overlay_controls.pos()}, "
            f"geometry: {self.overlay_controls.geometry()}"
        )
