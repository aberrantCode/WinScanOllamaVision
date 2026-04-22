"""Non-modal "Update available" banner.

Shown at the top of the main window when the ``UpdateService`` reports a
newer release. Emits signals for Install / Remind / Skip — orchestration
lives in the main window, not the widget.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy


class UpdateBanner(QFrame):
    """Compact horizontal strip: message + Install / Remind / Skip buttons."""

    install_clicked = pyqtSignal(object)  # UpdateInfo
    remind_clicked = pyqtSignal(object)  # UpdateInfo
    skip_clicked = pyqtSignal(object)  # UpdateInfo

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "#updateBanner { background-color: #FFF4CE; border: 1px solid #E5C100; "
            "padding: 6px; } "
            "#updateBanner QLabel { color: #4A3A00; } "
            "#updateBanner QPushButton { padding: 4px 10px; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._info: Any = None  # holds the last UpdateInfo when visible

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._message = QLabel("Update available")
        self._message.setWordWrap(False)
        layout.addWidget(self._message, stretch=1)

        self._install_btn = QPushButton("Install update")
        self._install_btn.clicked.connect(self._on_install)
        layout.addWidget(self._install_btn)

        self._remind_btn = QPushButton("Remind me later")
        self._remind_btn.clicked.connect(self._on_remind)
        layout.addWidget(self._remind_btn)

        self._skip_btn = QPushButton("Skip this version")
        self._skip_btn.clicked.connect(self._on_skip)
        layout.addWidget(self._skip_btn)

        self.hide()

    def show_for(self, info: Any, current_version: str) -> None:
        """Reveal the banner with a message tailored to ``info``."""
        self._info = info
        self._message.setText(f"Update available: v{current_version} → v{info.version}")
        self.show()

    def dismiss(self) -> None:
        self._info = None
        self.hide()

    # ---- click handlers ------------------------------------------------

    def _on_install(self) -> None:
        if self._info is not None:
            self.install_clicked.emit(self._info)

    def _on_remind(self) -> None:
        info = self._info
        self.dismiss()
        if info is not None:
            self.remind_clicked.emit(info)

    def _on_skip(self) -> None:
        info = self._info
        self.dismiss()
        if info is not None:
            self.skip_clicked.emit(info)
