"""Queue-based analysis job management.

This module provides a thread-safe queue system for managing document analysis
requests, supporting priority-based execution and graceful cancellation.
"""

import queue
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock


class JobType(Enum):
    """Types of analysis jobs."""

    SCAN_ALL = "scan_all"  # Full directory scan
    ANALYZE_FILES = "analyze_files"  # Specific file list


class JobPriority(Enum):
    """Job priority levels (lower number = higher priority)."""

    HIGH = 1  # On-demand user requests (re-analyze)
    NORMAL = 2  # Auto-scan, batch operations


@dataclass(order=True)
class AnalysisJob:
    """Analysis job with priority-based ordering."""

    priority: int = field(compare=True)
    created_at: float = field(compare=True)
    job_id: str = field(compare=False, default_factory=lambda: str(uuid.uuid4()))
    job_type: JobType = field(compare=False, default=JobType.SCAN_ALL)
    file_paths: list[str] = field(compare=False, default_factory=list)
    force_reanalysis: bool = field(compare=False, default=False)

    @classmethod
    def create(
        cls,
        job_type: JobType,
        priority: JobPriority,
        file_paths: list[str] | None = None,
        force_reanalysis: bool = False,
    ) -> "AnalysisJob":
        """Create a new analysis job with automatic timestamp."""
        return cls(
            job_id=str(uuid.uuid4()),
            job_type=job_type,
            priority=priority.value,
            file_paths=file_paths or [],
            force_reanalysis=force_reanalysis,
            created_at=time.time(),
        )


class AnalysisQueue:
    """Thread-safe queue for analysis jobs with priority support."""

    def __init__(self) -> None:
        """Initialize empty queue."""
        self._queue: queue.PriorityQueue[AnalysisJob] = queue.PriorityQueue()
        self._lock = Lock()
        self._current_job: AnalysisJob | None = None
        self._completed_jobs: dict[str, float] = {}  # job_id -> completion_time
        self._cancelled_jobs: set[str] = set()

    def enqueue(self, job: AnalysisJob) -> str:
        """Add job to queue.

        Args:
            job: Analysis job to enqueue

        Returns:
            Job ID for tracking
        """
        self._queue.put(job)
        return job.job_id

    def dequeue(self, timeout: float | None = None) -> AnalysisJob | None:
        """Get next job from queue (blocking).

        Args:
            timeout: Maximum seconds to wait, None for infinite

        Returns:
            Next job or None if timeout
        """
        try:
            job = self._queue.get(block=True, timeout=timeout)
            with self._lock:
                self._current_job = job
            return job
        except queue.Empty:
            return None

    def mark_complete(self, job_id: str) -> None:
        """Mark job as completed.

        Args:
            job_id: ID of completed job
        """
        with self._lock:
            self._completed_jobs[job_id] = time.time()
            if self._current_job and self._current_job.job_id == job_id:
                self._current_job = None

    def mark_cancelled(self, job_id: str) -> None:
        """Mark job as cancelled.

        Args:
            job_id: ID of cancelled job
        """
        with self._lock:
            self._cancelled_jobs.add(job_id)
            if self._current_job and self._current_job.job_id == job_id:
                self._current_job = None

    def get_pending_count(self) -> int:
        """Get number of pending jobs in queue.

        Returns:
            Number of jobs waiting to be processed
        """
        return self._queue.qsize()

    def get_current_job(self) -> AnalysisJob | None:
        """Get currently processing job.

        Returns:
            Current job or None
        """
        with self._lock:
            return self._current_job

    def clear_queue(self) -> int:
        """Clear all pending jobs (not current job).

        Returns:
            Number of jobs removed
        """
        count = 0
        with self._lock:
            # Drain the queue
            while not self._queue.empty():
                try:
                    job = self._queue.get_nowait()
                    self._cancelled_jobs.add(job.job_id)
                    count += 1
                except queue.Empty:
                    break
        return count

    def is_job_cancelled(self, job_id: str) -> bool:
        """Check if job has been cancelled.

        Args:
            job_id: Job ID to check

        Returns:
            True if job was cancelled
        """
        with self._lock:
            return job_id in self._cancelled_jobs

    def get_stats(self) -> dict[str, int]:
        """Get queue statistics.

        Returns:
            Dict with 'pending', 'completed', 'cancelled' counts
        """
        with self._lock:
            return {
                "pending": self._queue.qsize(),
                "completed": len(self._completed_jobs),
                "cancelled": len(self._cancelled_jobs),
                "current": 1 if self._current_job else 0,
            }
