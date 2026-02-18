"""Image status enumeration for tracking image lifecycle."""

from enum import Enum


class ImageStatus(Enum):
    """
    Enumeration for image file status tracking.

    Represents the various states an image can be in throughout
    the document processing workflow.

    Note: The `is_ignored` flag (added in Migration 17) is stored separately
    as a boolean field on the image_files table. Ignored images can still have
    any of the statuses below, but will be skipped during analysis scans.
    This separation allows for clean filtering without complicating status transitions.
    """

    REGISTERED = "registered"  # Initial state when file is discovered
    PENDING = "pending"  # Queued for analysis
    ANALYZING = "analyzing"  # Currently being analyzed
    ANALYZED = "analyzed"  # Analysis complete
    ERROR = "error"  # Analysis failed with error
    BUNDLED = "bundled"  # Grouped into a document bundle
    DELETED = "deleted"  # File has been deleted from disk
