"""
Datetime utilities for consistent timezone handling.

SQLite's CURRENT_TIMESTAMP returns UTC time, so all database timestamps
need to be converted to local timezone for display.
"""

from datetime import datetime, timezone
from typing import Any


def utc_to_local(dt: datetime) -> datetime:
    """
    Convert UTC datetime to local timezone.

    Args:
        dt: Datetime object (assumed to be UTC if naive)

    Returns:
        Datetime in local timezone
    """
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to local timezone
    return dt.astimezone()


def format_db_timestamp(
    timestamp_str: str | None, format_string: str = "%Y-%m-%d %I:%M:%S %p"
) -> str:
    """
    Format a database timestamp (UTC) to local timezone string.

    Args:
        timestamp_str: ISO format timestamp string from database (UTC)
        format_string: strftime format string

    Returns:
        Formatted datetime string in local timezone
    """
    if not timestamp_str:
        return "N/A"

    try:
        # Parse ISO string (from SQLite CURRENT_TIMESTAMP)
        dt_utc = datetime.fromisoformat(timestamp_str)

        # Convert to local timezone
        dt_local = utc_to_local(dt_utc)

        # Format
        return dt_local.strftime(format_string)
    except (ValueError, TypeError, AttributeError):
        return str(timestamp_str)


def format_datetime_for_display(dt: Any, format_string: str = "%Y-%m-%d %I:%M:%S %p") -> str:
    """
    Format any datetime value for display.

    Handles:
    - datetime objects (converted from UTC to local)
    - ISO timestamp strings (converted from UTC to local)
    - Unix timestamps (already local)
    - None/invalid values

    Args:
        dt: Datetime value (string, datetime, or timestamp)
        format_string: strftime format string

    Returns:
        Formatted datetime string in local timezone
    """
    if not dt:
        return "N/A"

    # String - assume ISO format from database (UTC)
    if isinstance(dt, str):
        return format_db_timestamp(dt, format_string)

    # datetime object - convert from UTC to local
    if isinstance(dt, datetime):
        dt_local = utc_to_local(dt)
        return dt_local.strftime(format_string)

    # Fallback
    return str(dt)
