"""
File Details Sort/Filter Proxy Model

Provides filtering and sorting capabilities for the file details table.
"""

from datetime import datetime, timezone
from typing import Any

from PyQt6.QtCore import QModelIndex, QSortFilterProxyModel, Qt

from ui.file_details.file_details_table_model import FileDetailsTableModel


class FileDetailsSortFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy model for filtering and sorting file details.

    Supports:
    - Column-specific filters
    - Full-text search across all columns
    - Quick filter presets
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._column_filters: dict[str, Any] = {}
        self._search_text: str = ""
        self._quick_filter: str | None = None

    def set_filters(self, filters: dict[str, Any]):
        """Set column-specific filters."""
        self._column_filters = filters.copy()
        self.invalidateFilter()

    def set_search_text(self, text: str):
        """Set full-text search filter."""
        self._search_text = text.lower().strip()
        self.invalidateFilter()

    def set_quick_filter(self, filter_name: str | None):
        """Set quick filter preset."""
        self._quick_filter = filter_name
        self.invalidateFilter()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:  # noqa: N802
        """Sort using the model's UserRole sort key when it provides one.

        Datetime columns expose an epoch float via UserRole so they sort
        chronologically despite a MM/DD/YYYY display string; all other columns
        fall back to Qt's default DisplayRole comparison.
        """
        model = self.sourceModel()
        if model is None:
            return bool(super().lessThan(left, right))
        left_key = model.data(left, Qt.ItemDataRole.UserRole)
        right_key = model.data(right, Qt.ItemDataRole.UserRole)
        if left_key is not None and right_key is not None:
            try:
                return bool(left_key < right_key)
            except TypeError:
                pass
        # Missing key on one side → push it below the populated one.
        if left_key is None and right_key is not None:
            return True
        if left_key is not None and right_key is None:
            return False
        return bool(super().lessThan(left, right))

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        """Determine if a row should be visible."""
        model = self.sourceModel()
        if not isinstance(model, FileDetailsTableModel):
            return True

        row_data = model.get_row_data(source_row)
        if not row_data:
            return False

        # Apply quick filter
        if self._quick_filter and not self._apply_quick_filter(row_data):
            return False

        # Apply column filters
        for col_key, filter_value in self._column_filters.items():
            if not filter_value:
                continue

            row_value = row_data.get(col_key)

            # Handle different filter types
            if isinstance(filter_value, list | tuple | set):
                if row_value not in filter_value:
                    return False
            else:
                if str(row_value).lower() != str(filter_value).lower():
                    return False

        # Apply search text
        return not self._search_text or self._search_in_row(row_data)

    def _apply_quick_filter(self, row_data: dict[str, Any]) -> bool:
        """Apply quick filter logic."""
        if self._quick_filter == "high_confidence":
            confidence = row_data.get("confidence", 0)
            try:
                return float(confidence) >= 80
            except (ValueError, TypeError):
                return False

        elif self._quick_filter == "needs_review":
            # Filter to images that need review: Failed, Analyzed, or low confidence
            status = row_data.get("status", "")

            # Include if status is Failed (error) or Analyzed (awaiting review)
            if status in ("Failed", "Analyzed"):
                return True

            # Also include if confidence is low (< 80)
            confidence = row_data.get("confidence", 100)
            try:
                return float(confidence) < 80
            except (ValueError, TypeError):
                return True

        elif self._quick_filter == "multi_page":
            total_pages = row_data.get("total_pages")
            if total_pages is None:
                return False
            try:
                return int(total_pages) > 1
            except (ValueError, TypeError):
                return False

        elif self._quick_filter == "recent":
            analysis_time = row_data.get("analysis_time")
            if not analysis_time:
                return False
            try:
                if isinstance(analysis_time, str):
                    analysis_time = datetime.fromisoformat(analysis_time)
                if isinstance(analysis_time, datetime):
                    now = datetime.now(timezone.utc)
                    # Ensure both datetimes are comparable: strip tz if analysis_time is naive
                    if analysis_time.tzinfo is None:
                        now = now.replace(tzinfo=None)
                    hours_ago = (now - analysis_time).total_seconds() / 3600
                    return hours_ago < 24
            except (ValueError, TypeError):
                pass
            return False

        elif self._quick_filter == "has_errors":
            # Check if status is Failed or if there's an error message
            status = row_data.get("status", "")
            error_msg = row_data.get("error_message", "")
            return status == "Failed" or bool(error_msg)

        elif self._quick_filter == "missing_metadata":
            # Check if BOTH company AND date are missing (at least one of these must be present)
            company = row_data.get("company", "")
            document_date = row_data.get("document_date", "")

            # Missing if field is empty, None, or 'N/A'
            company_missing = not company or company in ("N/A", "None", "")
            date_missing = not document_date or document_date in ("N/A", "None", "")

            # Only considered missing metadata if BOTH company AND date are missing
            return company_missing and date_missing

        elif self._quick_filter == "cached_only":
            return bool(row_data.get("cache_hit"))

        elif self._quick_filter == "blank_pages":
            # Filter to pages marked as blank (is_blank = True)
            is_blank = row_data.get("is_blank", False)
            return bool(is_blank)

        return True

    def _search_in_row(self, row_data: dict[str, Any]) -> bool:
        """Check if search text appears in any column."""
        search_text = self._search_text

        # Search in all string-like fields
        searchable_fields = [
            "filename",
            "company",
            "document_type",
            "document_date",
            "status",
            "error_message",
            "model_used",
            "provider",
            "full_path",
        ]

        for field in searchable_fields:
            value = row_data.get(field)
            if value and search_text in str(value).lower():
                return True

        return False
