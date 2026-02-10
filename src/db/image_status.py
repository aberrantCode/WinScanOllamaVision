"""
Image file status enumeration.

Defines valid status values for the image_files.status column.
"""

from enum import Enum


class ImageStatus(str, Enum):
    """
    Valid status values for image_files.status column.

    Status Flow:
        registered → pending → analyzing → analyzed → bundled
                                    ↓
                                 deleted (at any point)
    """

    # Initial discovery
    REGISTERED = "registered"

    # Queued for analysis (waiting in queue)
    PENDING = "pending"

    # Currently being analyzed by LLM
    ANALYZING = "analyzing"

    # Analysis complete
    ANALYZED = "analyzed"

    # Included in a document bundle
    BUNDLED = "bundled"

    # Marked for deletion
    DELETED = "deleted"

    @property
    def display_name(self) -> str:
        """Return user-friendly display name."""
        return self.value.title()

    @classmethod
    def from_string(cls, status: str) -> "ImageStatus":
        """
        Convert string to ImageStatus enum.

        Args:
            status: Status string from database

        Returns:
            ImageStatus enum value

        Raises:
            ValueError: If status is not valid
        """
        try:
            return cls(status)
        except ValueError as e:
            raise ValueError(
                f"Invalid status: {status}. Valid statuses: {', '.join([s.value for s in cls])}"
            ) from e

    @classmethod
    def all_values(cls) -> list[str]:
        """Return list of all valid status values."""
        return [status.value for status in cls]
