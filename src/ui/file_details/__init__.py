"""File details grid and dialog components."""

from ui.file_details.file_details_dialog import FileDetailsDialog
from ui.file_details.file_details_filter_model import FileDetailsSortFilterProxyModel
from ui.file_details.file_details_grid import FileDetailsGrid
from ui.file_details.file_details_table_model import FileDetailsTableModel

__all__ = [
    "FileDetailsGrid",
    "FileDetailsDialog",
    "FileDetailsTableModel",
    "FileDetailsSortFilterProxyModel",
]
