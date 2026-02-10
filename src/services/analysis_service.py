"""
Analysis Service
Orchestrates automatic page analysis on startup with caching support.
"""

import glob
import os
import time
from collections.abc import Callable
from typing import Any

from config.config_manager import ConfigManager
from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB
from llm_providers.provider_factory import ProviderFactory
from services.logging_service import get_logger
from services.metadata_normalizer import MetadataNormalizer


class AnalysisService:
    """Manages automatic startup analysis of document pages"""

    DEFAULT_ANALYSIS_PROMPT = (
        "Analyze this document page and extract the following information in JSON format:\n\n"
        "Required fields:\n"
        "- document_type: Type of document (invoice, receipt, contract, letter, etc.)\n"
        "- company: Company name that issued this document\n"
        "- document_date: Date on the document (YYYY-MM-DD format if possible)\n"
        "- tax_related: Is this document related to taxes? (true/false) Examples include: W-2, 1099, "
        "tax returns, property tax bills, tax receipts, IRS correspondence, deductible expense receipts\n"
        "- page_number: Current page number (if visible)\n"
        "- total_pages: Total number of pages (if visible)\n"
        "- rotation_needed: Analyze if the document needs rotation for proper reading. "
        "The text should be legible and readable without tilting your head. "
        "Return 'none' if already correctly oriented, '90_cw' for 90 degrees clockwise, "
        "'90_ccw' for 90 degrees counter-clockwise, or '180' for upside down.\n"
        "- confidence_score: Your confidence in the extraction (0.0 to 1.0)\n\n"
        "IMPORTANT: For rotation_needed, check if text can be read normally (left-to-right, top-to-bottom) "
        "without rotating the page. If you need to tilt your head to read it, specify the rotation needed.\n\n"
        "Return ONLY valid JSON with these exact field names."
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

    def _register_image_file(self, image_path: str) -> None:
        """
        Register an image file in the database (idempotent).

        If the file is already registered, updates last_seen_at.
        Otherwise, registers it with status 'registered'.

        Args:
            image_path: Path to the image file
        """
        try:
            # Check if already registered
            existing = self.analysis_db.get_image_file(image_path)

            if existing:
                # Update last_seen_at timestamp
                self.analysis_db.update_image_last_seen(image_path)
                self._log(f"[REGISTER] Updated last_seen for: {os.path.basename(image_path)}")
            else:
                # Register new file
                file_hash = self.metadata_db.compute_file_hash(image_path)
                file_stats = os.stat(image_path)
                file_size = file_stats.st_size
                file_mtime = file_stats.st_mtime
                directory_path = os.path.dirname(image_path)
                filename = os.path.basename(image_path)

                self.analysis_db.register_image_file(
                    image_path, file_hash, directory_path, filename, file_size, file_mtime
                )
                self._log(f"[REGISTER] Registered new image: {filename}")

        except Exception as e:
            self._log(f"[REGISTER ERROR] Failed to register {os.path.basename(image_path)}: {e}")
            # Don't fail the scan if registration fails - continue with analysis

    def analyze_single_file(self, file_path: str, force_reanalysis: bool = False) -> dict[str, Any]:
        """
        Analyze a single file (public interface for on-demand re-analysis).

        Args:
            file_path: Path to image file
            force_reanalysis: If True, bypass cache and force fresh analysis

        Returns:
            Dictionary with analysis result
        """
        # Register the file first (if not already registered)
        self._register_image_file(file_path)

        # Analyze the file (incremental=False means bypass cache)
        return self._analyze_single_page(file_path, incremental=not force_reanalysis)

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

        stats = {
            "total_files": 0,
            "analyzed": 0,
            "cached": 0,
            "errors": 0,
            "skipped": 0,
            "processing_time_ms": 0,
        }

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
            image_files = sorted(image_files_set)
            all_files.extend([(directory, f) for f in image_files])

        stats["total_files"] = len(all_files)
        self._log(f"[SCAN] Starting analysis of {stats['total_files']} files")

        try:
            # Process all files
            for idx, (_, image_path) in enumerate(all_files):
                current = idx + 1

                # Check for cancellation BEFORE starting each file
                # This allows immediate cancellation without waiting for current file to finish
                if abort_check and abort_check():
                    self._log("[SCAN] Abort detected before starting file, stopping immediately")
                    raise InterruptedError("Analysis aborted by user")

                if progress_callback:
                    progress_callback(
                        f"Analyzing {os.path.basename(image_path)}...",
                        current,
                        stats["total_files"],
                    )

                # Register image file (idempotent operation)
                self._register_image_file(image_path)

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
                    # Error is logged; had_error flag in analysis_results tracks failures

            # Update directory scan info for each directory
            for directory in directories:
                if os.path.exists(directory):
                    # Count files in this directory
                    image_files_set = set()
                    for ext in ["*.png", "*.PNG", "*.jpg", "*.JPG", "*.jpeg", "*.JPEG"]:
                        image_files_set.update(glob.glob(os.path.join(directory, ext)))
                    self.analysis_db.update_directory_scan_info(directory, len(image_files_set))

            stats["processing_time_ms"] = int((time.time() - start_time) * 1000)

        except InterruptedError:
            # Analysis was cancelled - update with partial results
            stats["processing_time_ms"] = int((time.time() - start_time) * 1000)
            self._log("[SCAN] Analysis cancelled by user")
            raise  # Re-raise to let caller handle it

        finally:
            # Check if analysis was aborted (don't save results)
            if abort_check and abort_check():
                self._log("[SCAN] Analysis aborted - no results saved")
            else:
                self._log(f"[SCAN] Analysis finalized - Stats: {stats}")

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
            if existing_analysis:
                # Get image file record to check hash (file_hash is in image_files table now)
                image_file = self.analysis_db.get_image_file(image_path)
                if image_file and image_file["file_hash"] == file_hash:
                    # Update status to 'analyzed' if it exists
                    analysis_id = existing_analysis.get("id")
                    if analysis_id:
                        self.analysis_db.update_image_status(image_path, "analyzed", analysis_id)
                    return {
                        "success": True,
                        "cached": True,
                        "skipped": False,
                        "analysis": existing_analysis,
                    }

        # File needs analysis - status is already set to "analyzing" by worker thread
        # (No need to update status here - would be duplicate)

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

                # Save error as analysis record so it appears in UI
                error_response = f"ERROR: Analysis failed\n\n{error_msg}"
                analysis_id = self.analysis_db.save_analysis(
                    file_path=image_path,
                    file_hash=file_hash,
                    provider_name=provider.provider_name,
                    model_name=result.get("model_used", "unknown"),
                    analysis_data={},  # Empty metadata
                    raw_response=error_response,  # Error message in raw response
                    processing_time_ms=result.get("processing_time_ms", 0),
                    prompt_text=metadata_prompt,
                    had_error=True,  # Mark as error
                )

                # Update status to indicate error
                self.analysis_db.update_image_status(
                    image_path, "analyzed"
                )  # Status 'analyzed' but with error

                return {"success": False, "cached": False, "skipped": False, "error": error_msg}

            # Save analysis to database
            self._log("[ANALYSIS] Saving to database...")
            analysis_id = self.analysis_db.save_analysis(
                file_path=image_path,
                file_hash=file_hash,
                provider_name=provider.provider_name,
                model_name=result["model_used"],
                analysis_data=result["metadata"],
                raw_response=result["response"],
                processing_time_ms=result["processing_time_ms"],
                prompt_text=metadata_prompt,
                had_error=False,  # Successful analysis
            )

            self._log(f"[ANALYSIS] Saved analysis with ID: {analysis_id}")

            # Normalize and save to metadata table
            try:
                normalizer = MetadataNormalizer()
                normalized = normalizer.normalize(result["metadata"])

                image_file = self.analysis_db.get_image_file(image_path)
                if image_file and analysis_id:
                    self.analysis_db.create_metadata_from_analysis(
                        image_file_id=image_file["id"],
                        analysis_id=analysis_id,
                        normalized_metadata=normalized,
                    )
                    self._log("[ANALYSIS] Created normalized metadata record")
            except Exception as normalize_error:
                self._log(
                    f"[ANALYSIS WARNING] Failed to create normalized metadata: {normalize_error}"
                )
                # Don't fail the analysis if normalization fails

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

            # Save exception as analysis record so it appears in UI
            error_response = (
                f"ERROR: Exception during analysis\n\n{str(e)}\n\nTraceback:\n{error_details}"
            )
            try:
                provider = self._get_provider()
                self.analysis_db.save_analysis(
                    file_path=image_path,
                    file_hash=file_hash,
                    provider_name=provider.provider_name,
                    model_name="unknown",
                    analysis_data={},  # Empty metadata
                    raw_response=error_response,  # Error message with traceback
                    processing_time_ms=0,
                    prompt_text=metadata_prompt if "metadata_prompt" in locals() else None,
                    had_error=True,  # Mark as error
                )

                # Update status to indicate error
                self.analysis_db.update_image_status(image_path, "analyzed")
            except Exception:
                # If saving error also fails, just log and continue
                pass

            return {"success": False, "cached": False, "skipped": False, "error": str(e)}

    def _log(self, message: str):
        """Write log message using the logging service"""
        try:
            self.logger.info(message)
        except Exception:
            # If logging fails, use a fallback logger
            import logging

            logging.getLogger(__name__).info(message)

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
            progress_callback: Optional progress callback (should raise InterruptedError if cancelled)

        Returns:
            Dictionary with analysis statistics
        """
        stats = {"total_files": len(file_paths), "analyzed": 0, "cached": 0, "errors": 0}

        try:
            for i, file_path in enumerate(file_paths):
                if progress_callback:
                    # Progress callback will raise InterruptedError if cancelled
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

        except InterruptedError:
            # Analysis was cancelled - return partial results
            self._log("[ANALYZE_SPECIFIC] Analysis cancelled by user")
            raise  # Re-raise to let caller handle it

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

    def re_analyze_file(
        self, file_path: str, progress_callback: Callable[[str], None] | None = None
    ) -> dict[str, Any]:
        """
        Re-analyze a file, resetting its status before analysis.

        This is the centralized method for re-analysis that both UI components should use.
        It ensures consistent behavior by:
        1. Resetting the file's status to "Pending"
        2. Clearing any error messages
        3. Forcing a fresh analysis (bypassing cache)
        4. Emitting progress updates (if callback provided)

        Args:
            file_path: Path to the file to re-analyze
            progress_callback: Optional callback(status_text) for progress updates

        Returns:
            Dictionary with analysis result (same format as _analyze_single_page)
        """
        filename = os.path.basename(file_path)

        try:
            # Emit progress: Resetting status
            if progress_callback:
                progress_callback(f"Resetting status for {filename}...")

            # Reset status to pending before re-analysis
            self.analysis_db.update_analysis_metadata(file_path, {"status": "Pending"})
            self._log(f"[RE-ANALYSIS] Reset status to Pending for: {filename}")
        except Exception as e:
            self._log(f"[RE-ANALYSIS WARNING] Could not reset status: {e}")
            # Continue anyway - status reset is not critical

        # Emit progress: Starting analysis
        if progress_callback:
            progress_callback(f"Analyzing {filename} with LLM...")

        # Perform fresh analysis (incremental=False forces re-analysis)
        self._log(f"[RE-ANALYSIS] Starting fresh analysis for: {filename}")
        result = self._analyze_single_page(file_path, incremental=False)

        # Emit progress: Completed
        if progress_callback:
            if result.get("success"):
                progress_callback(f"Analysis complete for {filename}")
            else:
                progress_callback(f"Analysis failed for {filename}")

        return result


# Example usage
if __name__ == "__main__":
    import logging

    from config.config_manager import ConfigManager
    from services.logging_service import LoggingService

    LoggingService().initialize(log_level=logging.DEBUG, console_output=True)
    _logger = get_logger()

    # Create instances
    config = ConfigManager()
    analysis_db_instance = AnalysisDB()
    metadata_db_instance = MetadataDB()

    # Create service
    service = AnalysisService(config, analysis_db_instance, metadata_db_instance)

    # Test scan (won't actually analyze without valid images)
    def progress(status, current, total):
        _logger.info(f"[{current}/{total}] {status}")

    _logger.info("Testing analysis service...")
    stats = service.scan_all_directories(progress_callback=progress)
    _logger.info(f"Analysis complete: {stats}")

    # Cleanup
    analysis_db_instance.close()
    metadata_db_instance.close()
