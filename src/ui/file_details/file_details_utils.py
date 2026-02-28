"""
File Details Shared Utilities

Shared helper functions used by FileDetailsDialog and FileDetailsGrid to avoid
code duplication between the dialog and grid action mixins.
"""

import os

from services.logging_service import get_logger

logger = get_logger()


def find_actual_file_path(
    stored_path: str | None,
    filename: str,
    source_dirs: list[str],
) -> str | None:
    """
    Find the actual file path by checking the stored path and searching source directories.

    First checks if the stored path exists and is not in a temp folder.
    If not, searches all configured source directories for a file with the given name.

    Args:
        stored_path: The path stored in the database (may be stale or in a temp folder).
        filename: The base filename (or full path whose basename is used) to search for.
        source_dirs: List of source directory paths to search.

    Returns:
        The resolved absolute file path, or None if the file cannot be found.
    """
    basename = os.path.basename(filename)

    # Check if stored path exists and is not in a temp folder
    if stored_path and os.path.exists(stored_path):
        temp_indicators = ["temp", "tmp", "AppData\\Local\\Temp"]
        if not any(indicator in stored_path for indicator in temp_indicators):
            return stored_path

    # Search configured source directories
    for directory in source_dirs:
        if not os.path.exists(directory):
            continue

        for root, _, files in os.walk(directory):
            if basename in files:
                found_path = os.path.join(root, basename)
                if os.path.exists(found_path):
                    return found_path

    return None


def is_path_confined(file_path: str, source_dirs: list[str]) -> bool:
    """
    Check whether a file path is under one of the configured source directories.

    Uses os.path.commonpath to validate confinement, preventing path traversal
    outside the allowed directories.

    Args:
        file_path: The absolute file path to validate.
        source_dirs: List of allowed source directory paths.

    Returns:
        True if file_path is within at least one source directory, False otherwise.
    """
    normalized = os.path.normpath(os.path.abspath(file_path))
    for directory in source_dirs:
        try:
            normalized_dir = os.path.normpath(os.path.abspath(directory))
            common = os.path.commonpath([normalized, normalized_dir])
            if common == normalized_dir:
                return True
        except ValueError:
            # commonpath raises ValueError on Windows when paths are on different drives
            continue
    return False


def get_file_details_theme_colors(is_dark: bool) -> dict:
    """
    Return a color palette dict for the file details UI based on the theme flag.

    This is the authoritative source for theme colors shared between
    FileDetailsDialog and FileDetailsGrid.  The grid carries additional
    tertiary / tab colors that the dialog does not use; those extra keys are
    included here so that both consumers can call this single function.

    Args:
        is_dark: True to return dark-mode colors, False for light-mode colors.

    Returns:
        A dict mapping color-role names to CSS hex color strings.
    """
    if is_dark:
        return {
            "bg_primary": "#0B1120",
            "bg_secondary": "#151D2F",
            "bg_tertiary": "#1F2A40",
            "text_primary": "#E0E0E0",
            "text_secondary": "#B0B0B0",
            "text_tertiary": "#808080",
            "border": "#2A3550",
            "input_bg": "#151D2F",
            "accent": "#3B82F6",
            "button_bg": "#1F2A40",
            "button_hover": "#2A3550",
            "tab_active_bg": "#151D2F",
            "tab_inactive_bg": "#0B1120",
            "tab_hover_bg": "#1F2A40",
        }
    else:
        return {
            "bg_primary": "#FFFFFF",
            "bg_secondary": "#F9FAFB",
            "bg_tertiary": "#F3F4F6",
            "text_primary": "#111827",
            "text_secondary": "#374151",
            "text_tertiary": "#6B7280",
            "border": "#E5E7EB",
            "input_bg": "#FFFFFF",
            "accent": "#3B82F6",
            "button_bg": "#F3F4F6",
            "button_hover": "#EFF6FF",
            "tab_active_bg": "#FFFFFF",
            "tab_inactive_bg": "#F3F4F6",
            "tab_hover_bg": "#E5E7EB",
        }
