"""
Analysis Worker — persistent QThread that processes jobs from AnalysisQueue.

Extracted from ui/analysis_status_window.py so that pipeline panel code can
import a service-layer class rather than coupling to a UI module.
"""

import logging
import os
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from db.image_status import ImageStatus
from services.analysis_queue import AnalysisJob, AnalysisQueue, JobType
from services.status_reporter import get_reporter

if TYPE_CHECKING:
    pass

logger: logging.Logger | None = None


class AnalysisWorker(QThread):
    """Persistent worker thread that processes analysis jobs from queue."""

    # Signals
    job_started = pyqtSignal(str, str)  # (job_id, description)
    progress = pyqtSignal(str, int, int)  # (status_text, current, total)
    file_status_changed = pyqtSignal(str, str)  # (file_path, new_status) - for per-row updates
    job_finished = pyqtSignal(str, dict)  # (job_id, stats)
    error = pyqtSignal(str, str)  # (job_id, error_message)
    queue_empty = pyqtSignal()  # All jobs processed

    def __init__(self, config_manager, analysis_queue: AnalysisQueue):
        super().__init__()
        self.config_manager = config_manager
        self.analysis_queue = analysis_queue
        self._stop_requested = False
        self._current_job_id = None

    def _get_logger(self) -> logging.Logger:
        """Get logger instance (lazy initialization)."""
        global logger
        if logger is None:
            from services.logging_service import get_logger as _get_logger

            logger = _get_logger()
        return logger

    def run(self):
        """Continuously process jobs from queue until stopped."""
        while not self._stop_requested:
            # Get next job (blocking with timeout to allow checking stop flag)
            job = self.analysis_queue.dequeue(timeout=0.5)

            if job is None:
                # No job available, check if we should continue waiting
                if self._stop_requested:
                    break
                continue

            # Check if job was cancelled before we started
            if self.analysis_queue.is_job_cancelled(job.job_id):
                continue

            self._current_job_id = job.job_id

            try:
                # Process the job
                self._process_job(job)
            except Exception as e:
                import traceback

                error_msg = f"{str(e)}\n{traceback.format_exc()}"
                self._get_logger().error(f"Error processing job {job.job_id}: {error_msg}")
                self.error.emit(job.job_id, error_msg)
                # Surface the worker-level failure as a StatusEvent so it shows
                # up in history with a traceback a user can file an issue from.
                import contextlib

                with contextlib.suppress(Exception):
                    get_reporter().error(
                        "Analyze → Worker",
                        f"Analysis job failed: {type(e).__name__}",
                        exc=e,
                        correlation_id=job.job_id,
                        context={
                            "job_type": getattr(job.job_type, "name", str(job.job_type)),
                            "file_count": len(getattr(job, "file_paths", []) or []),
                        },
                    )
                self.analysis_queue.mark_cancelled(job.job_id)
            finally:
                self._current_job_id = None

            # Check if queue is empty
            if self.analysis_queue.get_pending_count() == 0:
                self.queue_empty.emit()

    def _process_job(self, job: AnalysisJob):
        """Process a single analysis job."""
        # Create thread-local database connections
        from db.analysis_db import AnalysisDB
        from db.metadata_db import MetadataDB
        from services.analysis_service import AnalysisService

        thread_analysis_db = None
        thread_metadata_db = None

        try:
            # Emit job started
            if job.job_type == JobType.SCAN_ALL:
                description = "Scanning all directories"
            else:
                description = f"Re-analyzing {len(job.file_paths)} file(s)"
            self.job_started.emit(job.job_id, description)

            # Create new database instances for this thread
            thread_analysis_db = AnalysisDB()
            thread_metadata_db = MetadataDB()
            thread_analysis_service = AnalysisService(
                self.config_manager, thread_analysis_db, thread_metadata_db
            )

            def progress_callback(status_text, current, total):
                if self.analysis_queue.is_job_cancelled(job.job_id):
                    raise InterruptedError("Job cancelled by user")
                # Diagnostic logging
                self._get_logger().debug(
                    f"[WORKER PROGRESS] About to emit progress signal: '{status_text}' ({current}/{total})"
                )
                self.progress.emit(status_text, current, total)
                self._get_logger().debug("[WORKER PROGRESS] Signal emitted successfully")

            def abort_check():
                return self.analysis_queue.is_job_cancelled(job.job_id)

            # Execute based on job type
            if job.job_type == JobType.SCAN_ALL:
                self._get_logger().debug(
                    f"[WORKER] Starting scan_all_directories for job {job.job_id}"
                )
                stats = thread_analysis_service.scan_all_directories(
                    progress_callback=progress_callback,
                    incremental=not job.force_reanalysis,
                    abort_check=abort_check,
                )
                self._get_logger().debug(f"[WORKER] Completed scan_all_directories: {stats}")
            else:  # JobType.ANALYZE_FILES
                # Process specific files
                stats = {
                    "analyzed": 0,
                    "cached": 0,
                    "errors": 0,
                    "total_files": len(job.file_paths),
                    "error_details": [],  # list[dict]: per-file failure records
                }
                for idx, file_path in enumerate(job.file_paths, 1):
                    if self.analysis_queue.is_job_cancelled(job.job_id):
                        raise InterruptedError("Job cancelled by user")

                    # Set status to "analyzing" when actually starting to process this file
                    thread_analysis_db.update_image_status(file_path, ImageStatus.ANALYZING.value)
                    self.file_status_changed.emit(file_path, ImageStatus.ANALYZING.value)

                    progress_callback(
                        f"Analyzing {os.path.basename(file_path)}", idx, len(job.file_paths)
                    )

                    # Re-analyze the file (using private method _analyze_single_page)
                    result = thread_analysis_service._analyze_single_page(
                        file_path, incremental=not job.force_reanalysis
                    )

                    if result.get("success"):
                        stats["analyzed"] += 1
                        # Set status to "analyzed" after successful processing
                        thread_analysis_db.update_image_status(
                            file_path, ImageStatus.ANALYZED.value
                        )
                        self.file_status_changed.emit(file_path, ImageStatus.ANALYZED.value)
                    else:
                        # Preserve the failure reason so the UI can show actionable detail
                        # and the user can file a scoped GitHub issue. Mirrors the
                        # save_error() call in analysis_service.scan_all_directories.
                        error_msg = result.get("error", "Unknown error")
                        stats["errors"] += 1
                        stats["error_details"].append(
                            {
                                "file_path": file_path,
                                "error_message": error_msg,
                                "error_type": "analysis_failed",
                                "job_type": "ANALYZE_FILES",
                            }
                        )
                        try:
                            thread_analysis_db.save_error(
                                file_path=file_path,
                                error_message=error_msg,
                                error_type="analysis_failed",
                            )
                        except Exception as save_exc:  # pragma: no cover - defensive
                            self._get_logger().warning(
                                f"Failed to persist error for {file_path}: {save_exc}"
                            )
                        # Emit a StatusEvent so the UI history surface can show details.
                        try:
                            get_reporter().error(
                                "Analyze → Re-analyze Files",
                                f"Re-analysis failed: {os.path.basename(file_path)}",
                                detail=error_msg,
                                file_path=file_path,
                                correlation_id=job.job_id,
                                context={
                                    "job_type": "ANALYZE_FILES",
                                    "force_reanalysis": bool(job.force_reanalysis),
                                },
                            )
                        except Exception as emit_exc:  # pragma: no cover - defensive
                            self._get_logger().warning(
                                f"Failed to emit status event for {file_path}: {emit_exc}"
                            )
                        # Set status to "error" to indicate failed processing
                        thread_analysis_db.update_image_status(file_path, ImageStatus.ERROR.value)
                        self.file_status_changed.emit(file_path, ImageStatus.ERROR.value)

                # Per-run summary event — useful when several files failed in
                # a single Re-analyze Selected run; the user sees one headline
                # that opens to the full list via correlation_id.
                if job.job_type == JobType.ANALYZE_FILES and stats["errors"] > 0:
                    import contextlib as _ctx

                    with _ctx.suppress(Exception):
                        get_reporter().warn(
                            "Analyze → Re-analyze Files",
                            f"{stats['errors']} of {stats['total_files']} files failed re-analysis",
                            detail=(
                                "Click the individual error events above for per-file "
                                "details, or filter this history by Correlation ID to "
                                "see them grouped."
                            ),
                            correlation_id=job.job_id,
                            context={
                                "analyzed": stats["analyzed"],
                                "errors": stats["errors"],
                                "total_files": stats["total_files"],
                            },
                        )

            # Mark job complete
            self.analysis_queue.mark_complete(job.job_id)
            self.job_finished.emit(job.job_id, stats)

        except InterruptedError:
            # Job was cancelled
            self.analysis_queue.mark_cancelled(job.job_id)
            self.job_finished.emit(
                job.job_id,
                {
                    "total_files": 0,
                    "analyzed": 0,
                    "cached": 0,
                    "errors": 0,
                    "message": "Job cancelled",
                },
            )
        finally:
            # Clean up thread-local connections
            if thread_analysis_db:
                thread_analysis_db.close()
            if thread_metadata_db:
                thread_metadata_db.close()

    def stop(self):
        """Request worker to stop after current job."""
        self._stop_requested = True

    def cancel_current_job(self):
        """Cancel the currently processing job."""
        if self._current_job_id:
            self.analysis_queue.mark_cancelled(self._current_job_id)
