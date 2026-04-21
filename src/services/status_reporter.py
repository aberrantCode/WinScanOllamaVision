"""
StatusReporter — the process-wide entry point for emitting status events.

Responsibilities:
- Accept ``info`` / ``warn`` / ``error`` calls from any thread.
- Auto-capture the caller's ``file:line`` as ``source``.
- Persist each event via ``StatusEventsRepository``.
- Emit a Qt ``event_recorded`` signal so subscribed widgets can refresh live.
- Own a stable ``session_id`` for the current app run.

The reporter is intentionally a singleton (``get_reporter()``) so backend
code — which may be deep inside a worker thread — can emit without having
to thread a handle through every layer. Pattern mirrors ``get_logger()``.

Testing guidance: in unit tests, pass ``repo`` explicitly and construct
a ``StatusReporter`` directly; don't use ``get_reporter()``. Use
``reset_reporter_for_tests()`` between tests that need a clean slate.
"""

from __future__ import annotations

import inspect
import logging
import os
import threading
import traceback
import uuid
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from services.status_event import LEVEL_ORDER, StatusEvent, StatusLevel

logger: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global logger
    if logger is None:
        from services.logging_service import get_logger as _get

        logger = _get()
    return logger


def _capture_source(skip_frames: int = 2) -> str | None:
    """Return ``"filename.py:lineno"`` for the caller N frames up the stack.

    ``skip_frames`` of 2 by default: frame 0 is this helper, frame 1 is
    the reporter method that called it, frame 2 is the actual caller.
    """
    try:
        frame = inspect.currentframe()
        for _ in range(skip_frames):
            if frame is None:
                return None
            frame = frame.f_back
        if frame is None:
            return None
        filename = os.path.basename(frame.f_code.co_filename)
        return f"{filename}:{frame.f_lineno}"
    except Exception:  # pragma: no cover - defensive
        return None


def _format_exception(exc: BaseException) -> str:
    """Return a Python traceback string for ``exc``."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


class StatusReporter(QObject):
    """Process-wide event emitter + persister for StatusEvents.

    Signals
    -------
    ``event_recorded(StatusEvent)`` — fired after every successful emit.
    UI code should connect with ``Qt.ConnectionType.QueuedConnection`` so
    signals from worker threads marshal to the main thread.
    """

    event_recorded = pyqtSignal(object)  # payload: StatusEvent

    def __init__(self, repo: Any = None, *, min_level: StatusLevel = "info") -> None:
        """Construct a reporter.

        Args:
            repo: A ``StatusEventsRepository``-like object with ``insert``
                and ``purge_older_than`` methods. May be ``None`` for
                pure-signal reporters used in tests.
            min_level: Events below this level are dropped at emit time.
        """
        super().__init__()
        self._repo = repo
        self._min_level: StatusLevel = min_level
        self._session_id = str(uuid.uuid4())
        self._write_lock = threading.Lock()

    # ---- Session ---------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    def set_min_level(self, level: StatusLevel) -> None:
        """Update the emission-time filter threshold."""
        self._min_level = level

    # ---- Emitters --------------------------------------------------------

    def info(self, feature: str, title: str, **kw: Any) -> StatusEvent:
        return self._emit("info", feature, title, **kw)

    def warn(self, feature: str, title: str, **kw: Any) -> StatusEvent:
        return self._emit("warn", feature, title, **kw)

    def error(
        self,
        feature: str,
        title: str,
        *,
        exc: BaseException | None = None,
        **kw: Any,
    ) -> StatusEvent:
        if exc is not None and "traceback" not in kw:
            kw["traceback"] = _format_exception(exc)
        if exc is not None and not kw.get("detail"):
            kw["detail"] = f"{type(exc).__name__}: {exc}"
        return self._emit("error", feature, title, **kw)

    def emit_event(self, event: StatusEvent) -> StatusEvent:
        """Low-level: accept an already-constructed StatusEvent."""
        return self._record(event)

    # ---- Internals -------------------------------------------------------

    def _emit(self, level: StatusLevel, feature: str, title: str, **kw: Any) -> StatusEvent:
        source = kw.pop("source", None) or _capture_source(skip_frames=3)
        event = StatusEvent(
            level=level,
            feature=feature,
            title=title,
            detail=kw.pop("detail", "") or "",
            source=source,
            traceback=kw.pop("traceback", None),
            context=kw.pop("context", {}) or {},
            file_path=kw.pop("file_path", None),
            correlation_id=kw.pop("correlation_id", None),
        )
        return self._record(event)

    def _record(self, event: StatusEvent) -> StatusEvent:
        # Emission-time filter
        if LEVEL_ORDER[event.level] < LEVEL_ORDER[self._min_level]:
            return event

        # Persist (best-effort — a DB write failure must not kill the caller)
        if self._repo is not None:
            try:
                with self._write_lock:
                    self._repo.insert(event, self._session_id)
            except Exception as exc:  # pragma: no cover - defensive
                _get_logger().warning(
                    "StatusReporter: failed to persist event %s: %s",
                    event.event_id,
                    exc,
                )

        # Emit regardless of persistence so live UI still reflects the event.
        try:
            self.event_recorded.emit(event)
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning("StatusReporter: signal emit failed: %s", exc)
        return event

    # ---- Queries (pass-throughs to the repo) -----------------------------

    def recent(
        self,
        *,
        limit: int = 50,
        min_level: StatusLevel | None = None,
        feature_prefix: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent events (newest first). Empty if no repo is attached."""
        if self._repo is None:
            return []
        try:
            return list(
                self._repo.recent(
                    limit=limit,
                    min_level=min_level,
                    feature_prefix=feature_prefix,
                    session_id=session_id,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning("StatusReporter: recent() query failed: %s", exc)
            return []

    def unacknowledged_count(self, *, min_level: StatusLevel = "warn") -> int:
        if self._repo is None:
            return 0
        try:
            return int(self._repo.unacknowledged_count(min_level=min_level))
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning("StatusReporter: unack count failed: %s", exc)
            return 0

    def acknowledge_all(self) -> None:
        if self._repo is None:
            return
        try:
            self._repo.acknowledge_all()
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning("StatusReporter: acknowledge_all failed: %s", exc)

    def set_starred(self, row_id: int, starred: bool) -> None:
        if self._repo is None:
            return
        try:
            self._repo.set_starred(row_id, starred)
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning("StatusReporter: set_starred failed: %s", exc)

    def delete_by_id(self, row_id: int) -> None:
        if self._repo is None:
            return
        try:
            self._repo.delete_by_id(row_id)
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning("StatusReporter: delete failed: %s", exc)

    # ---- Retention -------------------------------------------------------

    def purge_expired(self, retention_days: int) -> int:
        """Delete unstarred events older than the cutoff. Returns count."""
        if self._repo is None:
            return 0
        try:
            return int(self._repo.purge_older_than(retention_days))
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning("StatusReporter: purge failed: %s", exc)
            return 0


# ----- Singleton access ----------------------------------------------------

_instance: StatusReporter | None = None
_instance_lock = threading.Lock()


def get_reporter() -> StatusReporter:
    """Return the process-wide StatusReporter, constructing it on first call.

    On first call, the reporter is wired to a ``StatusEventsRepository``
    backed by the AppData analysis database. If the DB is unreachable
    the reporter still works — it just won't persist. Application code
    should never import this from test code; tests construct reporters
    directly.
    """
    global _instance
    if _instance is not None:
        return _instance

    with _instance_lock:
        if _instance is not None:
            return _instance

        repo = None
        try:
            import sqlite3

            from db.connection import DatabaseConnection, get_appdata_db_path
            from db.repositories.status_events_repo import StatusEventsRepository
            from db.schema import create_all_tables

            # Run schema migrations on the ordinary connection (main thread).
            db_path = get_appdata_db_path()
            migration_conn = DatabaseConnection(db_path)
            create_all_tables(migration_conn)
            migration_conn.close()

            # The reporter is called from worker threads (e.g. AnalysisWorker)
            # as well as the main thread. Python's sqlite3 defaults to
            # check_same_thread=True which would raise ProgrammingError on
            # every cross-thread insert and silently lose events. The
            # StatusReporter serializes all writes through ``_write_lock``,
            # so check_same_thread=False is safe here.
            conn = DatabaseConnection.__new__(DatabaseConnection)
            conn.db_path = db_path
            sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            sqlite_conn.row_factory = sqlite3.Row
            conn.connection = sqlite_conn  # type: ignore[assignment]
            repo = StatusEventsRepository(conn)
        except Exception as exc:  # pragma: no cover - defensive
            _get_logger().warning(
                "StatusReporter: could not attach DB repo (%s); running in-memory only",
                exc,
            )

        # Honor the user's StatusHistory.min_level setting at startup
        min_level: StatusLevel = "info"
        try:
            from config.config_manager import ConfigManager

            cfg_level = ConfigManager().get_setting("StatusHistory", "min_level", "info")
            if cfg_level in ("debug", "info", "warn", "error"):
                min_level = cfg_level  # type: ignore[assignment]
        except Exception:  # pragma: no cover - defensive
            pass

        _instance = StatusReporter(repo=repo, min_level=min_level)

        # Apply retention on startup so the DB doesn't grow unbounded
        try:
            from config.config_manager import ConfigManager

            retention = int(ConfigManager().get_setting("StatusHistory", "retention_days", "30"))
            if retention > 0:
                _instance.purge_expired(retention)
        except Exception:  # pragma: no cover - defensive
            pass

        return _instance


def reset_reporter_for_tests() -> None:
    """Clear the cached singleton. Call from test setup/teardown only."""
    global _instance
    with _instance_lock:
        _instance = None
