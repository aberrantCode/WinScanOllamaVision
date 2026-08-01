"""
Integration tests for the manual-bundling data path against a real SQLite DB.

Proves the whole create -> read-back cycle works with ZERO analyzed pages (the
Ollama-down scenario): pages are only *registered* in image_files, never analyzed.
"""

import pytest

from db.analysis_db import AnalysisDB
from services.bundling_service import BundlingService


@pytest.fixture
def db(tmp_path):
    database = AnalysisDB(db_path=str(tmp_path / "manual_bundle.db"))
    yield database
    database.close()


def _register(db: AnalysisDB, name: str) -> str:
    """Register an (un-analyzed) image file and return its path."""
    path = f"C:\\scans\\{name}"
    db._image_files.register(
        file_path=path,
        file_hash=f"hash-{name}",
        directory_path="C:\\scans",
        filename=name,
        file_size=100,
        file_mtime=0.0,
    )
    return path


def test_create_then_read_back_bundle_with_zero_analysis(db):
    """A manually created bundle round-trips through get_bundle_with_images."""
    p1 = _register(db, "a.png")
    p2 = _register(db, "b.png")
    service = BundlingService(db)

    result = service.create_or_extend_manual_bundle([p1, p2])
    assert result["status"] == "created"
    bundle_id = result["bundle_id"]
    assert bundle_id is not None

    loaded = db.get_bundle_with_images(bundle_id)
    assert loaded is not None
    assert loaded["id"] == bundle_id
    # file_paths are ordered and present even though no analysis exists
    assert loaded["file_paths"] == [p1, p2]
    # analyses has one (empty) entry per page — forms tolerate {}
    assert len(loaded["analyses"]) == 2


def test_extend_existing_bundle_appends_pages(db):
    """Re-bundling with one shared page extends the same bundle in order."""
    p1 = _register(db, "a.png")
    p2 = _register(db, "b.png")
    p3 = _register(db, "c.png")
    service = BundlingService(db)

    first = service.create_or_extend_manual_bundle([p1, p2])
    bundle_id = first["bundle_id"]

    second = service.create_or_extend_manual_bundle([p1, p3])
    assert second["status"] == "extended"
    assert second["bundle_id"] == bundle_id

    loaded = db.get_bundle_with_images(bundle_id)
    assert loaded["file_paths"] == [p1, p2, p3]


def test_get_bundle_with_images_returns_none_for_missing(db):
    assert db.get_bundle_with_images(999) is None
