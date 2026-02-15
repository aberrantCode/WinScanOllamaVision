"""Comprehensive tests for AnalysisQueue.

Tests queue-based analysis job management including:
- Job creation and priority ordering
- Thread-safe enqueue/dequeue operations
- Job lifecycle (pending -> current -> completed/cancelled)
- Queue statistics and clearing
"""

import time
from unittest.mock import patch

import pytest

from services.analysis_queue import (
    AnalysisJob,
    AnalysisQueue,
    JobPriority,
    JobType,
)


class TestJobType:
    """Tests for JobType enum."""

    def test_scan_all_value(self):
        """Test SCAN_ALL enum value."""
        assert JobType.SCAN_ALL.value == "scan_all"

    def test_analyze_files_value(self):
        """Test ANALYZE_FILES enum value."""
        assert JobType.ANALYZE_FILES.value == "analyze_files"


class TestJobPriority:
    """Tests for JobPriority enum."""

    def test_high_priority_value(self):
        """Test HIGH priority has value 1."""
        assert JobPriority.HIGH.value == 1

    def test_normal_priority_value(self):
        """Test NORMAL priority has value 2."""
        assert JobPriority.NORMAL.value == 2

    def test_high_priority_is_higher_than_normal(self):
        """Test HIGH priority (1) is numerically lower than NORMAL (2)."""
        assert JobPriority.HIGH.value < JobPriority.NORMAL.value


class TestAnalysisJob:
    """Tests for AnalysisJob dataclass."""

    def test_create_job_with_scan_all_type(self):
        """Test creating SCAN_ALL job."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        assert job.job_type == JobType.SCAN_ALL
        assert job.priority == JobPriority.NORMAL.value
        assert job.file_paths == []
        assert job.force_reanalysis is False
        assert job.job_id is not None
        assert len(job.job_id) > 0

    def test_create_job_with_analyze_files_type(self):
        """Test creating ANALYZE_FILES job with file paths."""
        file_paths = ["/test/file1.png", "/test/file2.png"]
        job = AnalysisJob.create(
            job_type=JobType.ANALYZE_FILES,
            priority=JobPriority.HIGH,
            file_paths=file_paths,
        )

        assert job.job_type == JobType.ANALYZE_FILES
        assert job.priority == JobPriority.HIGH.value
        assert job.file_paths == file_paths

    def test_create_job_with_force_reanalysis(self):
        """Test creating job with force_reanalysis flag."""
        job = AnalysisJob.create(
            job_type=JobType.SCAN_ALL,
            priority=JobPriority.NORMAL,
            force_reanalysis=True,
        )

        assert job.force_reanalysis is True

    def test_create_job_generates_unique_ids(self):
        """Test that each created job gets unique ID."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        assert job1.job_id != job2.job_id

    def test_create_job_sets_timestamp(self):
        """Test that job creation sets timestamp."""
        with patch("time.time", return_value=12345.0):
            job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        assert job.created_at == 12345.0

    def test_job_ordering_by_priority(self):
        """Test that jobs are ordered by priority (lower number = higher priority)."""
        high_priority_job = AnalysisJob(priority=JobPriority.HIGH.value, created_at=time.time())
        normal_priority_job = AnalysisJob(priority=JobPriority.NORMAL.value, created_at=time.time())

        # High priority (1) should be < normal priority (2)
        assert high_priority_job < normal_priority_job

    def test_job_ordering_by_timestamp_when_same_priority(self):
        """Test that jobs with same priority are ordered by timestamp."""
        older_job = AnalysisJob(priority=1, created_at=100.0)
        newer_job = AnalysisJob(priority=1, created_at=200.0)

        # Older job (lower timestamp) should be < newer job
        assert older_job < newer_job


class TestAnalysisQueueBasics:
    """Tests for basic AnalysisQueue operations."""

    @pytest.fixture
    def queue(self):
        """Create fresh queue for each test."""
        return AnalysisQueue()

    def test_init_creates_empty_queue(self, queue):
        """Test queue initialization."""
        assert queue.get_pending_count() == 0
        assert queue.get_current_job() is None

    def test_enqueue_adds_job_to_queue(self, queue):
        """Test enqueue adds job to queue."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_id = queue.enqueue(job)

        assert job_id == job.job_id
        assert queue.get_pending_count() == 1

    def test_enqueue_returns_job_id(self, queue):
        """Test enqueue returns job ID."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_id = queue.enqueue(job)

        assert job_id is not None
        assert len(job_id) > 0

    def test_dequeue_returns_job(self, queue):
        """Test dequeue returns enqueued job."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        queue.enqueue(job)

        dequeued = queue.dequeue(timeout=1.0)

        assert dequeued is not None
        assert dequeued.job_id == job.job_id

    def test_dequeue_sets_current_job(self, queue):
        """Test dequeue sets current job."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        queue.enqueue(job)

        dequeued = queue.dequeue(timeout=1.0)

        current = queue.get_current_job()
        assert current is not None
        assert current.job_id == dequeued.job_id

    def test_dequeue_returns_none_on_timeout(self, queue):
        """Test dequeue returns None when queue is empty and timeout expires."""
        # Empty queue with short timeout
        result = queue.dequeue(timeout=0.1)

        assert result is None

    def test_get_pending_count_returns_correct_count(self, queue):
        """Test get_pending_count returns accurate count."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        assert queue.get_pending_count() == 1

        queue.enqueue(job2)
        assert queue.get_pending_count() == 2


class TestAnalysisQueueJobLifecycle:
    """Tests for job lifecycle management."""

    @pytest.fixture
    def queue(self):
        """Create fresh queue for each test."""
        return AnalysisQueue()

    def test_mark_complete_records_completion(self, queue):
        """Test mark_complete records job completion."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_id = queue.enqueue(job)
        queue.dequeue(timeout=1.0)

        queue.mark_complete(job_id)

        stats = queue.get_stats()
        assert stats["completed"] == 1

    def test_mark_complete_clears_current_job(self, queue):
        """Test mark_complete clears current job."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_id = queue.enqueue(job)
        queue.dequeue(timeout=1.0)

        queue.mark_complete(job_id)

        assert queue.get_current_job() is None

    def test_mark_complete_does_not_clear_different_current_job(self, queue):
        """Test mark_complete only clears matching current job."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        job1_id = queue.enqueue(job1)
        queue.enqueue(job2)

        # Dequeue job1 (sets as current)
        queue.dequeue(timeout=1.0)

        # Mark job2 as complete (should not clear current since job1 is current)
        queue.mark_complete(job2.job_id)

        current = queue.get_current_job()
        assert current is not None
        assert current.job_id == job1_id

    def test_mark_cancelled_records_cancellation(self, queue):
        """Test mark_cancelled records job cancellation."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_id = queue.enqueue(job)
        queue.dequeue(timeout=1.0)

        queue.mark_cancelled(job_id)

        assert queue.is_job_cancelled(job_id) is True
        stats = queue.get_stats()
        assert stats["cancelled"] == 1

    def test_mark_cancelled_clears_current_job(self, queue):
        """Test mark_cancelled clears current job."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_id = queue.enqueue(job)
        queue.dequeue(timeout=1.0)

        queue.mark_cancelled(job_id)

        assert queue.get_current_job() is None

    def test_is_job_cancelled_returns_false_for_uncancelled(self, queue):
        """Test is_job_cancelled returns False for uncancelled job."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job_id = queue.enqueue(job)

        assert queue.is_job_cancelled(job_id) is False


class TestAnalysisQueueClearing:
    """Tests for queue clearing operations."""

    @pytest.fixture
    def queue(self):
        """Create fresh queue for each test."""
        return AnalysisQueue()

    def test_clear_queue_removes_all_pending_jobs(self, queue):
        """Test clear_queue removes all pending jobs."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job3 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)
        queue.enqueue(job3)

        count = queue.clear_queue()

        assert count == 3
        assert queue.get_pending_count() == 0

    def test_clear_queue_marks_jobs_as_cancelled(self, queue):
        """Test clear_queue marks removed jobs as cancelled."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)

        queue.clear_queue()

        assert queue.is_job_cancelled(job1.job_id) is True
        assert queue.is_job_cancelled(job2.job_id) is True

    def test_clear_queue_does_not_clear_current_job(self, queue):
        """Test clear_queue does not clear currently processing job."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)

        # Dequeue job1 (sets as current)
        current = queue.dequeue(timeout=1.0)

        # Clear remaining jobs
        count = queue.clear_queue()

        # Only job2 should be cleared
        assert count == 1
        # Current job should still be set
        assert queue.get_current_job() is not None
        assert queue.get_current_job().job_id == current.job_id

    def test_clear_queue_returns_zero_for_empty_queue(self, queue):
        """Test clear_queue returns 0 for empty queue."""
        count = queue.clear_queue()
        assert count == 0

    def test_clear_queue_handles_queue_empty_exception(self, queue):
        """Test clear_queue handles race condition where queue becomes empty during iteration."""
        import queue as queue_module

        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        queue.enqueue(job1)

        # Mock get_nowait to raise Empty after checking empty()
        original_get_nowait = queue._queue.get_nowait
        call_count = {"count": 0}

        def mock_get_nowait(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # First call succeeds and returns the job
                return original_get_nowait(*args, **kwargs)
            else:
                # Second call raises Empty (simulating race condition)
                raise queue_module.Empty()

        # Mock empty() to return False twice, then True
        empty_call_count = {"count": 0}

        def mock_empty(*args, **kwargs):
            empty_call_count["count"] += 1
            # Report not empty for first two checks, then empty
            return empty_call_count["count"] > 2

        with (
            patch.object(queue._queue, "get_nowait", side_effect=mock_get_nowait),
            patch.object(queue._queue, "empty", side_effect=mock_empty),
        ):
            count = queue.clear_queue()

        # Should have cleared 1 job before hitting the Empty exception
        assert count == 1


class TestAnalysisQueueStats:
    """Tests for queue statistics."""

    @pytest.fixture
    def queue(self):
        """Create fresh queue for each test."""
        return AnalysisQueue()

    def test_get_stats_returns_all_counts(self, queue):
        """Test get_stats returns all count fields."""
        stats = queue.get_stats()

        assert "pending" in stats
        assert "completed" in stats
        assert "cancelled" in stats
        assert "current" in stats

    def test_get_stats_initial_state(self, queue):
        """Test get_stats for empty queue."""
        stats = queue.get_stats()

        assert stats["pending"] == 0
        assert stats["completed"] == 0
        assert stats["cancelled"] == 0
        assert stats["current"] == 0

    def test_get_stats_with_pending_jobs(self, queue):
        """Test get_stats with pending jobs."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)

        stats = queue.get_stats()
        assert stats["pending"] == 2
        assert stats["current"] == 0

    def test_get_stats_with_current_job(self, queue):
        """Test get_stats with current job."""
        job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        queue.enqueue(job)
        queue.dequeue(timeout=1.0)

        stats = queue.get_stats()
        assert stats["current"] == 1
        assert stats["pending"] == 0

    def test_get_stats_with_completed_jobs(self, queue):
        """Test get_stats with completed jobs."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        job1_id = queue.enqueue(job1)
        job2_id = queue.enqueue(job2)

        queue.dequeue(timeout=1.0)
        queue.mark_complete(job1_id)

        queue.dequeue(timeout=1.0)
        queue.mark_complete(job2_id)

        stats = queue.get_stats()
        assert stats["completed"] == 2
        assert stats["current"] == 0

    def test_get_stats_with_cancelled_jobs(self, queue):
        """Test get_stats with cancelled jobs."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)

        queue.clear_queue()

        stats = queue.get_stats()
        assert stats["cancelled"] == 2

    def test_get_stats_mixed_states(self, queue):
        """Test get_stats with jobs in different states."""
        job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job3 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        job4 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)
        queue.enqueue(job3)
        queue.enqueue(job4)

        # Process job1 and complete it
        dequeued1 = queue.dequeue(timeout=1.0)
        queue.mark_complete(dequeued1.job_id)

        # Process job2 and cancel it
        dequeued2 = queue.dequeue(timeout=1.0)
        queue.mark_cancelled(dequeued2.job_id)

        # Job3 and Job4 remain pending

        stats = queue.get_stats()
        assert stats["completed"] == 1
        assert stats["cancelled"] == 1
        assert stats["pending"] == 2
        assert stats["current"] == 0


class TestAnalysisQueuePriorityOrdering:
    """Tests for priority-based job ordering."""

    @pytest.fixture
    def queue(self):
        """Create fresh queue for each test."""
        return AnalysisQueue()

    def test_high_priority_jobs_dequeued_first(self, queue):
        """Test that high priority jobs are dequeued before normal priority."""
        normal_job = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)
        high_job = AnalysisJob.create(job_type=JobType.ANALYZE_FILES, priority=JobPriority.HIGH)

        # Enqueue normal priority first
        queue.enqueue(normal_job)
        # Enqueue high priority second
        queue.enqueue(high_job)

        # High priority should be dequeued first
        first = queue.dequeue(timeout=1.0)
        assert first.job_id == high_job.job_id
        assert first.priority == JobPriority.HIGH.value

    def test_same_priority_jobs_dequeued_in_fifo_order(self, queue):
        """Test that jobs with same priority are dequeued FIFO."""
        # Create jobs with same priority but different timestamps
        with patch("time.time", return_value=100.0):
            job1 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        with patch("time.time", return_value=200.0):
            job2 = AnalysisJob.create(job_type=JobType.SCAN_ALL, priority=JobPriority.NORMAL)

        queue.enqueue(job1)
        queue.enqueue(job2)

        # Job1 (older timestamp) should be dequeued first
        first = queue.dequeue(timeout=1.0)
        assert first.job_id == job1.job_id

        # Job2 should be dequeued second
        second = queue.dequeue(timeout=1.0)
        assert second.job_id == job2.job_id
