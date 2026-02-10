"""Database repositories for focused data access."""

from db.repositories.analysis_repo import AnalysisRepository
from db.repositories.audit_repo import AuditRepository
from db.repositories.bundle_images_repo import BundleImagesRepository
from db.repositories.bundle_repo import BundleRepository
from db.repositories.directory_repo import DirectoryRepository
from db.repositories.image_files_repo import ImageFilesRepository
from db.repositories.pdf_files_repo import PdfFilesRepository
from db.repositories.pdf_image_pages_repo import PdfImagePagesRepository

# Note: MetadataRepository is not exported to avoid confusion
# Use metadata_repo.py explicitly when needed

__all__ = [
    "AnalysisRepository",
    "AuditRepository",
    "BundleImagesRepository",
    "BundleRepository",
    "DirectoryRepository",
    "ImageFilesRepository",
    "PdfFilesRepository",
    "PdfImagePagesRepository",
]
