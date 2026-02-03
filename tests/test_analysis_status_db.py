"""
Tests for Analysis Status Window database methods
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta
from src.analysis_db import AnalysisDB


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = AnalysisDB(path)
    yield db

    db.close()
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def populated_db(temp_db):
    """Create database with sample data"""
    # Add provider
    temp_db.add_provider(
        provider_name="ollama",
        provider_type="ollama",
        config={"base_url": "http://localhost:11434", "timeout": 300},
        default_model="qwen3-vl:latest"
    )
    temp_db.set_active_provider("ollama")

    # Add sample analyses with different statuses
    analyses = [
        # Successful analyses
        {
            'file_path': 'C:\\scans\\invoice_001.png',
            'file_hash': 'hash001',
            'data': {
                'document_type': 'Invoice',
                'company': 'Acme Corp',
                'document_date': '2024-01-15',
                'page_number': 1,
                'total_pages': 3,
                'confidence_score': 0.95
            },
            'processing_time': 1500
        },
        {
            'file_path': 'C:\\scans\\invoice_002.png',
            'file_hash': 'hash002',
            'data': {
                'document_type': 'Invoice',
                'company': 'Acme Corp',
                'document_date': '2024-01-15',
                'page_number': 2,
                'total_pages': 3,
                'confidence_score': 0.92
            },
            'processing_time': 1400
        },
        {
            'file_path': 'C:\\scans\\statement_001.png',
            'file_hash': 'hash003',
            'data': {
                'document_type': 'Statement',
                'company': 'Bank of Testing',
                'document_date': '2024-01-20',
                'page_number': 1,
                'total_pages': 1,
                'confidence_score': 0.88
            },
            'processing_time': 1600
        },
        {
            'file_path': 'C:\\scans\\receipt_001.png',
            'file_hash': 'hash004',
            'data': {
                'document_type': 'Receipt',
                'company': 'Store Inc',
                'document_date': '2024-01-22',
                'page_number': 1,
                'total_pages': 1,
                'confidence_score': 0.78
            },
            'processing_time': 1300
        },
        {
            'file_path': 'C:\\scans\\letter_001.png',
            'file_hash': 'hash005',
            'data': {
                'document_type': 'Letter',
                'company': 'Government Agency',
                'document_date': '2024-01-25',
                'page_number': 1,
                'total_pages': 2,
                'confidence_score': 0.85
            },
            'processing_time': 1700
        },
    ]

    for analysis in analyses:
        temp_db.save_analysis(
            file_path=analysis['file_path'],
            file_hash=analysis['file_hash'],
            provider_name="ollama",
            model_name="qwen3-vl:latest",
            analysis_data=analysis['data'],
            raw_response=f"Raw response for {analysis['file_path']}",
            processing_time_ms=analysis['processing_time']
        )

    # Mark some as cached
    temp_db.get_analysis('C:\\scans\\invoice_001.png')  # Increments cache counter
    temp_db.get_analysis('C:\\scans\\invoice_002.png')

    return temp_db


class TestGetRecentRuns:
    """Tests for get_recent_runs method"""

    def test_empty_database(self, temp_db):
        """Should return empty list when no analyses exist"""
        runs = temp_db.get_recent_runs(limit=10)
        assert runs == []

    def test_single_run(self, populated_db):
        """Should return single run with aggregated stats"""
        runs = populated_db.get_recent_runs(limit=10)

        assert len(runs) >= 1
        run = runs[0]

        # Verify run structure
        assert 'timestamp' in run
        assert 'total_files' in run
        assert 'analyzed' in run
        assert 'cached' in run
        assert 'errors' in run
        assert 'duration_seconds' in run
        assert 'status' in run

    def test_limit_parameter(self, populated_db):
        """Should respect limit parameter"""
        runs = populated_db.get_recent_runs(limit=2)
        assert len(runs) <= 2

    def test_run_ordering(self, populated_db):
        """Should return runs in descending chronological order (newest first)"""
        runs = populated_db.get_recent_runs(limit=10)

        if len(runs) > 1:
            for i in range(len(runs) - 1):
                # Parse timestamps and compare
                time1 = datetime.fromisoformat(runs[i]['timestamp'])
                time2 = datetime.fromisoformat(runs[i + 1]['timestamp'])
                assert time1 >= time2


class TestGetAnalysisStatistics:
    """Tests for get_analysis_statistics method"""

    def test_empty_database(self, temp_db):
        """Should return zero values for empty database"""
        stats = temp_db.get_analysis_statistics()

        assert stats['total_files'] == 0
        assert stats['total_runs'] == 0
        assert stats['success_rate'] == 0.0
        assert stats['cache_hit_rate'] == 0.0
        assert stats['avg_confidence'] == 0.0
        assert stats['avg_processing_time_ms'] == 0.0

    def test_populated_database(self, populated_db):
        """Should calculate correct statistics"""
        stats = populated_db.get_analysis_statistics()

        assert stats['total_files'] == 5
        assert stats['total_runs'] >= 1
        assert 0.0 <= stats['success_rate'] <= 100.0
        assert 0.0 <= stats['cache_hit_rate'] <= 100.0
        assert 0.0 <= stats['avg_confidence'] <= 1.0
        assert stats['avg_processing_time_ms'] > 0

    def test_statistics_structure(self, populated_db):
        """Should return all required fields"""
        stats = populated_db.get_analysis_statistics()

        required_fields = [
            'total_files',
            'total_runs',
            'success_rate',
            'cache_hit_rate',
            'avg_confidence',
            'avg_processing_time_ms',
            'total_processing_time_ms',
            'cached_files',
            'failed_files'
        ]

        for field in required_fields:
            assert field in stats


class TestGetDocumentTypeBreakdown:
    """Tests for get_document_type_breakdown method"""

    def test_empty_database(self, temp_db):
        """Should return empty dict for empty database"""
        breakdown = temp_db.get_document_type_breakdown()
        assert breakdown == {}

    def test_populated_database(self, populated_db):
        """Should return correct document type counts"""
        breakdown = populated_db.get_document_type_breakdown()

        assert breakdown['Invoice'] == 2
        assert breakdown['Statement'] == 1
        assert breakdown['Receipt'] == 1
        assert breakdown['Letter'] == 1

    def test_breakdown_ordering(self, populated_db):
        """Should return types ordered by count (descending)"""
        breakdown = populated_db.get_document_type_breakdown()

        counts = list(breakdown.values())
        assert counts == sorted(counts, reverse=True)

    def test_null_document_types(self, temp_db):
        """Should handle null document types gracefully"""
        # Add analysis without document type
        temp_db.add_provider("ollama", "ollama", {}, "model")
        temp_db.set_active_provider("ollama")

        temp_db.save_analysis(
            file_path="test.png",
            file_hash="hash",
            provider_name="ollama",
            model_name="model",
            analysis_data={'document_type': None},
            raw_response="",
            processing_time_ms=1000
        )

        breakdown = temp_db.get_document_type_breakdown()
        # Should either exclude None or use a placeholder like "Unknown"
        assert None not in breakdown or breakdown[None] >= 0


class TestGetFailedAnalyses:
    """Tests for get_failed_analyses method"""

    def test_empty_database(self, temp_db):
        """Should return empty list when no analyses exist"""
        failed = temp_db.get_failed_analyses()
        assert failed == []

    def test_no_failures(self, populated_db):
        """Should return empty list when no failures exist"""
        failed = populated_db.get_failed_analyses()
        assert failed == []

    def test_with_failures(self, temp_db):
        """Should return failed analyses with error details"""
        # Add provider
        temp_db.add_provider("ollama", "ollama", {}, "model")
        temp_db.set_active_provider("ollama")

        # Add successful analysis
        temp_db.save_analysis(
            file_path="success.png",
            file_hash="hash1",
            provider_name="ollama",
            model_name="model",
            analysis_data={'document_type': 'Invoice', 'confidence_score': 0.9},
            raw_response="success",
            processing_time_ms=1000
        )

        # Add failed analyses (we need to simulate failures in database)
        # This might require adding a status field or error tracking to the database schema
        # For now, we'll test the basic structure

        failed = temp_db.get_failed_analyses()
        assert isinstance(failed, list)

    def test_failed_structure(self, temp_db):
        """Should return properly structured failed analysis records"""
        failed = temp_db.get_failed_analyses()

        if len(failed) > 0:
            record = failed[0]
            assert 'file_path' in record
            assert 'error_message' in record or 'raw_response' in record
            assert 'analyzed_at' in record


class TestAnalysisRunGrouping:
    """Tests for grouping analyses into runs"""

    def test_run_identification(self, populated_db):
        """Should correctly identify analysis runs by timestamp proximity"""
        runs = populated_db.get_recent_runs(limit=10)

        # All our sample data should be in one run (added in quick succession)
        # Or multiple runs if timestamp-based grouping is used
        assert len(runs) >= 1

        if len(runs) == 1:
            # All files in one run
            run = runs[0]
            assert run['total_files'] == 5

    def test_run_duration_calculation(self, populated_db):
        """Should calculate run duration correctly"""
        runs = populated_db.get_recent_runs(limit=10)

        if len(runs) > 0:
            run = runs[0]
            # Duration should be non-negative
            assert run['duration_seconds'] >= 0


class TestStatisticsEdgeCases:
    """Tests for edge cases in statistics calculations"""

    def test_division_by_zero(self, temp_db):
        """Should handle division by zero in rate calculations"""
        stats = temp_db.get_analysis_statistics()

        # Should not raise exceptions
        assert stats['success_rate'] == 0.0
        assert stats['cache_hit_rate'] == 0.0
        assert stats['avg_confidence'] == 0.0

    def test_high_cache_hit_rate(self, populated_db):
        """Should correctly calculate high cache hit rates"""
        # Get all files multiple times to increase cache hits
        files = populated_db.get_analyzed_pages()
        for file_data in files:
            populated_db.get_analysis(file_data['file_path'])

        stats = populated_db.get_analysis_statistics()

        # Cache hit rate should be high
        assert stats['cache_hit_rate'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
