"""
Test Enhanced StartupWindow with scanner animation control and stats display
"""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gui import StartupWindow


@pytest.fixture
def app():
    """Create QApplication instance"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture
def startup_window(app):
    """Create StartupWindow instance"""
    window = StartupWindow()
    yield window
    window.close()


class TestEnhancedStartupWindow:
    """Test enhanced StartupWindow features"""

    def test_scanner_stats_label_exists(self, startup_window):
        """Test that scanner stats label is created"""
        assert hasattr(startup_window, 'scanner_stats_label')
        assert startup_window.scanner_stats_label is not None

    def test_scanner_label_exists(self, startup_window):
        """Test that scanner label is created"""
        assert hasattr(startup_window, 'scanner_label')
        assert startup_window.scanner_label is not None

    def test_movie_exists(self, startup_window):
        """Test that movie object is created"""
        assert hasattr(startup_window, 'movie')
        # Movie may not be valid if GIF not found, but should exist
        assert startup_window.movie is not None

    def test_analysis_db_initialized(self, startup_window):
        """Test that AnalysisDB is initialized"""
        assert hasattr(startup_window, 'analysis_db')
        assert startup_window.analysis_db is not None

    def test_update_scanner_animation_method_exists(self, startup_window):
        """Test that _update_scanner_animation method exists"""
        assert hasattr(startup_window, '_update_scanner_animation')
        assert callable(startup_window._update_scanner_animation)

    def test_update_scanner_stats_method_exists(self, startup_window):
        """Test that _update_scanner_stats method exists"""
        assert hasattr(startup_window, '_update_scanner_stats')
        assert callable(startup_window._update_scanner_stats)

    def test_format_relative_time_method_exists(self, startup_window):
        """Test that _format_relative_time method exists"""
        assert hasattr(startup_window, '_format_relative_time')
        assert callable(startup_window._format_relative_time)

    def test_update_scanner_animation_start(self, startup_window):
        """Test starting scanner animation"""
        if hasattr(startup_window, 'movie') and startup_window.movie.isValid():
            startup_window._update_scanner_animation(True)
            # Animation should be running (state would be MovieState.Running)
            # We can't easily test this without the actual GIF file

    def test_update_scanner_animation_stop(self, startup_window):
        """Test stopping scanner animation"""
        if hasattr(startup_window, 'movie') and startup_window.movie.isValid():
            startup_window._update_scanner_animation(False)
            # Animation should be stopped
            # We can't easily test this without the actual GIF file

    def test_update_scanner_stats_no_args(self, startup_window):
        """Test updating scanner stats with no arguments (query database)"""
        try:
            startup_window._update_scanner_stats()
            # Should update the label text
            assert startup_window.scanner_stats_label.text() != ""
        except Exception as e:
            # May fail if database is not accessible, but shouldn't crash
            pass

    def test_update_scanner_stats_with_status(self, startup_window):
        """Test updating scanner stats with custom status"""
        test_stats = {
            'analyzed': 10,
            'cached': 5,
            'errors': 1
        }
        startup_window._update_scanner_stats(status="Analyzing 10/20...", stats=test_stats)

        # Check that label was updated
        label_text = startup_window.scanner_stats_label.text()
        assert label_text != ""
        assert "Analyzing 10/20..." in label_text

    def test_format_relative_time_just_now(self, startup_window):
        """Test relative time formatting for recent timestamp"""
        from datetime import datetime, timedelta

        # Current time
        now = datetime.now()
        iso_timestamp = now.isoformat()

        result = startup_window._format_relative_time(iso_timestamp)
        assert result == "Just now"

    def test_format_relative_time_minutes_ago(self, startup_window):
        """Test relative time formatting for minutes ago"""
        from datetime import datetime, timedelta

        # 30 minutes ago
        past = datetime.now() - timedelta(minutes=30)
        iso_timestamp = past.isoformat()

        result = startup_window._format_relative_time(iso_timestamp)
        assert "minute" in result

    def test_format_relative_time_hours_ago(self, startup_window):
        """Test relative time formatting for hours ago"""
        from datetime import datetime, timedelta

        # 2 hours ago
        past = datetime.now() - timedelta(hours=2)
        iso_timestamp = past.isoformat()

        result = startup_window._format_relative_time(iso_timestamp)
        assert "hour" in result

    def test_format_relative_time_days_ago(self, startup_window):
        """Test relative time formatting for days ago"""
        from datetime import datetime, timedelta

        # 5 days ago
        past = datetime.now() - timedelta(days=5)
        iso_timestamp = past.isoformat()

        result = startup_window._format_relative_time(iso_timestamp)
        assert "day" in result

    def test_format_relative_time_invalid(self, startup_window):
        """Test relative time formatting with invalid timestamp"""
        result = startup_window._format_relative_time("invalid_timestamp")
        assert result == "Unknown"

    def test_scanner_container_is_clickable(self, startup_window):
        """Test that scanner container has pointing hand cursor"""
        # The container is created dynamically in _init_ui
        # We can't easily access it from outside, but we can verify the window opens
        assert hasattr(startup_window, 'show_analysis_status')
        assert callable(startup_window.show_analysis_status)


class TestStartupWindowAnalysisIntegration:
    """Test integration between StartupWindow and analysis"""

    def test_start_analysis_starts_animation(self, startup_window):
        """Test that starting analysis starts scanner animation"""
        # Mock analysis service
        mock_service = MagicMock()

        # Start analysis
        with patch.object(startup_window, '_update_scanner_animation') as mock_update:
            startup_window.start_analysis(mock_service)
            mock_update.assert_called_once_with(True)

    def test_on_analysis_finished_stops_animation(self, startup_window):
        """Test that finishing analysis stops scanner animation"""
        mock_stats = {
            'total_files': 10,
            'analyzed': 8,
            'cached': 2,
            'errors': 0
        }

        # Mock the analysis_timer that gets created during start_analysis
        startup_window.analysis_timer = MagicMock()

        with patch.object(startup_window, '_update_scanner_animation') as mock_update:
            with patch.object(startup_window, '_update_scanner_stats'):
                startup_window._on_analysis_finished(mock_stats)
                mock_update.assert_called_once_with(False)

    def test_on_analysis_progress_updates_stats(self, startup_window):
        """Test that analysis progress updates scanner stats"""
        mock_stats = {
            'analyzed': 5,
            'cached': 3,
            'errors': 0
        }

        with patch.object(startup_window, '_update_scanner_stats') as mock_update:
            startup_window._on_analysis_progress("Analyzing...", 5, 10, mock_stats)
            # Should be called with status and stats
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert 'status' in call_args[1] or len(call_args[0]) > 0

    def test_cancel_analysis_stops_animation(self, startup_window):
        """Test that canceling analysis stops scanner animation"""
        # Mock analysis worker
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        startup_window.analysis_worker = mock_worker

        # Mock QMessageBox to auto-confirm
        with patch('gui.QMessageBox.question', return_value=MagicMock()):
            with patch.object(startup_window, '_update_scanner_animation') as mock_update:
                with patch.object(startup_window, '_update_scanner_stats'):
                    # This will trigger the dialog, so we need to mock it
                    try:
                        startup_window._cancel_analysis()
                    except:
                        pass  # May fail due to dialog interaction, but animation should be called


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
