"""
IssuePreviewDialog — shows the exact title/labels/body that will be submitted
to GitHub, with privacy toggles, before opening the browser.

Keeps the user in control: they see what's being disclosed and can redact
paths or strip the traceback before clicking Continue.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.issue_template import build_github_issue_url, build_issue_template
from services.status_event import StatusEvent

APP_VERSION_FALLBACK = "0.0.0-dev"


class IssuePreviewDialog(QDialog):
    """Show the pending issue content + privacy toggles before opening the browser."""

    def __init__(
        self,
        event: StatusEvent,
        *,
        app_version: str = APP_VERSION_FALLBACK,
        base_url: str | None = None,
        url_opener: Callable[[str], bool] | None = None,
        default_redact_paths: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._event = event
        self._app_version = app_version
        self._base_url = base_url
        self._opener = url_opener or webbrowser.open

        self.setWindowTitle("File GitHub Issue — Preview")
        self.resize(720, 640)
        self._build_ui(default_redact_paths)
        self._refresh_preview()

    # ---- UI --------------------------------------------------------------

    def _build_ui(self, default_redact_paths: bool) -> None:
        root = QVBoxLayout(self)

        intro = QLabel(
            "This is the exact content that will be sent to GitHub when you click "
            "Continue. Nothing is submitted yet — GitHub will open a new-issue form "
            "pre-filled with these values. You can still edit them in the browser."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        # Privacy toggles
        privacy = QGroupBox("Privacy")
        pl = QVBoxLayout(privacy)
        self._redact_cb = QCheckBox("Redact file paths to basenames only")
        self._redact_cb.setChecked(default_redact_paths)
        self._tb_cb = QCheckBox("Include traceback")
        self._tb_cb.setChecked(True)
        self._sys_cb = QCheckBox("Include system info (OS, Python version)")
        self._sys_cb.setChecked(True)
        for cb in (self._redact_cb, self._tb_cb, self._sys_cb):
            cb.stateChanged.connect(self._refresh_preview)
            pl.addWidget(cb)
        root.addWidget(privacy)

        # Title + labels preview
        header = QFormLayout()
        self._title_edit = QLineEdit()
        self._title_edit.setReadOnly(True)
        self._labels_lbl = QLabel()
        header.addRow("Title:", self._title_edit)
        header.addRow("Labels:", self._labels_lbl)
        root.addLayout(header)

        # Body preview
        self._body_edit = QTextEdit()
        self._body_edit.setReadOnly(True)
        self._body_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 9pt;")
        root.addWidget(self._body_edit, stretch=1)

        # Buttons
        bb = QDialogButtonBox()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        continue_btn = QPushButton("Continue to GitHub")
        continue_btn.setDefault(True)
        continue_btn.clicked.connect(self._on_continue)
        bb.addButton(cancel, QDialogButtonBox.ButtonRole.RejectRole)
        bb.addButton(continue_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        root.addWidget(bb)

    # ---- Preview ---------------------------------------------------------

    def _refresh_preview(self) -> None:
        template = build_issue_template(
            self._event,
            app_version=self._app_version,
            redact_paths=self._redact_cb.isChecked(),
            include_traceback=self._tb_cb.isChecked(),
            include_system_info=self._sys_cb.isChecked(),
        )
        self._title_edit.setText(template.title)
        self._labels_lbl.setText(", ".join(template.labels))
        self._body_edit.setPlainText(template.body)

    def _current_url(self) -> str:
        kw: dict = {
            "app_version": self._app_version,
            "redact_paths": self._redact_cb.isChecked(),
            "include_traceback": self._tb_cb.isChecked(),
            "include_system_info": self._sys_cb.isChecked(),
        }
        if self._base_url:
            kw["base_url"] = self._base_url
        return build_github_issue_url(self._event, **kw)

    # ---- Actions ---------------------------------------------------------

    def _on_continue(self) -> None:
        import contextlib

        url = self._current_url()
        with contextlib.suppress(Exception):  # pragma: no cover - defensive
            self._opener(url)
        self.accept()

    # ---- Accessors (tests) ----------------------------------------------

    @property
    def current_url(self) -> str:
        return self._current_url()
