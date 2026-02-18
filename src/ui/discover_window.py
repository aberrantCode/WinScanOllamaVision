"""
Discover Window for reviewing and managing discovered images.

Provides a dedicated interface for:
- Previewing images before analysis
- Filtering by analysis status
- Organizing by source directory
- Cleaning up unwanted images
- Excluding specific images from analysis
"""

import logging
import os
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.repositories.image_files_repo import ImageFilesRepository
from services.discovery_worker import DiscoveryWorker
from ui.image_preview_widget import ImagePreviewWidget, ToolbarPosition, ToolbarSize
from ui.styles import Colors

if TYPE_CHECKING:
    from services.logging_service import get_logger
else:
    get_logger = None

logger: logging.Logger | None = None


class DiscoverWindow(QDialog):
    """
    Window for discovering and managing image files.

    Allows users to review discovered images, filter by status/directory,
    and perform actions like unregister, delete, or ignore.
    """

    # Signals
    files_changed = pyqtSignal()  # Emitted when files are modified
    files_deleted = pyqtSignal(list)  # Emitted with list of deleted file paths
    files_unregistered = pyqtSignal(list)  # Emitted with list of unregistered file paths
    files_ignored = pyqtSignal(list)  # Emitted with list of ignored file paths

    def __init__(
        self,
        analysis_db: AnalysisDB,
        config_manager: ConfigManager | None = None,
        parent: QWidget | None = None,
    ):
        """
        Initialize Discover window.

        Args:
            analysis_db: Analysis database instance
            config_manager: Configuration manager (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.analysis_db = analysis_db
        self.config_manager = config_manager or ConfigManager()
        self.dark_mode = False

        # Debug: Log instance ID
        self._get_logger().info(f"[DISCOVER] DiscoverWindow __init__ - instance ID: {id(self)}")

        # Get theme
        if config_manager:
            theme = config_manager.get_setting("Theme", "theme", "light")
            self.dark_mode = theme == "dark"

        # UI components (initialized in _init_ui)
        self.directory_combo: QComboBox | None = None
        self.show_analyzed_checkbox: QCheckBox | None = None
        self.refresh_button: QPushButton | None = None
        self.discover_button: QPushButton | None = None
        self.progress_bar: QProgressBar | None = None
        self.image_tree: QTreeWidget | None = None
        self.tree_header_label: QLabel | None = None
        self.preview_widget: ImagePreviewWidget | None = None
        self.file_info_label: QLabel | None = None
        self.analysis_status_label: QLabel | None = None
        self.unregister_button: QPushButton | None = None
        self.delete_button: QPushButton | None = None
        self.ignore_button: QPushButton | None = None

        # Discovery worker
        self.discovery_worker: DiscoveryWorker | None = None

        # Initialize UI
        self._init_ui()

        # Populate directory dropdown and load initial data after UI is fully initialized
        # Use QTimer to ensure all Qt initialization is complete
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(0, self._post_init_setup)

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    def _post_init_setup(self) -> None:
        """
        Complete initialization after Qt event loop starts.

        Called via QTimer.singleShot to ensure all UI components are fully initialized.
        """
        # Debug: Check state at start of _post_init_setup
        self._get_logger().info(
            f"[DISCOVER] _post_init_setup called - directory_combo is {'None' if not self.directory_combo else 'OK'}, instance ID: {id(self)}"
        )

        # Populate directory dropdown
        try:
            self._populate_directory_dropdown()
        except Exception as e:
            self._get_logger().error(
                f"[DISCOVER] Failed to populate directory dropdown: {e}", exc_info=True
            )
            # Ensure at least "All Directories" is present
            if self.directory_combo:
                self.directory_combo.addItem("All Directories")

        # Load initial data
        self._refresh_images()

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        self.setWindowTitle("Discover Images")
        self.setModal(True)
        self.resize(1200, 800)

        # Main layout
        layout = QVBoxLayout(self)

        # Add controls bar
        controls_layout = self._create_controls_bar()
        layout.addLayout(controls_layout)

        # Debug: Check immediately after creating controls
        self._get_logger().info(
            f"[DISCOVER] After _create_controls_bar - directory_combo is {'None' if not self.directory_combo else 'OK'}"
        )

        # Add progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(25)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Add main content (splitter with tree and preview)
        splitter = self._create_main_splitter()
        layout.addWidget(splitter)

        # Debug: Check after creating splitter
        self._get_logger().info(
            f"[DISCOVER] After _create_main_splitter - directory_combo is {'None' if not self.directory_combo else 'OK'}"
        )

        # Add dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Apply theme
        self._apply_theme()

        # Debug: Check after applying theme
        self._get_logger().info(
            f"[DISCOVER] After _apply_theme - directory_combo is {'None' if not self.directory_combo else 'OK'}"
        )

        # Debug: Check if directory_combo is still valid after _init_ui completes
        self._get_logger().info(
            f"[DISCOVER] _init_ui completed - directory_combo is {'None' if not self.directory_combo else 'OK'}, instance ID: {id(self)}"
        )

    def _create_controls_bar(self) -> QHBoxLayout:
        """
        Create top controls bar with filters and discovery button.

        Returns:
            Layout containing filter controls
        """
        self._get_logger().info(f"[DISCOVER] _create_controls_bar called - instance ID: {id(self)}")
        controls_layout = QHBoxLayout()

        # Directory filter
        dir_label = QLabel("Directory:")
        dir_label.setFixedHeight(30)
        controls_layout.addWidget(dir_label)

        self._get_logger().info("[DISCOVER] Creating directory_combo")
        self.directory_combo = QComboBox()
        self._get_logger().info(
            f"[DISCOVER] IMMEDIATELY after assignment - directory_combo is {'None' if not self.directory_combo else 'OK'}, id={id(self.directory_combo) if self.directory_combo else 'N/A'}"
        )
        self._get_logger().info(
            f"[DISCOVER] directory_combo created: {self.directory_combo is not None}"
        )
        self.directory_combo.setFixedHeight(30)
        self._get_logger().info(
            f"[DISCOVER] After setFixedHeight - directory_combo is {'None' if not self.directory_combo else 'OK'}"
        )
        self.directory_combo.setMinimumWidth(200)
        self.directory_combo.currentIndexChanged.connect(self._refresh_images)
        controls_layout.addWidget(self.directory_combo, stretch=1)  # Expand to fill space

        # Show analyzed checkbox
        self.show_analyzed_checkbox = QCheckBox("Show analyzed images")
        self.show_analyzed_checkbox.setFixedHeight(30)
        self.show_analyzed_checkbox.setChecked(True)
        self.show_analyzed_checkbox.stateChanged.connect(self._refresh_images)
        controls_layout.addWidget(self.show_analyzed_checkbox)

        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setFixedHeight(30)
        self.refresh_button.setFixedWidth(80)
        self.refresh_button.clicked.connect(self._refresh_images)
        controls_layout.addWidget(self.refresh_button)

        # Discover button
        self.discover_button = QPushButton("Discover Images")
        self.discover_button.setFixedHeight(30)
        self.discover_button.setFixedWidth(140)
        self.discover_button.clicked.connect(self._on_discover_clicked)
        controls_layout.addWidget(self.discover_button)

        # Debug: Check directory_combo RIGHT before returning
        self._get_logger().info(
            f"[DISCOVER] Right before return from _create_controls_bar - directory_combo is {'None' if not self.directory_combo else 'OK'}, id={id(self.directory_combo) if self.directory_combo else 'N/A'}"
        )
        self._get_logger().info("[DISCOVER] _create_controls_bar completed successfully")
        return controls_layout

    def _create_main_splitter(self) -> QSplitter:
        """
        Create main splitter with image tree and preview panel.

        Returns:
            Splitter widget
        """
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Image tree
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # Right panel: Preview and info
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # Set initial splitter proportions (40% left, 60% right)
        splitter.setSizes([400, 600])

        return splitter

    def _create_left_panel(self) -> QWidget:
        """
        Create left panel with image tree and bulk actions.

        Returns:
            Widget containing tree and actions
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Tree header with count
        header_layout = QHBoxLayout()
        header_title = QLabel("<b>Discovered Images</b>")
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        self.tree_header_label = QLabel("0 images found")
        self.tree_header_label.setStyleSheet("color: #666;")
        header_layout.addWidget(self.tree_header_label)
        layout.addLayout(header_layout)

        # Image tree
        self.image_tree = QTreeWidget()
        self.image_tree.setHeaderLabels(["Image", "Status"])
        self.image_tree.setColumnWidth(0, 300)
        self.image_tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        layout.addWidget(self.image_tree)

        # Bulk actions bar
        actions_layout = QHBoxLayout()

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._on_select_all)
        actions_layout.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._on_deselect_all)
        actions_layout.addWidget(deselect_all_btn)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        # File info section
        info_group = QLabel("<b>File Information</b>")
        layout.addWidget(info_group)

        # File info label
        self.file_info_label = QLabel("No image selected")
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setMaximumHeight(100)
        layout.addWidget(self.file_info_label)

        # Analysis status label
        self.analysis_status_label = QLabel("")
        layout.addWidget(self.analysis_status_label)

        return panel

    def _create_right_panel(self) -> QWidget:
        """
        Create right panel with image preview and action buttons.

        Returns:
            Widget containing preview and actions
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Get theme colors
        theme_colors = self._get_theme_colors()

        # Image preview (full height)
        self.preview_widget = ImagePreviewWidget(
            toolbar_size=ToolbarSize.COMPACT,
            toolbar_position=ToolbarPosition.BOTTOM_CENTER,
            theme_colors=theme_colors,
            config_manager=self.config_manager,
            analysis_db=self.analysis_db,
        )
        layout.addWidget(self.preview_widget, stretch=1)

        # Action buttons
        actions_layout = QHBoxLayout()

        self.unregister_button = QPushButton("Unregister")
        self.unregister_button.setToolTip("Remove from database (file remains on disk)")
        self.unregister_button.clicked.connect(self._on_unregister_clicked)
        self.unregister_button.setEnabled(False)
        actions_layout.addWidget(self.unregister_button)

        self.delete_button = QPushButton("Delete from Disk")
        self.delete_button.setToolTip("Permanently delete file from disk")
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.delete_button.setEnabled(False)
        actions_layout.addWidget(self.delete_button)

        self.ignore_button = QPushButton("Ignore Analysis")
        self.ignore_button.setToolTip("Skip during future analysis scans")
        self.ignore_button.clicked.connect(self._on_ignore_clicked)
        self.ignore_button.setEnabled(False)
        actions_layout.addWidget(self.ignore_button)

        actions_layout.addStretch()
        layout.addLayout(actions_layout)

        return panel

    def _get_theme_colors(self) -> dict[str, str]:
        """
        Get theme colors based on current theme mode.

        Returns:
            Dictionary of theme colors
        """
        if self.dark_mode:
            return {
                "bg_primary": Colors.GRAY_900,
                "bg_secondary": Colors.GRAY_800,
                "text_primary": Colors.WHITE,
                "text_secondary": Colors.GRAY_400,
                "border": Colors.GRAY_700,
                "accent": Colors.PRIMARY,
                "button_bg": Colors.GRAY_800,
                "button_hover": Colors.GRAY_700,
            }
        else:
            return {
                "bg_primary": Colors.WHITE,
                "bg_secondary": Colors.GRAY_100,
                "text_primary": Colors.GRAY_900,
                "text_secondary": Colors.GRAY_700,
                "border": Colors.GRAY_300,
                "accent": Colors.PRIMARY,
                "button_bg": Colors.GRAY_100,
                "button_hover": Colors.PRIMARY_PALE,
            }

    def _apply_theme(self) -> None:
        """Apply theme styling to the window."""
        colors = self._get_theme_colors()

        # Apply to main window
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {colors['bg_primary']};
                color: {colors['text_primary']};
            }}
            QWidget {{
                background-color: {colors['bg_primary']};
                color: {colors['text_primary']};
            }}
            QLabel {{
                color: {colors['text_primary']};
                background-color: transparent;
            }}
            QPushButton {{
                background-color: {colors['button_bg']};
                color: {colors['text_primary']};
                border: 1px solid {colors['border']};
                padding: 5px 15px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {colors['button_hover']};
            }}
            QPushButton:disabled {{
                background-color: {colors['bg_secondary']};
                color: {colors['text_secondary']};
            }}
            QTreeWidget {{
                background-color: {colors['bg_primary']};
                color: {colors['text_primary']};
                border: 1px solid {colors['border']};
            }}
            QComboBox {{
                background-color: {colors['button_bg']};
                color: {colors['text_primary']};
                border: 1px solid {colors['border']};
                padding: 5px;
                min-height: 25px;
            }}
            QComboBox:drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {colors['text_primary']};
                width: 0;
                height: 0;
            }}
            QComboBox QAbstractItemView {{
                background-color: {colors['button_bg']};
                color: {colors['text_primary']};
                border: 1px solid {colors['border']};
                selection-background-color: {colors['accent']};
                selection-color: {colors['bg_primary']};
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 25px;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {colors['button_hover']};
            }}
            QCheckBox {{
                color: {colors['text_primary']};
                background-color: transparent;
            }}
            QProgressBar {{
                background-color: {colors['bg_secondary']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                text-align: center;
                color: {colors['text_primary']};
            }}
            QProgressBar::chunk {{
                background-color: {colors['accent']};
                border-radius: 3px;
            }}
        """
        )

    def _load_images(self) -> dict[str, list[dict[str, Any]]]:
        """
        Load images from database with current filters applied.

        Returns:
            Dict mapping directory_path to list of image dicts
        """
        image_repo = ImageFilesRepository(self.analysis_db.connection)

        # Get all non-deleted images
        all_images = image_repo.get_all()

        # Apply directory filter
        directory_filter = (
            self.directory_combo.currentText() if self.directory_combo else "All Directories"
        )
        if directory_filter != "All Directories":
            all_images = [img for img in all_images if img["directory_path"] == directory_filter]

        # Apply analysis status filter
        if self.show_analyzed_checkbox and not self.show_analyzed_checkbox.isChecked():
            all_images = [img for img in all_images if img["status"] != "analyzed"]

        # Always exclude ignored images from default view
        all_images = [img for img in all_images if not img.get("is_ignored", False)]

        # Group by directory
        grouped: dict[str, list[dict[str, Any]]] = {}
        for img in all_images:
            dir_path = img["directory_path"]
            if dir_path not in grouped:
                grouped[dir_path] = []
            grouped[dir_path].append(img)

        return grouped

    def _refresh_images(self) -> None:
        """Refresh the image list and update UI."""
        # Load images with current filters
        grouped_images = self._load_images()

        # Populate tree
        self._populate_tree(grouped_images)

        # Update tree header label
        total_count = sum(len(images) for images in grouped_images.values())
        if self.tree_header_label:
            self.tree_header_label.setText(f"{total_count} images found")

    def _populate_tree(self, grouped_images: dict[str, list[dict[str, Any]]]) -> None:
        """
        Populate tree widget with images grouped by directory.

        Args:
            grouped_images: Dict mapping directory_path to list of image dicts
        """
        if not self.image_tree:
            return

        self.image_tree.clear()

        for directory_path, images in sorted(grouped_images.items()):
            # Create parent item for directory
            dir_item = QTreeWidgetItem(self.image_tree)
            dir_item.setText(0, directory_path)
            dir_item.setExpanded(True)

            # Style directory items (bold)
            font = dir_item.font(0)
            font.setBold(True)
            dir_item.setFont(0, font)

            # Add child items for each image
            for img in images:
                img_item = QTreeWidgetItem(dir_item)

                # Display filename
                img_item.setText(0, img["filename"])

                # Add checkbox for selection
                img_item.setFlags(img_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                img_item.setCheckState(0, Qt.CheckState.Unchecked)

                # Store full data
                img_item.setData(0, Qt.ItemDataRole.UserRole, img)

                # Visual indicator for analyzed status
                if img["status"] == "analyzed":
                    img_item.setForeground(0, QColor(Colors.SUCCESS))
                    img_item.setText(1, "✓ Analyzed")
                else:
                    img_item.setForeground(0, QColor(Colors.GRAY_600))
                    img_item.setText(1, "○ Registered")

    def refresh_directory_dropdown(self) -> None:
        """
        Public method to refresh the directory dropdown.
        Can be called externally when directories are updated in settings.
        """
        self._populate_directory_dropdown()

    def _populate_directory_dropdown(self) -> None:
        """
        Populate directory filter dropdown with all directories containing registered images.
        Falls back to configured source directories if no images found in database.
        """
        # Debug: Log who's calling this and the state
        import traceback

        self._get_logger().info(
            f"[DISCOVER] _populate_directory_dropdown called, directory_combo is {'None' if not self.directory_combo else 'OK'}, instance ID: {id(self)}"
        )
        self._get_logger().debug(f"[DISCOVER] Call stack:\n{''.join(traceback.format_stack())}")

        if not self.directory_combo:
            self._get_logger().warning("[DISCOVER] directory_combo is None, cannot populate")
            return

        # Save current selection
        current_text = self.directory_combo.currentText()

        # Block signals during update
        self.directory_combo.blockSignals(True)

        # Clear and repopulate
        self.directory_combo.clear()
        self.directory_combo.addItem("All Directories")

        unique_directories: set[str] = set()

        try:
            # Use the existing image_files repository from AnalysisDB
            all_images = self.analysis_db._image_files.get_all()

            self._get_logger().info(f"[DISCOVER] Retrieved {len(all_images)} images from database")

            # Extract unique directory paths (excluding ignored and deleted)
            for img in all_images:
                if not img.get("is_ignored", False):
                    dir_path = img.get("directory_path")
                    if dir_path:
                        unique_directories.add(dir_path)
                    else:
                        self._get_logger().warning(
                            f"[DISCOVER] Image {img.get('filename', 'unknown')} has no directory_path"
                        )

            self._get_logger().info(
                f"[DISCOVER] Found {len(unique_directories)} unique directories from database"
            )

            # Fallback: If no directories from database, use configured source directories
            if not unique_directories:
                configured_dirs = self.config_manager.get_directories()
                self._get_logger().info(
                    f"[DISCOVER] No directories from database, using {len(configured_dirs)} configured directories"
                )
                unique_directories = set(configured_dirs)

        except Exception as e:
            self._get_logger().error(f"[DISCOVER] Failed to query database: {e}", exc_info=True)
            # Fallback to configured directories on error
            unique_directories = set(self.config_manager.get_directories())

        # Add directories in sorted order
        for directory_path in sorted(unique_directories):
            self.directory_combo.addItem(directory_path)
            self._get_logger().debug(f"[DISCOVER] Added directory to combobox: {directory_path}")

        # Restore selection if possible
        index = self.directory_combo.findText(current_text)
        if index >= 0:
            self.directory_combo.setCurrentIndex(index)
        else:
            self.directory_combo.setCurrentIndex(0)

        self._get_logger().info(
            f"[DISCOVER] Directory dropdown populated with {self.directory_combo.count()} items"
        )

        # Unblock signals
        self.directory_combo.blockSignals(False)

    def _on_tree_selection_changed(self) -> None:
        """Handle tree selection change."""
        if not self.image_tree:
            return

        selected_items = self.image_tree.selectedItems()
        if not selected_items or len(selected_items) == 0:
            # No selection - disable buttons
            if self.unregister_button:
                self.unregister_button.setEnabled(False)
            if self.delete_button:
                self.delete_button.setEnabled(False)
            if self.ignore_button:
                self.ignore_button.setEnabled(False)
            if self.file_info_label:
                self.file_info_label.setText("No image selected")
            if self.analysis_status_label:
                self.analysis_status_label.setText("")
            return

        # Get first selected item
        item = selected_items[0]

        # Check if it's a directory item (has no data)
        img_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not img_data:
            # Directory item selected - disable buttons
            if self.unregister_button:
                self.unregister_button.setEnabled(False)
            if self.delete_button:
                self.delete_button.setEnabled(False)
            if self.ignore_button:
                self.ignore_button.setEnabled(False)
            return

        # Enable action buttons
        if self.unregister_button:
            self.unregister_button.setEnabled(True)
        if self.delete_button:
            self.delete_button.setEnabled(True)
        if self.ignore_button:
            self.ignore_button.setEnabled(True)

        # Update preview
        file_path = img_data["file_path"]
        if self.preview_widget and os.path.exists(file_path):
            from PyQt6.QtGui import QPixmap

            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.preview_widget.set_pixmap(pixmap, apply_fit="window", file_path=file_path)

        # Update file info
        file_size_mb = img_data["file_size"] / (1024 * 1024)
        info_text = f"<b>File:</b> {img_data['filename']}<br>"
        info_text += f"<b>Path:</b> {file_path}<br>"
        info_text += f"<b>Size:</b> {file_size_mb:.2f} MB<br>"
        info_text += f"<b>Status:</b> {img_data['status']}"
        if self.file_info_label:
            self.file_info_label.setText(info_text)

        # Update analysis status
        if img_data["status"] == "analyzed" and self.analysis_status_label:
            self.analysis_status_label.setText("<b>Analysis:</b> Completed")
        elif self.analysis_status_label:
            self.analysis_status_label.setText("<b>Analysis:</b> Not analyzed")

    def _on_select_all(self) -> None:
        """Select all images in tree."""
        if not self.image_tree:
            return

        root = self.image_tree.invisibleRootItem()
        if not root:
            return

        for i in range(root.childCount()):
            dir_item = root.child(i)
            if not dir_item:
                continue
            for j in range(dir_item.childCount()):
                img_item = dir_item.child(j)
                if img_item:
                    img_item.setCheckState(0, Qt.CheckState.Checked)

    def _on_deselect_all(self) -> None:
        """Deselect all images in tree."""
        if not self.image_tree:
            return

        root = self.image_tree.invisibleRootItem()
        if not root:
            return

        for i in range(root.childCount()):
            dir_item = root.child(i)
            if not dir_item:
                continue
            for j in range(dir_item.childCount()):
                img_item = dir_item.child(j)
                if img_item:
                    img_item.setCheckState(0, Qt.CheckState.Unchecked)

    def _get_selected_images(self) -> list[str]:
        """
        Get list of file paths for checked images.

        Returns:
            List of file paths
        """
        if not self.image_tree:
            return []

        selected_paths = []
        root = self.image_tree.invisibleRootItem()
        if not root:
            return []

        for i in range(root.childCount()):
            dir_item = root.child(i)
            if not dir_item:
                continue
            for j in range(dir_item.childCount()):
                img_item = dir_item.child(j)
                if img_item and img_item.checkState(0) == Qt.CheckState.Checked:
                    img_data = img_item.data(0, Qt.ItemDataRole.UserRole)
                    if img_data:
                        selected_paths.append(img_data["file_path"])

        return selected_paths

    def _on_unregister_clicked(self) -> None:
        """Handle unregister button click."""
        selected = self._get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select images to unregister.")
            return

        # Confirmation dialog
        msg = f"Unregister {len(selected)} image(s)?\n\n"
        msg += "This will:\n"
        msg += "• Remove the image(s) from the database\n"
        msg += "• Delete all analysis results and metadata\n"
        msg += "• NOT delete the physical files\n\n"
        msg += "Files can be re-discovered by running a new scan."

        reply = QMessageBox.question(
            self,
            "Confirm Unregister",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            image_repo = ImageFilesRepository(self.analysis_db.connection)

            for file_path in selected:
                image_repo.mark_deleted(file_path)

            # Emit signals
            self.files_unregistered.emit(selected)
            self.files_changed.emit()

            # Reload tree
            self._refresh_images()

            # Show confirmation (if window has statusBar)
            self._get_logger().info(f"Unregistered {len(selected)} image(s)")

    def _on_delete_clicked(self) -> None:
        """Handle delete from disk button click."""
        selected = self._get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select images to delete.")
            return

        # CRITICAL: Multi-step confirmation with safety checks
        msg = f"⚠️ PERMANENTLY DELETE {len(selected)} FILE(S) FROM DISK?\n\n"
        msg += "This action CANNOT be undone!\n\n"
        msg += "Files to be deleted:\n"
        msg += "\n".join(f"• {os.path.basename(fp)}" for fp in selected[:10])
        if len(selected) > 10:
            msg += f"\n... and {len(selected) - 10} more"

        # Custom dialog with checkbox confirmation
        dialog = QDialog(self)
        dialog.setWindowTitle("Confirm Permanent Deletion")
        layout = QVBoxLayout(dialog)

        # Warning message
        warning_label = QLabel(msg)
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)

        # Confirmation checkbox
        confirm_checkbox = QCheckBox("I understand this is permanent and cannot be undone")
        layout.addWidget(confirm_checkbox)

        # Buttons
        button_box = QDialogButtonBox()
        delete_btn = button_box.addButton(
            "Delete Permanently", QDialogButtonBox.ButtonRole.DestructiveRole
        )
        if delete_btn:
            delete_btn.setEnabled(False)  # Disabled until checkbox checked
            delete_btn.setStyleSheet("QPushButton { background-color: #DC2626; color: white; }")
        button_box.addButton(QDialogButtonBox.StandardButton.Cancel)

        def on_confirm_changed(state: Qt.CheckState) -> None:
            if delete_btn:
                delete_btn.setEnabled(state == Qt.CheckState.Checked)

        confirm_checkbox.stateChanged.connect(on_confirm_changed)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Perform deletion
        image_repo = ImageFilesRepository(self.analysis_db.connection)
        deleted_count = 0
        error_count = 0

        for file_path in selected:
            try:
                # Delete physical file
                if os.path.exists(file_path):
                    os.remove(file_path)

                # Mark as deleted in database
                image_repo.mark_deleted(file_path)
                deleted_count += 1
            except (FileNotFoundError, PermissionError) as e:
                self._get_logger().error(f"Failed to delete {file_path}: {e}")
                error_count += 1

        # Show results
        if error_count > 0:
            QMessageBox.warning(
                self,
                "Deletion Incomplete",
                f"Deleted {deleted_count} file(s), but {error_count} failed.\nCheck logs for details.",
            )
        else:
            QMessageBox.information(self, "Success", f"Permanently deleted {deleted_count} file(s)")

        # Emit signals
        self.files_deleted.emit(selected)
        self.files_changed.emit()

        # Refresh
        self._refresh_images()

    def _on_ignore_clicked(self) -> None:
        """Handle ignore analysis button click."""
        selected = self._get_selected_images()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select images to ignore.")
            return

        # Confirmation
        msg = f"Ignore {len(selected)} image(s) from future analysis?\n\n"
        msg += "Ignored images:\n"
        msg += "• Will remain registered in the database\n"
        msg += "• Will be skipped during analysis scans\n"
        msg += "• Can be un-ignored later\n"

        reply = QMessageBox.question(
            self,
            "Confirm Ignore",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            image_repo = ImageFilesRepository(self.analysis_db.connection)

            for file_path in selected:
                image_repo.set_ignored(file_path, ignored=True)

            # Show confirmation
            QMessageBox.information(self, "Success", f"Ignored {len(selected)} image(s)")

            # Emit signals
            self.files_ignored.emit(selected)
            self.files_changed.emit()

            # Reload tree (ignored images will be filtered out)
            self._refresh_images()

    def _on_discover_clicked(self) -> None:
        """Start the discovery process."""
        # Check if discovery is already running
        if self.discovery_worker and self.discovery_worker.isRunning():
            QMessageBox.warning(self, "Discovery In Progress", "Discovery is already running.")
            return

        # Get directories from config
        directories = self.config_manager.get_directories()
        if not directories:
            QMessageBox.warning(
                self,
                "No Directories",
                "No source directories configured.\n\nPlease add directories in Settings.",
            )
            return

        # Disable buttons during discovery
        if self.discover_button:
            self.discover_button.setEnabled(False)
        if self.refresh_button:
            self.refresh_button.setEnabled(False)

        # Show progress bar
        if self.progress_bar:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Starting discovery...")

        # Create and configure worker
        self.discovery_worker = DiscoveryWorker(self.config_manager, directories)
        self.discovery_worker.progress.connect(self._on_discovery_progress)
        self.discovery_worker.finished.connect(self._on_discovery_finished)
        self.discovery_worker.error.connect(self._on_discovery_error)

        # Start discovery
        self.discovery_worker.start()
        self._get_logger().info("[DISCOVER WINDOW] Discovery started")

    def _on_discovery_progress(self, status_text: str, current: int, total: int) -> None:
        """
        Handle discovery progress updates.

        Args:
            status_text: Current status message
            current: Current file index
            total: Total files to process
        """
        if self.progress_bar:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.setFormat(f"{current}/{total} - {status_text}")

        # Refresh tree periodically (every 10 files) to show new discoveries
        if current % 10 == 0:
            self._refresh_images()

    def _on_discovery_finished(self, new_file_count: int) -> None:
        """
        Handle discovery completion.

        Args:
            new_file_count: Number of newly discovered files
        """
        # Hide progress bar
        if self.progress_bar:
            self.progress_bar.setVisible(False)

        # Re-enable buttons
        if self.discover_button:
            self.discover_button.setEnabled(True)
        if self.refresh_button:
            self.refresh_button.setEnabled(True)

        # Refresh directory dropdown (in case new directories were discovered)
        self._populate_directory_dropdown()

        # Refresh tree to show all discovered images
        self._refresh_images()

        # Show completion message
        if new_file_count > 0:
            QMessageBox.information(
                self,
                "Discovery Complete",
                f"Discovery completed successfully!\n\n{new_file_count} new image(s) discovered and registered.",
            )
        else:
            QMessageBox.information(
                self, "Discovery Complete", "Discovery completed.\n\nNo new images found."
            )

        self._get_logger().info(
            f"[DISCOVER WINDOW] Discovery completed - {new_file_count} new files"
        )

    def _on_discovery_error(self, error_message: str) -> None:
        """
        Handle discovery errors.

        Args:
            error_message: Error message from worker
        """
        # Hide progress bar
        if self.progress_bar:
            self.progress_bar.setVisible(False)

        # Re-enable buttons
        if self.discover_button:
            self.discover_button.setEnabled(True)
        if self.refresh_button:
            self.refresh_button.setEnabled(True)

        # Show error dialog
        QMessageBox.critical(
            self, "Discovery Error", f"An error occurred during discovery:\n\n{error_message}"
        )

        self._get_logger().error(f"[DISCOVER WINDOW] Discovery error: {error_message}")

    def closeEvent(self, event):  # noqa: N802
        """Handle window close event - stop discovery worker if running."""
        if self.discovery_worker and self.discovery_worker.isRunning():
            # Ask user for confirmation
            reply = QMessageBox.question(
                self,
                "Discovery In Progress",
                "Discovery is still running. Do you want to cancel it and close the window?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Stop the worker
                self.discovery_worker.stop()
                self.discovery_worker.wait(3000)  # Wait up to 3 seconds
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
