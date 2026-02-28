"""Bundle review action bar: navigation, zoom/rotation controls, bundle decisions."""

from typing import Any

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors


class BundleActionBar(QWidget):
    """Bottom action bar with nav buttons, zoom/fit/rotate controls, and accept/reject."""

    def __init__(
        self,
        dark_mode: bool,
        callbacks: dict[str, Any],
        current_bundle_index: int = 0,
        total_bundles: int = 1,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._dark_mode = dark_mode
        self._build_ui(callbacks)
        self.update_nav_state(current_bundle_index, total_bundles)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_ui(self, callbacks: dict[str, Any]) -> None:
        theme = get_bundle_colors(self._dark_mode)
        self.setStyleSheet(f"background: {theme['bg_secondary']};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Navigation buttons
        self._prev_btn = QPushButton("← Previous Bundle")
        self._prev_btn.setStyleSheet(self._nav_btn_style(theme))
        self._prev_btn.clicked.connect(callbacks["on_previous"])
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next Bundle →")
        self._next_btn.setStyleSheet(self._nav_btn_style(theme))
        self._next_btn.clicked.connect(callbacks["on_next"])
        layout.addWidget(self._next_btn)

        layout.addStretch()

        # Zoom controls
        btn_style = self._small_btn_style(theme)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setStyleSheet(btn_style)
        zoom_out_btn.setFixedSize(40, 32)
        zoom_out_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        zoom_out_btn.setToolTip("Zoom Out")
        zoom_out_btn.clicked.connect(callbacks["on_zoom_out"])
        layout.addWidget(zoom_out_btn)

        self._zoom_spinner = QSpinBox()
        self._zoom_spinner.setRange(25, 400)
        self._zoom_spinner.setValue(100)
        self._zoom_spinner.setSuffix("%")
        self._zoom_spinner.setFixedWidth(70)
        self._zoom_spinner.setFixedHeight(32)
        self._zoom_spinner.setStyleSheet(self._spinner_style(theme))
        self._zoom_spinner.valueChanged.connect(callbacks["on_zoom_changed"])
        layout.addWidget(self._zoom_spinner)

        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setStyleSheet(btn_style)
        zoom_in_btn.setFixedSize(40, 32)
        zoom_in_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        zoom_in_btn.setToolTip("Zoom In")
        zoom_in_btn.clicked.connect(callbacks["on_zoom_in"])
        layout.addWidget(zoom_in_btn)

        layout.addSpacing(12)

        # Fit buttons
        fit_width_btn = QPushButton("⬌")
        fit_width_btn.setStyleSheet(btn_style)
        fit_width_btn.setFixedSize(40, 32)
        fit_width_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fit_width_btn.setToolTip("Fit to Width")
        fit_width_btn.clicked.connect(callbacks["on_fit_width"])
        layout.addWidget(fit_width_btn)

        fit_height_btn = QPushButton("⬍")
        fit_height_btn.setStyleSheet(btn_style)
        fit_height_btn.setFixedSize(40, 32)
        fit_height_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fit_height_btn.setToolTip("Fit to Height")
        fit_height_btn.clicked.connect(callbacks["on_fit_height"])
        layout.addWidget(fit_height_btn)

        fit_window_btn = QPushButton("⛶")
        fit_window_btn.setStyleSheet(btn_style)
        fit_window_btn.setFixedSize(40, 32)
        fit_window_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        fit_window_btn.setToolTip("Fit to Window")
        fit_window_btn.clicked.connect(callbacks["on_fit_window"])
        layout.addWidget(fit_window_btn)

        layout.addSpacing(12)

        # Rotation controls
        rotate_left_btn = QPushButton("↺")
        rotate_left_btn.setStyleSheet(btn_style)
        rotate_left_btn.setFixedSize(40, 32)
        rotate_left_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        rotate_left_btn.setToolTip("Rotate Counter-Clockwise")
        rotate_left_btn.clicked.connect(callbacks["on_rotate_ccw"])
        layout.addWidget(rotate_left_btn)

        rotate_right_btn = QPushButton("↻")
        rotate_right_btn.setStyleSheet(btn_style)
        rotate_right_btn.setFixedSize(40, 32)
        rotate_right_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        rotate_right_btn.setToolTip("Rotate Clockwise")
        rotate_right_btn.clicked.connect(callbacks["on_rotate_cw"])
        layout.addWidget(rotate_right_btn)

        layout.addStretch()

        # Bundle decision buttons
        self._skip_btn = QPushButton("⏭ Skip for Later")
        self._skip_btn.setStyleSheet(self._warning_btn_style(theme))
        self._skip_btn.clicked.connect(callbacks["on_skip"])
        layout.addWidget(self._skip_btn)

        self._reject_btn = QPushButton("✗ Reject Bundle")
        self._reject_btn.setStyleSheet(self._danger_btn_style(theme))
        self._reject_btn.clicked.connect(callbacks["on_reject"])
        layout.addWidget(self._reject_btn)

        self._accept_btn = QPushButton("✓ Accept && Convert to PDF")
        self._accept_btn.setStyleSheet(self._success_btn_style(theme))
        self._accept_btn.setMinimumWidth(200)
        self._accept_btn.clicked.connect(callbacks["on_accept"])
        layout.addWidget(self._accept_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def zoom_spinner(self) -> QSpinBox:
        return self._zoom_spinner

    def update_nav_state(self, current_index: int, total: int) -> None:
        """Enable/disable prev and next buttons based on position."""
        self._prev_btn.setEnabled(current_index > 0)
        self._next_btn.setEnabled(current_index < total - 1)

    def apply_theme(self, dark_mode: bool) -> None:
        """Re-apply colour styles for the five themed buttons."""
        self._dark_mode = dark_mode
        theme = get_bundle_colors(dark_mode)
        self.setStyleSheet(f"background: {theme['bg_secondary']};")
        self._prev_btn.setStyleSheet(self._nav_btn_style(theme))
        self._next_btn.setStyleSheet(self._nav_btn_style(theme))
        self._zoom_spinner.setStyleSheet(self._spinner_style(theme))
        self._skip_btn.setStyleSheet(self._warning_btn_style(theme))
        self._reject_btn.setStyleSheet(self._danger_btn_style(theme))
        self._accept_btn.setStyleSheet(self._success_btn_style(theme))

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nav_btn_style(theme: dict) -> str:
        return f"""
        QPushButton {{
            background: {theme["button_bg"]};
            color: {theme["button_text"]};
            border: 1px solid {theme["border"]};
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {theme["bg_hover"]};
            border-color: {theme["border_focus"]};
        }}
        QPushButton:disabled {{
            background: {theme["bg_secondary"]};
            color: {theme["text_disabled"]};
        }}
        """

    @staticmethod
    def _small_btn_style(theme: dict) -> str:
        return f"""
        QPushButton {{
            background: {theme["button_bg"]};
            color: {theme["button_text"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {theme["button_hover"]};
            border-color: {theme["border"]};
            color: {theme["text_primary"]};
        }}
        QPushButton:pressed {{
            background: {theme["selected"]};
        }}
        """

    @staticmethod
    def _spinner_style(theme: dict) -> str:
        return f"""
        QSpinBox {{
            background: {theme["button_bg"]};
            color: {theme["text_primary"]};
            border: 1px solid {theme["border"]};
            border-radius: 4px;
            padding: 2px 4px;
            font-size: 11px;
        }}
        QSpinBox:focus {{
            border-color: {theme["selected"]};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            width: 0px;
        }}
        """

    @staticmethod
    def _warning_btn_style(theme: dict) -> str:
        return f"""
        QPushButton {{
            background: {theme["warning"]};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {theme["warning_hover"]};
        }}
        """

    @staticmethod
    def _danger_btn_style(theme: dict) -> str:
        return f"""
        QPushButton {{
            background: {theme["danger"]};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {theme["danger_hover"]};
        }}
        """

    @staticmethod
    def _success_btn_style(theme: dict) -> str:
        return f"""
        QPushButton {{
            background: {theme["success"]};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {theme["success_hover"]};
        }}
        """
