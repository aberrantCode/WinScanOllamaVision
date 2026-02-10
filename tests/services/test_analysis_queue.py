"""Tests for analysis queue management."""

import time
from threading import Thread

from services.analysis_queue import AnalysisJob, AnalysisQueue, JobPriority, JobType


class TestAnalysisJob:
    """Tests for AnalysisJob creation and ordering."""

    def test_create_job_with_defaults(self):
        """Test creating job with default parameters."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        assert job.job_id is not None
        assert len(job.job_id) > 0
        assert job.job_type == JobType.SCAN_ALL
        assert job.priority == JobPriority.NORMAL.value
        assert job.file_paths == []
        assert job.force_reanalysis is False
        assert job.created_at > 0

    def test_create_job_with_file_paths(self):
        """Test creating job with specific files."""
        files = ["/path/to/file1.png", "/path/to/file2.jpg"]
        job = AnalysisJob.create(
            job_type=JobType.ANALYZE_FILES,
            priority=JobPriority.HIGH,
            file_paths=files,
            force_reanalysis=True,
        )

        assert job.job_type == JobType.ANALYZE_FILES
        assert job.priority == JobPriority.HIGH.value
        assert job.file_paths == files
        assert job.force_reanalysis is True

    def test_job_ordering_by_priority(self):
        """Test jobs are ordered by priority (lower number first)."""
        job_high = AnalysisJob.create(job_type=JobType.ANALYZE_FILES, priority=JobPriority.HIGH)
        job_normal = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        # HIGH priority (1) should be less than NORMAL priority (2)
        assert job_high < job_normal

    def test_job_ordering_by_timestamp_same_priority(self):
        """Test jobs with same priority ordered by creation time (FIFO)."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        time.sleep(0.01)  # Ensure different timestamps
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        # Earlier job should be less than later job
        assert job1 < job2


class TestAnalysisQueue:
    """Tests for AnalysisQueue operations."""

    def test_enqueue_dequeue(self):
        """Test basic enqueue and dequeue operations."""
        queue = AnalysisQueue()
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        job_id = queue.enqueue(job)
        assert job_id == job.job_id

        dequeued = queue.dequeue(timeout=1.0)
        assert dequeued is not None
        assert dequeued.job_id == job.job_id

    def test_dequeue_timeout(self):
        """Test dequeue returns None on timeout."""
        queue = AnalysisQueue()

        dequeued = queue.dequeue(timeout=0.1)
        assert dequeued is None

    def test_priority_ordering(self):
        """Test high priority jobs processed before normal priority."""
        queue = AnalysisQueue()

        # Enqueue in reverse priority order
        job_normal = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_high = AnalysisJob.create(job_type=JobType.ANALYZE_FILES, priority=JobPriority.HIGH)

        queue.enqueue(job_normal)
        queue.enqueue(job_high)

        # HIGH priority should dequeue first
        first = queue.dequeue(timeout=1.0)
        assert first is not None
        assert first.priority == JobPriority.HIGH.value

        second = queue.dequeue(timeout=1.0)
        assert second is not None
        assert second.priority == JobPriority.NORMAL.value

    def test_fifo_within_same_priority(self):
        """Test FIFO ordering within same priority level."""
        queue = AnalysisQueue()

        # Create three jobs with same priority
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        time.sleep(0.01)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        time.sleep(0.01)
        job3 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)
        queue.enqueue(job3)

        # Should dequeue in order: job1, job2, job3
        assert queue.dequeue(timeout=1.0).job_id == job1.job_id
        assert queue.dequeue(timeout=1.0).job_id == job2.job_id
        assert queue.dequeue(timeout=1.0).job_id == job3.job_id

    def test_get_pending_count(self):
        """Test getting count of pending jobs."""
        queue = AnalysisQueue()

        assert queue.get_pending_count() == 0

        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        assert queue.get_pending_count() == 1

        queue.enqueue(job2)
        assert queue.get_pending_count() == 2

        queue.dequeue(timeout=1.0)
        assert queue.get_pending_count() == 1

    def test_get_current_job(self):
        """Test tracking current job being processed."""
        queue = AnalysisQueue()

        assert queue.get_current_job() is None

        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        queue.enqueue(job)

        dequeued = queue.dequeue(timeout=1.0)
        current = queue.get_current_job()
        assert current is not None
        assert current.job_id == dequeued.job_id

    def test_mark_complete(self):
        """Test marking job as complete."""
        queue = AnalysisQueue()
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job)
        queue.dequeue(timeout=1.0)

        assert queue.get_current_job() is not None
        queue.mark_complete(job.job_id)
        assert queue.get_current_job() is None

    def test_mark_cancelled(self):
        """Test marking job as cancelled."""
        queue = AnalysisQueue()
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job)
        queue.dequeue(timeout=1.0)

        queue.mark_cancelled(job.job_id)
        assert queue.is_job_cancelled(job.job_id)
        assert queue.get_current_job() is None

    def test_clear_queue(self):
        """Test clearing all pending jobs."""
        queue = AnalysisQueue()

        # Add 5 jobs
        for _ in range(5):
            job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
            queue.enqueue(job)

        assert queue.get_pending_count() == 5

        # Clear queue
        cleared = queue.clear_queue()
        assert cleared == 5
        assert queue.get_pending_count() == 0

    def test_clear_queue_does_not_affect_current_job(self):
        """Test clear_queue preserves current job."""
        queue = AnalysisQueue()

        # Add jobs
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job3 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)
        queue.enqueue(job3)

        # Start processing first job
        current = queue.dequeue(timeout=1.0)
        assert queue.get_pending_count() == 2

        # Clear queue
        cleared = queue.clear_queue()
        assert cleared == 2

        # Current job should still be tracked
        assert queue.get_current_job() is not None
        assert queue.get_current_job().job_id == current.job_id

    def test_get_stats(self):
        """Test getting queue statistics."""
        queue = AnalysisQueue()

        # Initial stats
        stats = queue.get_stats()
        assert stats["pending"] == 0
        assert stats["completed"] == 0
        assert stats["cancelled"] == 0
        assert stats["current"] == 0

        # Add and process jobs
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job3 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)
        queue.enqueue(job3)

        stats = queue.get_stats()
        assert stats["pending"] == 3

        # Process first job
        dequeued = queue.dequeue(timeout=1.0)
        stats = queue.get_stats()
        assert stats["pending"] == 2
        assert stats["current"] == 1

        # Complete first job
        queue.mark_complete(dequeued.job_id)
        stats = queue.get_stats()
        assert stats["completed"] == 1
        assert stats["current"] == 0

        # Cancel remaining jobs
        queue.clear_queue()
        stats = queue.get_stats()
        assert stats["cancelled"] == 2

    def test_thread_safety_concurrent_enqueue(self):
        """Test queue handles concurrent enqueue operations."""
        queue = AnalysisQueue()
        enqueued_ids = []

        def enqueue_jobs():
            for _ in range(10):
                job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
                job_id = queue.enqueue(job)
                enqueued_ids.append(job_id)

        # Start multiple threads enqueueing
        threads = [Thread(target=enqueue_jobs) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 30 jobs total (3 threads * 10 jobs each)
        assert queue.get_pending_count() == 30
        assert len(enqueued_ids) == 30

    def test_thread_safety_concurrent_dequeue(self):
        """Test queue handles concurrent dequeue operations."""
        queue = AnalysisQueue()

        # Enqueue 20 jobs
        for _ in range(20):
            job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
            queue.enqueue(job)

        dequeued_ids = []

        def dequeue_jobs():
            for _ in range(10):
                job = queue.dequeue(timeout=1.0)
                if job:
                    dequeued_ids.append(job.job_id)

        # Start two threads dequeueing
        threads = [Thread(target=dequeue_jobs) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have dequeued all 20 jobs
        assert len(dequeued_ids) == 20
        assert queue.get_pending_count() == 0
