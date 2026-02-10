"""Tests for datetime utility functions."""

from datetime import datetime, timezone

from ui.datetime_utils import format_datetime_for_display, format_db_timestamp, utc_to_local


class TestDatetimeUtils:
    """Test datetime conversion and formatting utilities."""

    def test_utc_to_local_with_naive_datetime(self):
        """Test converting naive datetime (assumed UTC) to local."""
        # Create a naive datetime (no timezone)
        naive_dt = datetime(2024, 1, 15, 14, 30, 0)

        # Convert to local
        local_dt = utc_to_local(naive_dt)

        # Should have timezone info
        assert local_dt.tzinfo is not None

        # Should be different from UTC (unless you're in UTC timezone)
        # Can't assert exact values since they depend on system timezone

    def test_utc_to_local_with_aware_datetime(self):
        """Test converting timezone-aware UTC datetime to local."""
        # Create UTC datetime
        utc_dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)

        # Convert to local
        local_dt = utc_to_local(utc_dt)

        # Should have timezone info
        assert local_dt.tzinfo is not None

        # Should represent the same moment in time
        assert utc_dt.timestamp() == local_dt.timestamp()

    def test_format_db_timestamp_with_valid_string(self):
        """Test formatting SQLite timestamp string."""
        # SQLite CURRENT_TIMESTAMP format
        timestamp_str = "2024-01-15 14:30:00"

        # Format to local time
        result = format_db_timestamp(timestamp_str)

        # Should be formatted (exact value depends on system timezone)
        assert result != "N/A"
        assert len(result) > 0

    def test_format_db_timestamp_with_none(self):
        """Test formatting None timestamp."""
        result = format_db_timestamp(None)
        assert result == "N/A"

    def test_format_db_timestamp_with_empty_string(self):
        """Test formatting empty string."""
        result = format_db_timestamp("")
        assert result == "N/A"

    def test_format_db_timestamp_with_custom_format(self):
        """Test formatting with custom format string."""
        timestamp_str = "2024-01-15 14:30:00"

        # Use custom format
        result = format_db_timestamp(timestamp_str, "%Y-%m-%d")

        # Should be date only
        assert result != "N/A"
        assert ":" not in result  # No time component

    def test_format_db_timestamp_with_invalid_string(self):
        """Test formatting invalid timestamp string."""
        result = format_db_timestamp("not a timestamp")

        # Should return the original string
        assert result == "not a timestamp"

    def test_format_datetime_for_display_with_string(self):
        """Test formatting ISO string for display."""
        iso_string = "2024-01-15 14:30:00"

        result = format_datetime_for_display(iso_string)

        # Should be formatted
        assert result != "N/A"
        assert len(result) > 0

    def test_format_datetime_for_display_with_datetime(self):
        """Test formatting datetime object for display."""
        dt = datetime(2024, 1, 15, 14, 30, 0)

        result = format_datetime_for_display(dt)

        # Should be formatted
        assert result != "N/A"
        assert "2024-01-15" in result

    def test_format_datetime_for_display_with_none(self):
        """Test formatting None value."""
        result = format_datetime_for_display(None)
        assert result == "N/A"

    def test_format_datetime_for_display_with_empty_string(self):
        """Test formatting empty string."""
        result = format_datetime_for_display("")
        assert result == "N/A"

    def test_format_datetime_preserves_same_moment(self):
        """Test that UTC to local conversion preserves the moment in time."""
        # Create a known UTC timestamp
        utc_dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        utc_timestamp_seconds = utc_dt.timestamp()

        # Convert to local
        local_dt = utc_to_local(utc_dt)
        local_timestamp_seconds = local_dt.timestamp()

        # Should represent the same moment
        assert utc_timestamp_seconds == local_timestamp_seconds
