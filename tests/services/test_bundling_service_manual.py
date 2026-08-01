"""
Tests for BundlingService.create_or_extend_manual_bundle.

Covers the manual page-bundling merge rule invoked from the Analyze list view:
- 0 existing bundles among the selection  -> create a new 'suggested' bundle
- exactly 1 existing bundle               -> add the not-yet-member pages to it
- 2+ distinct existing bundles            -> abort (ambiguous)
- idempotency (re-bundling the same set adds nothing)
- rejected bundles are ignored for the rule

The db is fully mocked; no Qt and no real SQLite are involved.
"""

from unittest.mock import MagicMock

import pytest

from services.bundling_service import BundlingService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    return BundlingService(mock_db)


def _wire_image_ids(mock_db, mapping: dict[str, int | None]):
    """Make get_image_id return the mapped id for each path."""
    mock_db.get_image_id.side_effect = lambda p: mapping.get(p)


def _wire_bundles_for_image(mock_db, mapping: dict[int, list[dict]]):
    """Make get_bundles_for_image return the mapped bundle rows per image id."""
    mock_db.get_bundles_for_image.side_effect = lambda iid: mapping.get(iid, [])


class TestCreateOrExtendManualBundle:
    def test_none_bundled_creates_new_bundle(self, service, mock_db):
        _wire_image_ids(mock_db, {"a.png": 1, "b.png": 2})
        _wire_bundles_for_image(mock_db, {1: [], 2: []})
        mock_db.save_bundle_suggestion.return_value = 99

        result = service.create_or_extend_manual_bundle(["a.png", "b.png"])

        assert result["status"] == "created"
        assert result["bundle_id"] == 99
        assert result["existing_bundle_ids"] == []
        # Created with both resolved paths, status stays 'suggested' via save_bundle_suggestion
        args, kwargs = mock_db.save_bundle_suggestion.call_args
        assert kwargs["file_paths"] == ["a.png", "b.png"]
        # Must not try to extend an existing bundle
        mock_db.add_images_to_bundle.assert_not_called()

    def test_one_existing_adds_others_to_that_bundle(self, service, mock_db):
        _wire_image_ids(mock_db, {"a.png": 1, "b.png": 2, "c.png": 3})
        # Only page 1 is already in bundle 10 (suggested); 2 and 3 are loose
        _wire_bundles_for_image(
            mock_db,
            {1: [{"id": 10, "status": "suggested"}], 2: [], 3: []},
        )
        mock_db.get_bundle_images.return_value = [{"id": 1}]

        result = service.create_or_extend_manual_bundle(["a.png", "b.png", "c.png"])

        assert result["status"] == "extended"
        assert result["bundle_id"] == 10
        assert result["existing_bundle_ids"] == [10]
        # Only the not-yet-member image ids are added, in selection order
        mock_db.add_images_to_bundle.assert_called_once_with(10, [2, 3])
        mock_db.save_bundle_suggestion.assert_not_called()

    def test_two_separate_bundles_aborts(self, service, mock_db):
        _wire_image_ids(mock_db, {"a.png": 1, "b.png": 2})
        _wire_bundles_for_image(
            mock_db,
            {1: [{"id": 10, "status": "suggested"}], 2: [{"id": 20, "status": "suggested"}]},
        )

        result = service.create_or_extend_manual_bundle(["a.png", "b.png"])

        assert result["status"] == "ambiguous"
        assert result["bundle_id"] is None
        assert result["existing_bundle_ids"] == [10, 20]
        mock_db.save_bundle_suggestion.assert_not_called()
        mock_db.add_images_to_bundle.assert_not_called()

    def test_idempotent_rebundle_same_set_adds_nothing(self, service, mock_db):
        _wire_image_ids(mock_db, {"a.png": 1, "b.png": 2})
        # Both pages already in bundle 10
        _wire_bundles_for_image(
            mock_db,
            {1: [{"id": 10, "status": "suggested"}], 2: [{"id": 10, "status": "suggested"}]},
        )
        mock_db.get_bundle_images.return_value = [{"id": 1}, {"id": 2}]

        result = service.create_or_extend_manual_bundle(["a.png", "b.png"])

        assert result["status"] == "extended"
        assert result["bundle_id"] == 10
        assert result["added_image_ids"] == []
        # Nothing new to add -> no write
        mock_db.add_images_to_bundle.assert_not_called()

    def test_rejected_bundle_is_ignored_and_new_bundle_created(self, service, mock_db):
        _wire_image_ids(mock_db, {"a.png": 1, "b.png": 2})
        # Page 1 only belongs to a rejected bundle -> should not count as existing
        _wire_bundles_for_image(
            mock_db,
            {1: [{"id": 10, "status": "rejected"}], 2: []},
        )
        mock_db.save_bundle_suggestion.return_value = 77

        result = service.create_or_extend_manual_bundle(["a.png", "b.png"])

        assert result["status"] == "created"
        assert result["bundle_id"] == 77
        assert result["existing_bundle_ids"] == []

    def test_unresolvable_paths_return_error(self, service, mock_db):
        _wire_image_ids(mock_db, {"a.png": None, "b.png": None})

        result = service.create_or_extend_manual_bundle(["a.png", "b.png"])

        assert result["status"] == "error"
        assert result["bundle_id"] is None
        mock_db.save_bundle_suggestion.assert_not_called()
