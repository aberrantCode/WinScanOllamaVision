"""
Analysis Service
Orchestrates automatic page analysis on startup with caching support.
"""

import glob
import os
import time
import uuid
from collections.abc import Callable
from typing import Any

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from llm_providers.provider_factory import ProviderFactory
from services.logging_service import get_logger


class AnalysisService:
    """Manages automatic startup analysis of document pages"""

    DEFAULT_ANALYSIS_PROMPT = (
        "Please analyze the page and extract the following fields: document_type, company, "
        "document_date, page_number, total_pages, rotation, and confidence_score. "
        "Return the results in a concise JSON-friendly format or key/value pairs."
    )

    def __init__(
        self, config_manager: ConfigManager, analysis_db: AnalysisDB, metadata_db: MetadataDB
    ):
        """
        Initialize analysis service.

        Args:
            config_manager: Configuration manager instance
            analysis_db: Analysis database instance
            metadata_db: Metadata database instance
        """
        self.config = config_manager
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.provider = None
        self.logger = get_logger()

    def _get_provider(self):
        """Get or create provider instance"""
        if self.provider is None:
            self.provider = ProviderFactory.create_from_config_manager(self.config)
        return self.provider

    def scan_all_directories(
        self,
        progress_callback: Callable[[str, int, int], None] | None = None,
        incremental: bool = True,
        abort_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """
        Scan all configured source directories and analyze pages.

        Args:
            progress_callback: Optional callback(status_text, current, total)
            incremental: If True, skip already-analyzed files (cache-aware)
            abort_check: Optional callback that returns True if analysis should be aborted without saving

        Returns:
            Dictionary with analysis statistics
        """
        self._log("[SCAN] Starting scan_all_directories...")

        # Check if auto-analysis is enabled
        if not self.config.get_bool("AutoAnalysis", "enabled", True):
            self._log("[SCAN] Auto-analysis is disabled in settings")
            return {
                "total_files": 0,
                "analyzed": 0,
                "cached": 0,
                "errors": 0,
                "skipped": 0,
                "message": "Auto-analysis disabled in settings",
            }

        directories = self.analysis_db.get_active_directories()
        if not directories:
            # Fall back to scan folder from DocumentProcessing
            scan_folder = self.config.get_setting("DocumentProcessing", "scan_folder")
            self._log(f"[SCAN] No active directories, using scan_folder: {scan_folder}")
            if scan_folder and os.path.exists(scan_folder):
                directories = [scan_folder]
            else:
                self._log("[SCAN] No directories found to scan")
                return {
                    "total_files": 0,
                    "analyzed": 0,
                    "cached": 0,
                    "errors": 0,
                    "skipped": 0,
                    "message": "No source directories configured",
                }
        else:
            self._log(f"[SCAN] Active directories: {directories}")

        # Get batch size from config
        batch_size = self.config.get_int("AutoAnalysis", "batch_size", 10)

        stats = {
            "total_files": 0,
            "analyzed": 0,
            "cached": 0,
            "errors": 0,
            "skipped": 0,
            "processing_time_ms": 0,
        }

        # Generate unique run ID
        run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        start_time = time.time()

        # Collect all files first to get total count
        all_files = []
        for directory in directories:
            if not os.path.exists(directory):
                continue

            # Find all image files (PNG, JPG, JPEG) - use set to avoid duplicates
            image_files_set = set()
            for ext in ["*.png", "*.PNG", "*.jpg", "*.JPG", "*.jpeg", "*.JPEG"]:
                image_files_set.update(glob.glob(os.path.join(directory, ext)))
            image_files = sorted(list(image_files_set))
            all_files.extend([(directory, f) for f in image_files])

        stats["total_files"] = len(all_files)

        # Start tracking this run
        self._log(f"[SCAN] Starting run {run_id} with {stats['total_files']} files")
        self.analysis_db.start_analysis_run(run_id, stats["total_files"])

        try:
            # Process all files
            for idx, (directory, image_path) in enumerate(all_files):
                current = idx + 1

                if progress_callback:
                    progress_callback(
                        f"Analyzing {os.path.basename(image_path)}...",
                        current,
                        stats["total_files"],
                    )

                # Analyze single page
                result = self._analyze_single_page(image_path, incremental)

                if result["cached"]:
                    stats["cached"] += 1
                elif result["success"]:
                    stats["analyzed"] += 1
                elif result["skipped"]:
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1
                    error_msg = result.get("error", "Unknown error")
                    self._log(
                        f"[SCAN] File failed: {os.path.basename(image_path)} - Error: {error_msg}"
                    )

                    # Save error to database
                    self.analysis_db.save_analysis_error(
                        run_id=run_id,
                        file_path=image_path,
                        error_message=error_msg,
                        error_type="analysis_failed",
                    )

            # Update directory scan info for each directory
            for directory in directories:
                if os.path.exists(directory):
                    # Count files in this directory
                    image_files_set = set()
                    for ext in ["*.png", "*.PNG", "*.jpg", "*.JPG", "*.jpeg", "*.JPEG"]:
                        image_files_set.update(glob.glob(os.path.join(directory, ext)))
                    self.analysis_db.update_directory_scan_info(directory, len(image_files_set))

            stats["processing_time_ms"] = int((time.time() - start_time) * 1000)

            # Finalize the run
            run_status = (
                "completed"
                if stats["errors"] == 0
                else "failed"
                if stats["errors"] == stats["total_files"]
                else "completed"
            )

        except InterruptedError:
            # Analysis was cancelled - update with partial results
            stats["processing_time_ms"] = int((time.time() - start_time) * 1000)
            run_status = "cancelled"
            self._log(f"[SCAN] Run {run_id} cancelled by user")
            raise  # Re-raise to let caller handle it

        finally:
            # Check if analysis was aborted (don't save results)
            if abort_check and abort_check():
                # Abort mode - mark as aborted with zero stats
                self.analysis_db.update_analysis_run(
                    run_id=run_id, analyzed=0, cached=0, errors=0, skipped=0, status="aborted"
                )
                self._log(f"[SCAN] Run {run_id} aborted - no results saved")
            else:
                # Normal completion or stop (save partial results)
                self.analysis_db.update_analysis_run(
                    run_id=run_id,
                    analyzed=stats["analyzed"],
                    cached=stats["cached"],
                    errors=stats["errors"],
                    skipped=stats["skipped"],
                    status=run_status,
                )
                self._log(f"[SCAN] Run {run_id} finalized - Stats: {stats}")

        return stats

    def _analyze_single_page(self, image_path: str, incremental: bool = True) -> dict[str, Any]:
        """
        Analyze a single page with cache-aware processing.

        Args:
            image_path: Path to image file
            incremental: If True, use cached results if available

        Returns:
            Dictionary with result info
        """
        # Compute file hash
        file_hash = self.metadata_db.compute_file_hash(image_path)

        # Check if already analyzed (cache hit)
        if incremental:
            existing_analysis = self.analysis_db.get_analysis(image_path)
            if existing_analysis and existing_analysis["file_hash"] == file_hash:
                return {
                    "success": True,
                    "cached": True,
                    "skipped": False,
                    "analysis": existing_analysis,
                }

        # File needs analysis
        try:
            self._log(f"[ANALYSIS] Starting analysis for: {os.path.basename(image_path)}")
            provider = self._get_provider()
            self._log(f"[ANALYSIS] Provider obtained: {provider.provider_name}")

            # Get metadata extraction prompt from settings
            metadata_prompt = self.config.get_setting("Prompts", "document_metadata")
            if not metadata_prompt:
                # Fallback to a basic prompt if not configured
                metadata_prompt = "Analyze this document and extract metadata."

            # Perform analysis
            self._log("[ANALYSIS] Calling provider.analyze_images()...")
            result = provider.analyze_images(image_paths=[image_path], prompt=metadata_prompt)
            self._log(f"[ANALYSIS] Provider returned: success={result.get('success')}")

            if not result["success"]:
                error_msg = result.get("error", "Unknown error")
                self._log(f"[ANALYSIS ERROR] Provider returned failure: {error_msg}")
                return {"success": False, "cached": False, "skipped": False, "error": error_msg}

            # Save analysis to database
            self._log("[ANALYSIS] Saving to database...")
            self.analysis_db.save_analysis(
                file_path=image_path,
                file_hash=file_hash,
                provider_name=provider.provider_name,
                model_name=result["model_used"],
                analysis_data=result["metadata"],
                raw_response=result["response"],
                processing_time_ms=result["processing_time_ms"],
            )

            # Also save to metadata_db for backward compatibility
            self.metadata_db.save_metadata(
                file_path=image_path,
                metadata=result["metadata"],
                model_used=result["model_used"],
                processing_time_ms=result["processing_time_ms"],
            )

            self._log("[ANALYSIS] Successfully saved to database")
            return {
                "success": True,
                "cached": False,
                "skipped": False,
                "analysis": result["metadata"],
            }

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            self._log(
                f"[ANALYSIS EXCEPTION] Error analyzing {os.path.basename(image_path)}: {str(e)}"
            )
            self._log(f"[ANALYSIS EXCEPTION] Traceback:\n{error_details}")
            return {"success": False, "cached": False, "skipped": False, "error": str(e)}

    def _log(self, message: str):
        """Write log message using the logging service"""
        try:
            self.logger.info(message)
        except Exception:
            # If logging fails, just print to console
            print(message)

    def analyze_specific_files(
        self,
        file_paths: list[str],
        force_reanalysis: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze specific files (for manual triggering).

        Args:
            file_paths: List of file paths to analyze
            force_reanalysis: If True, re-analyze even if cached
            progress_callback: Optional progress callback

        Returns:
            Dictionary with analysis statistics
        """
        stats = {"total_files": len(file_paths), "analyzed": 0, "cached": 0, "errors": 0}

        for i, file_path in enumerate(file_paths):
            if progress_callback:
                progress_callback(
                    f"Analyzing {os.path.basename(file_path)}...", i + 1, stats["total_files"]
                )

            result = self._analyze_single_page(file_path, incremental=not force_reanalysis)

            if result["cached"]:
                stats["cached"] += 1
            elif result["success"]:
                stats["analyzed"] += 1
            else:
                stats["errors"] += 1

        return stats

    def get_analysis_for_files(self, file_paths: list[str]) -> list[dict[str, Any]]:
        """
        Get analysis results for specific files.

        Args:
            file_paths: List of file paths

        Returns:
            List of analysis dictionaries
        """
        results = []
        for file_path in file_paths:
            analysis = self.analysis_db.get_analysis(file_path)
            if analysis:
                results.append(analysis)
        return results


# Example usage
if __name__ == "__main__":
    from analysis_db import AnalysisDB
    from metadata_db import MetadataDB

    from config.config_manager import ConfigManager

    # Create instances
    config = ConfigManager()
    analysis_db = AnalysisDB()
    metadata_db = MetadataDB()

    # Create service
    service = AnalysisService(config, analysis_db, metadata_db)

    # Test scan (won't actually analyze without valid images)
    def progress(status, current, total):
        print(f"[{current}/{total}] {status}")

    print("Testing analysis service...")
    stats = service.scan_all_directories(progress_callback=progress)
    print(f"Analysis complete: {stats}")

    # Cleanup
    analysis_db.close()
    metadata_db.close()
