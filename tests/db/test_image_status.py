"""Tests for ImageStatus enum."""

import pytest

from db.image_status import ImageStatus


class TestImageStatus:
    """Tests for ImageStatus enumeration."""

    def test_all_status_values_exist(self):
        """Test that all expected status values are defined."""
        expected_statuses = {
            "REGISTERED",
            "PENDING",
            "ANALYZING",
            "ANALYZED",
            "BUNDLED",
            "DELETED",
        }
        actual_statuses = {status.name for status in ImageStatus}
        assert actual_statuses == expected_statuses

    def test_status_values_are_lowercase(self):
        """Test that enum values are lowercase versions of names."""
        for status in ImageStatus:
            assert status.value == status.name.lower()

    def test_status_can_be_accessed_by_name(self):
        """Test that statuses can be accessed by name."""
        assert ImageStatus.REGISTERED.value == "registered"
        assert ImageStatus.PENDING.value == "pending"
        assert ImageStatus.ANALYZING.value == "analyzing"
        assert ImageStatus.ANALYZED.value == "analyzed"
        assert ImageStatus.BUNDLED.value == "bundled"
        assert ImageStatus.DELETED.value == "deleted"

    def test_status_can_be_accessed_by_value(self):
        """Test that statuses can be looked up by value."""
        assert ImageStatus("registered") == ImageStatus.REGISTERED
        assert ImageStatus("pending") == ImageStatus.PENDING
        assert ImageStatus("analyzing") == ImageStatus.ANALYZING
        assert ImageStatus("analyzed") == ImageStatus.ANALYZED
        assert ImageStatus("bundled") == ImageStatus.BUNDLED
        assert ImageStatus("deleted") == ImageStatus.DELETED

    def test_invalid_status_value_raises_error(self):
        """Test that invalid status values raise ValueError."""
        with pytest.raises(ValueError):
            ImageStatus("invalid_status")

    def test_status_display_name_formatting(self):
        """Test that status names can be formatted for display."""
        # This is the logic used in file_details_grid.py
        for status in ImageStatus:
            display_name = status.name.replace("_", " ").title()
            # All current statuses are single words, so title case should match
            assert display_name.istitle()
            assert " " not in display_name  # No spaces in current status names

    def test_status_display_names_are_user_friendly(self):
        """Test that formatted display names are human-readable."""
        expected_display_names = {
            ImageStatus.REGISTERED: "Registered",
            ImageStatus.PENDING: "Pending",
            ImageStatus.ANALYZING: "Analyzing",
            ImageStatus.ANALYZED: "Analyzed",
            ImageStatus.BUNDLED: "Bundled",
            ImageStatus.DELETED: "Deleted",
        }

        for status, expected_name in expected_display_names.items():
            display_name = status.name.replace("_", " ").title()
            assert display_name == expected_name

    def test_status_iteration(self):
        """Test that all statuses can be iterated."""
        statuses = list(ImageStatus)
        assert len(statuses) == 6
        assert ImageStatus.REGISTERED in statuses
        assert ImageStatus.PENDING in statuses
        assert ImageStatus.ANALYZING in statuses
        assert ImageStatus.ANALYZED in statuses
        assert ImageStatus.BUNDLED in statuses
        assert ImageStatus.DELETED in statuses

    def test_status_comparison(self):
        """Test that status values can be compared."""
        assert ImageStatus.REGISTERED == ImageStatus.REGISTERED
        assert ImageStatus.REGISTERED != ImageStatus.PENDING
        assert ImageStatus.REGISTERED is ImageStatus.REGISTERED

    def test_status_string_representation(self):
        """Test that status has proper string representation."""
        status = ImageStatus.REGISTERED
        assert "REGISTERED" in str(status)
        assert "registered" in repr(status)
