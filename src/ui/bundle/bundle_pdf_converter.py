"""Pure-service PDF conversion utilities for the bundle workflow.

This module owns:
- Output directory resolution  (``BundlePdfConverter.determine_output_directory``)
- Actual PDF creation via BundlingService (``BundlePdfConverter.convert``)
- Opening the produced PDF  (``BundlePdfConverter.open_pdf``)
- Human-readable file-size formatting (``BundlePdfConverter.format_file_size``)

No Qt imports — unit-testable without a QApplication.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from config.config_manager import ConfigManager
    from db.analysis_db import AnalysisDB


class BundlePdfConverter:
    """Handles output-directory logic and PDF conversion for bundle review."""

    def __init__(self, config_manager: ConfigManager, analysis_db: AnalysisDB) -> None:
        self.config_manager = config_manager
        self.analysis_db = analysis_db

    # ------------------------------------------------------------------
    # Output directory resolution
    # ------------------------------------------------------------------

    def determine_output_directory(self, bundle: dict) -> str:
        """Return the output directory path based on the configured strategy.

        Args:
            bundle: Bundle dict that must contain ``file_paths``.

        Returns:
            Absolute path to the output directory.
        """
        strategy = self.config_manager.get_setting(
            "OutputDirectory", "strategy", default="same_as_source"
        )

        if strategy == "global_custom":
            custom_path = self.config_manager.get_setting(
                "OutputDirectory", "global_custom_path", default=""
            )
            if custom_path and os.path.isdir(custom_path):
                return cast(str, custom_path)
            # Fall through to default if path not set or invalid.

        elif strategy == "same_as_source":
            if bundle.get("file_paths"):
                first_file = bundle["file_paths"][0]
                source_dir = os.path.dirname(first_file)
                subdirectory = cast(
                    str,
                    self.config_manager.get_setting(
                        "OutputDirectory", "subdirectory_name", default="ORGANIZED"
                    ),
                )
                return os.path.join(source_dir, subdirectory)
            from services.logging_service import get_logger

            get_logger().warning(
                "OutputDirectory strategy='same_as_source' but bundle has no file_paths; "
                "falling back to default output directory."
            )

        elif strategy == "beside_source":
            if bundle.get("file_paths"):
                first_file = bundle["file_paths"][0]
                return cast(str, os.path.dirname(first_file))
            from services.logging_service import get_logger

            get_logger().warning(
                "OutputDirectory strategy='beside_source' but bundle has no file_paths; "
                "falling back to default output directory."
            )

        # Default fallback
        return os.path.join(os.path.expanduser("~"), "Documents", "WinScanLLM", "PDFs")

    # ------------------------------------------------------------------
    # PDF conversion
    # ------------------------------------------------------------------

    def convert(
        self,
        bundle: dict,
        metadata: dict,
        ordered_paths: list[str],
        rotation_angle: int,
    ) -> str:
        """Convert *ordered_paths* to a PDF and persist the result.

        Args:
            bundle:        Bundle dict (used for output-dir resolution and DB
                           update).
            metadata:      Must contain ``output_filename`` (with ``.PDF``
                           extension already enforced by the caller).
            ordered_paths: Image paths in the desired final order.
            rotation_angle: Degrees to rotate pages (0, 90, 180, 270).

        Returns:
            Absolute path to the newly created PDF file.
        """
        from services.bundling_service import BundlingService

        bundling_service = BundlingService(self.analysis_db)

        output_dir = self.determine_output_directory(bundle)
        output_path = Path(output_dir) / metadata["output_filename"]
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pdf_path = bundling_service.convert_bundle_to_pdf(
            file_paths=ordered_paths,
            output_path=str(output_path),
            metadata=metadata,
            rotation_angle=rotation_angle,
        )

        bundle_id = bundle.get("id")
        if bundle_id:
            bundling_service.update_bundle_metadata(bundle_id, metadata)
            bundling_service.mark_bundle_completed(bundle_id, pdf_path)

        return pdf_path

    # ------------------------------------------------------------------
    # Open PDF
    # ------------------------------------------------------------------

    def open_pdf(self, pdf_path: str) -> None:
        """Open *pdf_path* with the platform default PDF viewer."""
        if platform.system() == "Windows":
            os.startfile(pdf_path)  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.call(["open", pdf_path])
        else:
            subprocess.call(["xdg-open", pdf_path])

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def format_file_size(size_bytes: int | float) -> str:
        """Return *size_bytes* formatted as a human-readable string."""
        size: float = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
