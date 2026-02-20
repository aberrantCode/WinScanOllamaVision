"""
Splash screen displayed during application initialization.

Shows the app name, scanner animation, and a live status text block while the
following initialization tasks complete in a background thread:

  1. Verify settings & configuration values
  2. Verify source directories exist
  3. Verify the database is valid
  4. Apply any pending schema migrations
  5. Rebuild database indexes (REINDEX / ANALYZE)
  6. Refresh available models from all providers
"""

import contextlib
import logging
import os

from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QMovie
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------


class InitializationWorker(QThread):
    """
    Background thread that performs all application initialization tasks.

    Emits *status_changed* with a human-readable description as each task
    begins, then emits *init_complete* when every task has finished so the
    caller can safely transition from the splash screen to the main window.
    """

    status_changed = pyqtSignal(str)
    init_complete = pyqtSignal()

    def __init__(self, config_manager) -> None:
        super().__init__()
        self._config_manager = config_manager

    # ------------------------------------------------------------------
    # QThread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            self._verify_config()
            self._verify_directories()
            self._init_database()
            self._rebuild_indexes()
            self._refresh_models()
        except Exception:
            logger.exception("Unexpected error during initialization worker")
            # Ensure any partially-opened DB connections are released so the
            # main thread can open its own without hitting a file lock.
            for attr in ("_analysis_db", "_metadata_db"):
                db = getattr(self, attr, None)
                if db is not None:
                    with contextlib.suppress(Exception):
                        db.close()

        self.status_changed.emit("Ready")
        self.init_complete.emit()

    # ------------------------------------------------------------------
    # Individual initialization steps
    # ------------------------------------------------------------------

    def _verify_config(self) -> None:
        """Verify all required configuration sections are present."""
        self.status_changed.emit("Verifying configuration...")
        required_sections = [
            "LLMProvider",
            "SourceDirectories",
            "AutoAnalysis",
            "Discovery",
            "Theme",
        ]
        for section in required_sections:
            if not self._config_manager.config.has_section(section):
                logger.warning("Configuration section missing: %s (will use defaults)", section)

    def _verify_directories(self) -> None:
        """Check that every configured source directory exists on disk."""
        self.status_changed.emit("Verifying source directories...")
        for directory in self._config_manager.get_directories():
            if not os.path.exists(directory):
                logger.warning("Configured source directory not found: %s", directory)

    def _init_database(self) -> None:
        """Open the database and apply any pending schema migrations."""
        # Import here: avoids a circular import at module load time and also
        # ensures the DB classes are only imported after logging is initialised.
        from db.analysis_db import AnalysisDB
        from db.metadata_db import MetadataDB

        self.status_changed.emit("Verifying database...")
        self._analysis_db = AnalysisDB()

        self.status_changed.emit("Applying database schema updates...")
        self._metadata_db = MetadataDB()

    def _rebuild_indexes(self) -> None:
        """Rebuild all SQLite indexes and refresh query-planner statistics."""
        self.status_changed.emit("Rebuilding database indexes...")
        try:
            raw_conn = self._analysis_db.connection.connection
            if raw_conn is None:
                raise RuntimeError("Database connection is not open")
            raw_conn.execute("REINDEX")
            raw_conn.execute("ANALYZE")
            self._analysis_db.connection.commit()
        except Exception:
            logger.exception("Non-fatal error rebuilding database indexes")
        finally:
            # Close worker-owned connections; the main thread will open its own.
            # Use separate try/except so a failure on the first close never
            # prevents the second connection from being released.
            for db in (self._analysis_db, self._metadata_db):
                with contextlib.suppress(Exception):
                    db.close()

    def _refresh_models(self) -> None:
        """Attempt a fast refresh of the Ollama model list."""
        self.status_changed.emit("Refreshing available models...")
        try:
            from llm_providers.ollama_service import OllamaService

            base_url = self._config_manager.get_setting(
                "Ollama", "base_url", "http://localhost:11434"
            )
            # Use a short timeout so an unavailable server doesn't stall startup.
            service = OllamaService(base_url=base_url, timeout=5.0)
            service.list_models()
            logger.debug("Ollama model list refreshed successfully")
        except Exception:
            logger.debug("Ollama model refresh skipped (server not available or timed out)")


# ---------------------------------------------------------------------------
# Splash screen widget
# ---------------------------------------------------------------------------


class SplashScreen(QWidget):
    """
    Frameless splash screen shown during application initialisation.

    Layout (all elements are horizontally centred):

        ┌──────────────────────────────────────┐
        │                                      │
        │          WinScanLLM                  │  ← app name (bold, large)
        │                                      │
        │       [ scanner animation ]          │  ← scanner.gif
        │                                      │
        │     Verifying configuration...       │  ← live status text
        │                                      │
        └──────────────────────────────────────┘
    """

    def __init__(self, app_name: str, parent: "QWidget | None" = None) -> None:
        super().__init__(parent)
        self._app_name = app_name
        self._movie: QMovie | None = None
        self._setup_window()
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_status(self, text: str) -> None:
        """Update the live status label.  Must be called on the main thread.

        Thread-safety when updating from the worker is achieved by connecting
        ``InitializationWorker.status_changed`` to this slot, which causes Qt
        to use a queued connection and deliver the call on the main thread.
        """
        self._status_label.setText(text)

    def center_on_screen(self) -> None:
        """Move the splash so it is centred on the primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    # ------------------------------------------------------------------
    # Private setup helpers
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedSize(480, 430)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 28)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── App name ─────────────────────────────────────────────────────
        name_label = QLabel(self._app_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        name_label.setFont(font)
        name_label.setStyleSheet("color: white; letter-spacing: 1px;")
        layout.addWidget(name_label)

        # ── Scanner GIF ───────────────────────────────────────────────────
        self._scanner_label = QLabel()
        self._scanner_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._load_animation()
        layout.addWidget(self._scanner_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        # ── Status text ───────────────────────────────────────────────────
        self._status_label = QLabel("Initializing...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: rgba(148, 200, 255, 0.90); font-size: 10pt;")
        self._status_label.setFixedHeight(44)
        layout.addWidget(self._status_label)

        # Dark blue background to match the main window
        self.setStyleSheet("background-color: #0B1120;")

    def _load_animation(self) -> None:
        """
        Load *assets/scanner.gif* and start playback on the scanner label.

        Mirrors the logic used in StartupWindow so the visual experience is
        consistent between the splash and the main window.
        """
        # This file lives in src/ui/; the project root is two levels up.
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        gif_path = os.path.join(project_root, "assets", "scanner.gif")

        if not os.path.exists(gif_path):
            self._scanner_label.setText("[ animation unavailable ]")
            self._scanner_label.setStyleSheet("color: rgba(255,255,255,0.3); font-size: 9pt;")
            return

        movie = QMovie(gif_path)
        movie.setCacheMode(QMovie.CacheMode.CacheNone)

        if not movie.isValid():
            self._scanner_label.setText("[ animation unavailable ]")
            return

        # Determine scaled display size; cap at 220 × 220 for the splash.
        movie.jumpToFrame(0)
        orig = movie.currentImage().size()
        if orig.width() <= 0 or orig.height() <= 0:
            orig = movie.frameRect().size()

        max_dim = 220
        if orig.width() > 0 and orig.height() > 0:
            if orig.width() > max_dim or orig.height() > max_dim:
                scale = min(max_dim / orig.width(), max_dim / orig.height())
                scaled = QSize(int(orig.width() * scale), int(orig.height() * scale))
            else:
                scaled = orig
        else:
            scaled = QSize(max_dim, max_dim)

        movie.setScaledSize(scaled)
        self._scanner_label.setMovie(movie)
        self._scanner_label.setFixedSize(scaled)
        movie.setSpeed(100)
        movie.start()
        self._movie = movie  # Keep a reference to prevent garbage collection
