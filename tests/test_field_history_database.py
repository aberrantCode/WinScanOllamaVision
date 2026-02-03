"""
Tests for field history database functionality.

Tests the get_unique_companies(), get_unique_titles(), and cache invalidation
functionality in MetadataDB class.
"""

import os
import pytest
import tempfile
import shutil
from datetime import datetime
from typing import List

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from metadata_db import MetadataDB


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_metadata.db')
    db = MetadataDB(db_path=db_path)

    yield db

    db.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_pdf_dir():
    """Create temporary directory for test PDFs"""
    temp_dir = tempfile.mkdtemp()

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


class TestEmptyDatabase:
    """Test behavior with empty database"""

    def test_get_unique_companies_empty(self, temp_db):
        """Empty database returns empty list for companies"""
        companies = temp_db.get_unique_companies()
        assert companies == []

    def test_get_unique_titles_empty(self, temp_db):
        """Empty database returns empty list for titles"""
        titles = temp_db.get_unique_titles()
        assert titles == []


class TestUniqueValueExtraction:
    """Test unique value extraction from archived documents"""

    def test_single_company_extracted(self, temp_db, temp_pdf_dir):
        """Single company is extracted correctly"""
        pdf_path = os.path.join(temp_pdf_dir, 'test1.pdf')

        # Create dummy PDF file
        with open(pdf_path, 'w') as f:
            f.write('dummy pdf')

        # Archive document with company
        temp_db.archive_document(
            pdf_path=pdf_path,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        companies = temp_db.get_unique_companies(use_cache=False)
        assert companies == ['Acme Corp']

    def test_single_title_extracted(self, temp_db, temp_pdf_dir):
        """Single document title is extracted correctly"""
        pdf_path = os.path.join(temp_pdf_dir, 'test1.pdf')

        with open(pdf_path, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        titles = temp_db.get_unique_titles(use_cache=False)
        assert titles == ['Invoice']

    def test_multiple_companies_extracted(self, temp_db, temp_pdf_dir):
        """Multiple different companies are extracted"""
        companies_to_add = ['Acme Corp', 'Beta Industries', 'Gamma LLC']

        for i, company in enumerate(companies_to_add):
            pdf_path = os.path.join(temp_pdf_dir, f'test{i}.pdf')
            with open(pdf_path, 'w') as f:
                f.write('dummy pdf')

            temp_db.archive_document(
                pdf_path=pdf_path,
                source_files=[],
                document_metadata={
                    'company': company,
                    'title': 'Invoice',
                    'date': '2026-01-01'
                }
            )

        companies = temp_db.get_unique_companies(use_cache=False)
        assert set(companies) == set(companies_to_add)

    def test_multiple_titles_extracted(self, temp_db, temp_pdf_dir):
        """Multiple different titles are extracted"""
        titles_to_add = ['Invoice', 'Receipt', 'Statement']

        for i, title in enumerate(titles_to_add):
            pdf_path = os.path.join(temp_pdf_dir, f'test{i}.pdf')
            with open(pdf_path, 'w') as f:
                f.write('dummy pdf')

            temp_db.archive_document(
                pdf_path=pdf_path,
                source_files=[],
                document_metadata={
                    'company': 'Acme Corp',
                    'title': title,
                    'date': '2026-01-01'
                }
            )

        titles = temp_db.get_unique_titles(use_cache=False)
        assert set(titles) == set(titles_to_add)


class TestAlphabeticalSorting:
    """Test case-insensitive alphabetical sorting"""

    def test_companies_sorted_alphabetically(self, temp_db, temp_pdf_dir):
        """Companies are sorted alphabetically (case-insensitive)"""
        companies_unsorted = ['Zebra Corp', 'Acme Corp', 'beta industries']

        for i, company in enumerate(companies_unsorted):
            pdf_path = os.path.join(temp_pdf_dir, f'test{i}.pdf')
            with open(pdf_path, 'w') as f:
                f.write('dummy pdf')

            temp_db.archive_document(
                pdf_path=pdf_path,
                source_files=[],
                document_metadata={
                    'company': company,
                    'title': 'Invoice',
                    'date': '2026-01-01'
                }
            )

        companies = temp_db.get_unique_companies(use_cache=False)
        assert companies == ['Acme Corp', 'beta industries', 'Zebra Corp']

    def test_titles_sorted_alphabetically(self, temp_db, temp_pdf_dir):
        """Titles are sorted alphabetically (case-insensitive)"""
        titles_unsorted = ['Warranty', 'invoice', 'Receipt']

        for i, title in enumerate(titles_unsorted):
            pdf_path = os.path.join(temp_pdf_dir, f'test{i}.pdf')
            with open(pdf_path, 'w') as f:
                f.write('dummy pdf')

            temp_db.archive_document(
                pdf_path=pdf_path,
                source_files=[],
                document_metadata={
                    'company': 'Acme Corp',
                    'title': title,
                    'date': '2026-01-01'
                }
            )

        titles = temp_db.get_unique_titles(use_cache=False)
        assert titles == ['invoice', 'Receipt', 'Warranty']


class TestNullAndEmptyFiltering:
    """Test filtering of NULL and empty string values"""

    def test_null_companies_filtered(self, temp_db, temp_pdf_dir):
        """NULL companies are not included in results"""
        # Add document with company
        pdf_path1 = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path1, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path1,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # Add document without company (None)
        pdf_path2 = os.path.join(temp_pdf_dir, 'test2.pdf')
        with open(pdf_path2, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path2,
            source_files=[],
            document_metadata={
                'company': None,
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        companies = temp_db.get_unique_companies(use_cache=False)
        assert companies == ['Acme Corp']

    def test_empty_companies_filtered(self, temp_db, temp_pdf_dir):
        """Empty string companies are not included in results"""
        # Add document with company
        pdf_path1 = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path1, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path1,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # Add document with empty company
        pdf_path2 = os.path.join(temp_pdf_dir, 'test2.pdf')
        with open(pdf_path2, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path2,
            source_files=[],
            document_metadata={
                'company': '',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        companies = temp_db.get_unique_companies(use_cache=False)
        assert companies == ['Acme Corp']

    def test_null_titles_filtered(self, temp_db, temp_pdf_dir):
        """NULL titles are not included in results"""
        # Add document with title
        pdf_path1 = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path1, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path1,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # Add document without title
        pdf_path2 = os.path.join(temp_pdf_dir, 'test2.pdf')
        with open(pdf_path2, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path2,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': None,
                'date': '2026-01-01'
            }
        )

        titles = temp_db.get_unique_titles(use_cache=False)
        assert titles == ['Invoice']

    def test_empty_titles_filtered(self, temp_db, temp_pdf_dir):
        """Empty string titles are not included in results"""
        # Add document with title
        pdf_path1 = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path1, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path1,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # Add document with empty title
        pdf_path2 = os.path.join(temp_pdf_dir, 'test2.pdf')
        with open(pdf_path2, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path2,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': '',
                'date': '2026-01-01'
            }
        )

        titles = temp_db.get_unique_titles(use_cache=False)
        assert titles == ['Invoice']


class TestCaching:
    """Test cache population and invalidation"""

    def test_cache_populated_on_first_call(self, temp_db, temp_pdf_dir):
        """Cache is populated on first call with use_cache=True"""
        pdf_path = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # First call populates cache
        companies1 = temp_db.get_unique_companies(use_cache=True)

        # Second call uses cache (should be same object reference)
        companies2 = temp_db.get_unique_companies(use_cache=True)

        assert companies1 is companies2  # Same object, from cache

    def test_cache_bypassed_with_use_cache_false(self, temp_db, temp_pdf_dir):
        """Cache is bypassed when use_cache=False"""
        pdf_path = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # Populate cache
        companies1 = temp_db.get_unique_companies(use_cache=True)

        # Bypass cache
        companies2 = temp_db.get_unique_companies(use_cache=False)

        assert companies1 is not companies2  # Different objects
        assert companies1 == companies2  # But same content

    def test_cache_invalidated_after_archive(self, temp_db, temp_pdf_dir):
        """Cache is invalidated after archiving new document"""
        # Archive first document
        pdf_path1 = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path1, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path1,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # Populate cache
        companies1 = temp_db.get_unique_companies(use_cache=True)
        assert companies1 == ['Acme Corp']

        # Archive second document (should invalidate cache)
        pdf_path2 = os.path.join(temp_pdf_dir, 'test2.pdf')
        with open(pdf_path2, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path2,
            source_files=[],
            document_metadata={
                'company': 'Beta Industries',
                'title': 'Receipt',
                'date': '2026-01-02'
            }
        )

        # Get companies again - should query DB and show both
        companies2 = temp_db.get_unique_companies(use_cache=True)
        assert set(companies2) == {'Acme Corp', 'Beta Industries'}

    def test_manual_cache_invalidation(self, temp_db, temp_pdf_dir):
        """Manual cache invalidation clears cached values"""
        pdf_path = os.path.join(temp_pdf_dir, 'test1.pdf')
        with open(pdf_path, 'w') as f:
            f.write('dummy pdf')

        temp_db.archive_document(
            pdf_path=pdf_path,
            source_files=[],
            document_metadata={
                'company': 'Acme Corp',
                'title': 'Invoice',
                'date': '2026-01-01'
            }
        )

        # Populate cache
        temp_db.get_unique_companies(use_cache=True)
        temp_db.get_unique_titles(use_cache=True)

        assert temp_db._companies_cache is not None
        assert temp_db._titles_cache is not None

        # Invalidate
        temp_db.invalidate_field_history_cache()

        assert temp_db._companies_cache is None
        assert temp_db._titles_cache is None


class TestDeduplication:
    """Test deduplication of duplicate values"""

    def test_duplicate_companies_deduplicated(self, temp_db, temp_pdf_dir):
        """Multiple documents with same company result in single entry"""
        company = 'Acme Corp'

        for i in range(3):
            pdf_path = os.path.join(temp_pdf_dir, f'test{i}.pdf')
            with open(pdf_path, 'w') as f:
                f.write('dummy pdf')

            temp_db.archive_document(
                pdf_path=pdf_path,
                source_files=[],
                document_metadata={
                    'company': company,
                    'title': f'Invoice{i}',
                    'date': '2026-01-01'
                }
            )

        companies = temp_db.get_unique_companies(use_cache=False)
        assert companies == ['Acme Corp']
        assert len(companies) == 1

    def test_duplicate_titles_deduplicated(self, temp_db, temp_pdf_dir):
        """Multiple documents with same title result in single entry"""
        title = 'Invoice'

        for i in range(3):
            pdf_path = os.path.join(temp_pdf_dir, f'test{i}.pdf')
            with open(pdf_path, 'w') as f:
                f.write('dummy pdf')

            temp_db.archive_document(
                pdf_path=pdf_path,
                source_files=[],
                document_metadata={
                    'company': f'Company{i}',
                    'title': title,
                    'date': '2026-01-01'
                }
            )

        titles = temp_db.get_unique_titles(use_cache=False)
        assert titles == ['Invoice']
        assert len(titles) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
