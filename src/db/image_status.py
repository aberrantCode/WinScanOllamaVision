"""Image status enumeration for tracking image lifecycle."""

from enum import Enum


class ImageStatus(Enum):
    """
    Enumeration for image file status tracking.

    Represents the various states an image can be in throughout
    the document processing workflow.
    """

    REGISTERED = "registered"  # Initial state when file is discovered
    PENDING = "pending"  # Queued for analysis
    ANALYZING = "analyzing"  # Currently being analyzed
    ANALYZED = "analyzed"  # Analysis complete
    BUNDLED = "bundled"  # Grouped into a document bundle
    DELETED = "deleted"  # File has been deleted from disk
