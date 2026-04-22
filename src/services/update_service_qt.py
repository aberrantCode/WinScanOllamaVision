"""Qt facade for the update service.

Keeps PyQt6 out of ``update_service.py`` so the pure helpers stay testable
on environments without Qt installed. The orchestration here is thin: each
method wraps a pure helper inside a background ``QThreadPool`` runnable
and emits signals with the result.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from services.logging_service import get_logger
from services.update_service import (
    UpdateInfo,
    decide_update,
    download_and_verify,
    fetch_latest_release,
    load_cache,
    save_cache,
    should_check_now,
)


class _Runnable(QRunnable):
    """Tiny QRunnable that runs a closure on the global thread pool."""

    def __init__(self, fn: Any) -> None:
        super().__init__()
        self._fn = fn

    def run(self) -> None:
        try:
            self._fn()
        except Exception:  # noqa: BLE001 — signal-based error reporting is the contract here
            get_logger().exception("UpdateService background task crashed")


class UpdateService(QObject):
    """Orchestrates update-check + download on background threads.

    All I/O (GitHub API, download) happens off the GUI thread. The caller
    wires signals into UI widgets (banner, Settings).
    """

    update_available = pyqtSignal(object)  # UpdateInfo
    update_check_failed = pyqtSignal(str)
    download_progress = pyqtSignal(int, int)  # bytes_so_far, total_bytes
    download_complete = pyqtSignal(object)  # Path
    download_failed = pyqtSignal(str)

    def __init__(
        self,
        owner: str,
        repo: str,
        current_version: str,
        cache_path: Path,
        include_prereleases: bool,
        skipped_version: str,
        user_agent: str,
    ) -> None:
        super().__init__()
        self._owner = owner
        self._repo = repo
        self._current_version = current_version
        self._cache_path = cache_path
        self._include_prereleases = include_prereleases
        self._skipped_version = skipped_version
        self._user_agent = user_agent

    # ---- public API ---------------------------------------------------

    def check_for_updates(self, force: bool = False) -> None:
        QThreadPool.globalInstance().start(_Runnable(lambda: self._check_impl(force)))

    def download_update(self, info: UpdateInfo, dest_dir: Path) -> None:
        QThreadPool.globalInstance().start(_Runnable(lambda: self._download_impl(info, dest_dir)))

    # ---- helpers ------------------------------------------------------

    def _check_impl(self, force: bool) -> None:
        cache = load_cache(self._cache_path)
        last_iso = cache.get("checked_at") if isinstance(cache, dict) else None
        last = _parse_iso(last_iso) if isinstance(last_iso, str) else None
        if not force and not should_check_now(last):
            get_logger().debug("UpdateService: cache fresh, skipping check")
            return

        release = fetch_latest_release(self._owner, self._repo, user_agent=self._user_agent)
        if release is None:
            self.update_check_failed.emit("network or API error")
            return

        info = decide_update(
            current=self._current_version,
            release=release,
            include_prereleases=self._include_prereleases,
            skipped=self._skipped_version,
        )
        save_cache(
            self._cache_path,
            {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "latest_tag": release.tag_name,
            },
        )
        if info is not None:
            self.update_available.emit(info)

    def _download_impl(self, info: UpdateInfo, dest_dir: Path) -> None:
        if not info.asset_url or not info.asset_digest:
            self.download_failed.emit("release has no installer asset")
            return
        try:
            path = download_and_verify(
                url=info.asset_url,
                expected_digest=info.asset_digest,
                dest_dir=dest_dir,
                user_agent=self._user_agent,
            )
        except Exception as exc:  # noqa: BLE001 — signal-based error reporting
            self.download_failed.emit(str(exc))
            return
        self.download_complete.emit(path)


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
