"""Bundle review action bar: navigation and bundle decision controls."""

from typing import Any

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)

from ui.bundle.bundle_colors import get_bundle_colors


class BundleActionBar(QWidget):
    """Bottom action bar with prev/next navigation and Skip / Reject / Accept decisions."""

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

        # ── Navigation ────────────────────────────────────────────────
        self._prev_btn = QPushButton("← Previous Bundle")
        self._prev_btn.setStyleSheet(self._nav_btn_style(theme))
        self._prev_btn.clicked.connect(callbacks["on_previous"])
        layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next Bundle →")
        self._next_btn.setStyleSheet(self._nav_btn_style(theme))
        self._next_btn.clicked.connect(callbacks["on_next"])
        layout.addWidget(self._next_btn)

        layout.addStretch()

        # ── Decision buttons ──────────────────────────────────────────
        self._skip_btn = QPushButton("⏭  Skip")
        self._skip_btn.setStyleSheet(self._warning_btn_style(theme))
        self._skip_btn.clicked.connect(callbacks["on_skip"])
        layout.addWidget(self._skip_btn)

        self._reject_btn = QPushButton("✗  Reject")
        self._reject_btn.setStyleSheet(self._danger_btn_style(theme))
        self._reject_btn.clicked.connect(callbacks["on_reject"])
        layout.addWidget(self._reject_btn)

        # Accept is a split dropdown: primary = Accept, secondary = Accept & Export Now
        self._accept_btn = QToolButton()
        self._accept_btn.setText("✓  Accept")
        self._accept_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self._accept_btn.setStyleSheet(self._success_tool_btn_style(theme))

        accept_menu = QMenu(self._accept_btn)
        export_action = accept_menu.addAction("✓  Accept && Export Now")
        assert export_action is not None
        export_action.triggered.connect(callbacks["on_accept_export"])
        self._accept_btn.setMenu(accept_menu)
        self._accept_btn.clicked.connect(callbacks["on_accept"])
        layout.addWidget(self._accept_btn)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_nav_state(self, current_index: int, total: int) -> None:
        """Enable/disable prev and next buttons based on position."""
        self._prev_btn.setEnabled(current_index > 0)
        self._next_btn.setEnabled(current_index < total - 1)

    def apply_theme(self, dark_mode: bool) -> None:
        """Re-apply colour styles for the themed buttons."""
        self._dark_mode = dark_mode
        theme = get_bundle_colors(dark_mode)
        self.setStyleSheet(f"background: {theme['bg_secondary']};")
        self._prev_btn.setStyleSheet(self._nav_btn_style(theme))
        self._next_btn.setStyleSheet(self._nav_btn_style(theme))
        self._skip_btn.setStyleSheet(self._warning_btn_style(theme))
        self._reject_btn.setStyleSheet(self._danger_btn_style(theme))
        self._accept_btn.setStyleSheet(self._success_tool_btn_style(theme))

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
    def _success_tool_btn_style(theme: dict) -> str:
        return f"""
        QToolButton {{
            background: {theme["success"]};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 16px;
            font-weight: 600;
        }}
        QToolButton:hover {{
            background: {theme["success_hover"]};
        }}
        QToolButton::menu-button {{
            border: none;
            border-left: 1px solid rgba(255,255,255,0.3);
            border-radius: 0 6px 6px 0;
            width: 20px;
        }}
        QToolButton::menu-button:hover {{
            background: {theme["success_hover"]};
        }}
        """
