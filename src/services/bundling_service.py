"""
Bundling Service
Generates intelligent document bundling recommendations based on analysis results.
"""

import contextlib
import json
import os
import re
from collections import defaultdict
from typing import Any, cast

from db.analysis_db import AnalysisDB
from db.metadata_db import MetadataDB


class BundlingService:
    """Generates document bundle suggestions with confidence scoring"""

    def __init__(self, analysis_db: AnalysisDB):
        """
        Initialize bundling service.

        Args:
            analysis_db: Analysis database instance
        """
        self.analysis_db = analysis_db

    def generate_bundle_recommendations(
        self,
        file_paths: list[str] | None = None,
        directory: str | None = None,
        min_confidence: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Generate bundle recommendations for files.

        Args:
            file_paths: Optional specific file paths to bundle
            directory: Optional directory to analyze (uses analyzed pages if None)
            min_confidence: Minimum confidence score for bundles

        Returns:
            List of bundle suggestion dictionaries
        """
        # Get analyzed pages
        if file_paths:
            analyses = []
            for path in file_paths:
                analysis = self.analysis_db.get_analysis(path)
                if analysis:
                    analyses.append(analysis)
        else:
            analyses = self.analysis_db.get_analyzed_pages(directory_filter=directory)

        if not analyses:
            return []

        # NEW: Exclude files already in accepted/completed bundles
        bundled_files = self.analysis_db.get_bundled_file_paths()
        analyses = [a for a in analyses if a["file_path"] not in bundled_files]

        if not analyses:
            return []  # All files already bundled

        # Group by explicit page numbers first
        bundles_by_page_numbers = self._group_by_page_numbers(analyses)

        # Group remaining files by metadata
        remaining_analyses = [
            a
            for a in analyses
            if a["file_path"]
            not in [f for bundle in bundles_by_page_numbers for f in bundle["file_paths"]]
        ]

        bundles_by_metadata = self._group_by_metadata(remaining_analyses)

        # Combine all bundles
        all_bundles = bundles_by_page_numbers + bundles_by_metadata

        # Calculate confidence scores
        scored_bundles = []
        for bundle in all_bundles:
            confidence = self._calculate_bundle_confidence(bundle)
            if confidence >= min_confidence:
                bundle["confidence_score"] = confidence
                scored_bundles.append(bundle)

        # Sort by completeness first, then confidence
        scored_bundles = self._sort_bundles_by_completeness(scored_bundles)

        # Save bundles to database
        for bundle in scored_bundles:
            bundle_id = self.analysis_db.save_bundle_suggestion(
                file_paths=bundle["file_paths"],
                bundle_metadata=bundle,
                confidence_score=bundle["confidence_score"],
            )
            # Attach the database ID to the bundle dict for caller convenience
            bundle["id"] = bundle_id

            # Set proposed output filename for source images
            proposed_filename = self.propose_output_filename(bundle)
            for file_path in bundle["file_paths"]:
                # If image file doesn't exist in database, skip silently
                # (this can happen for files not yet registered)
                with contextlib.suppress(Exception):
                    self.analysis_db.set_image_output_filename(file_path, proposed_filename)

        return scored_bundles

    def _group_by_page_numbers(self, analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Group files that have explicit page numbers and matching metadata.

        Args:
            analyses: List of analysis dictionaries

        Returns:
            List of bundle dictionaries
        """
        bundles = []

        # Group by (company, document_type, document_date)
        groups = defaultdict(list)

        for analysis in analyses:
            # Only consider files with explicit page numbers
            if not analysis.get("page_number"):
                continue

            # Exclude single-page documents (e.g., "1 of 1")
            # These should never be bundled with other pages
            total_pages = analysis.get("total_pages")
            if total_pages == 1:
                continue

            key = (
                analysis.get("company", "").lower() if analysis.get("company") else "",
                analysis.get("document_type", "").lower() if analysis.get("document_type") else "",
                analysis.get("document_date", "") if analysis.get("document_date") else "",
            )

            groups[key].append(analysis)

        # Create bundles from groups with 2+ pages
        for key, group in groups.items():
            if len(group) >= 2:
                # Sort by page number
                group.sort(key=lambda x: x.get("page_number", 0))

                company, doc_type, doc_date = key

                bundles.append(
                    {
                        "file_paths": [a["file_path"] for a in group],
                        "company": company or None,
                        "document_type": doc_type or None,
                        "document_date": doc_date or None,
                        "total_pages": len(group),
                        "grouping_method": "explicit_page_numbers",
                        "analyses": group,
                    }
                )

        return bundles

    def _group_by_metadata(self, analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Group files by matching metadata (company, type, date).

        Args:
            analyses: List of analysis dictionaries

        Returns:
            List of bundle dictionaries
        """
        bundles = []

        # Group by (company, document_type, document_date)
        groups = defaultdict(list)

        for analysis in analyses:
            # Exclude single-page documents (e.g., "1 of 1")
            # These should never be bundled with other pages
            total_pages = analysis.get("total_pages")
            if total_pages == 1:
                continue

            # Create key from metadata
            key = (
                analysis.get("company", "").lower() if analysis.get("company") else "",
                analysis.get("document_type", "").lower() if analysis.get("document_type") else "",
                analysis.get("document_date", "") if analysis.get("document_date") else "",
            )

            # Skip if all key components are empty
            if not any(key):
                continue

            groups[key].append(analysis)

        # Create bundles from groups
        for key, group in groups.items():
            if len(group) >= 2:
                company, doc_type, doc_date = key

                # Sort by filename (as a fallback for ordering)
                group.sort(key=lambda x: os.path.basename(x["file_path"]))

                bundles.append(
                    {
                        "file_paths": [a["file_path"] for a in group],
                        "company": company or None,
                        "document_type": doc_type or None,
                        "document_date": doc_date or None,
                        "total_pages": len(group),
                        "grouping_method": "metadata_matching",
                        "analyses": group,
                    }
                )

        return bundles

    def _calculate_bundle_confidence(self, bundle: dict[str, Any]) -> float:
        """
        Calculate confidence score for a bundle.

        Args:
            bundle: Bundle dictionary with analyses

        Returns:
            Confidence score (0.0 to 1.0)
        """
        analyses = bundle.get("analyses", [])
        if not analyses:
            return 0.0

        confidence = 0.0
        max_confidence = 1.0

        # Factor 1: Grouping method (40% of score)
        if bundle["grouping_method"] == "explicit_page_numbers":
            confidence += 0.4
        elif bundle["grouping_method"] == "metadata_matching":
            confidence += 0.2

        # Factor 2: Metadata completeness (30% of score)
        metadata_count = sum(
            [
                1 if bundle.get("company") else 0,
                1 if bundle.get("document_type") else 0,
                1 if bundle.get("document_date") else 0,
            ]
        )
        confidence += (metadata_count / 3) * 0.3

        # Factor 3: Page number continuity (20% of score)
        if bundle["grouping_method"] == "explicit_page_numbers":
            page_numbers = sorted(
                [a.get("page_number", 0) for a in analyses if a.get("page_number")]
            )
            if len(page_numbers) >= 2:
                # Check if continuous (1,2,3,4) or has gaps
                expected = list(range(page_numbers[0], page_numbers[0] + len(page_numbers)))
                if page_numbers == expected:
                    confidence += 0.2  # Perfect continuity
                else:
                    # Partial continuity
                    gaps = sum(
                        1
                        for i in range(len(page_numbers) - 1)
                        if page_numbers[i + 1] - page_numbers[i] > 1
                    )
                    confidence += max(0, 0.2 - (gaps * 0.05))

        # Factor 4: Individual analysis confidence (10% of score)
        avg_analysis_confidence = sum(a.get("confidence_score", 0.5) for a in analyses) / len(
            analyses
        )
        confidence += avg_analysis_confidence * 0.1

        # Normalize to 0.0-1.0 range
        return cast(float, min(max(confidence, 0.0), max_confidence))

    def get_bundle_by_id(self, bundle_id: int) -> dict[str, Any] | None:
        """
        Get bundle suggestion by ID.

        Args:
            bundle_id: Bundle ID from database

        Returns:
            Bundle dictionary or None
        """
        bundles = self.analysis_db.get_bundle_suggestions()
        for bundle in bundles:
            if bundle["id"] == bundle_id:
                return bundle
        return None

    def update_bundle_status(
        self, bundle_id: int, status: str, user_action: str | None = None
    ) -> None:
        """
        Update bundle status after user interaction.

        Args:
            bundle_id: Bundle ID
            status: New status (accepted, rejected, modified, completed)
            user_action: Description of user action
        """
        self.analysis_db.update_bundle_status(bundle_id, status, user_action)

    def mark_bundle_completed(self, bundle_id: int, pdf_path: str) -> None:
        """
        Mark bundle as completed after successful PDF generation.
        Also registers the PDF and updates source image statuses.

        Args:
            bundle_id: Bundle ID
            pdf_path: Full path to generated PDF file
        """
        from services.logging_service import get_logger

        logger = get_logger()

        # Get bundle details
        bundle = self.get_bundle_by_id(bundle_id)
        if not bundle:
            logger.warning(f"Bundle {bundle_id} not found")
            return

        # Extract source image IDs and update their status
        file_paths = bundle.get("file_paths", [])
        if isinstance(file_paths, str):
            # Handle case where file_paths might still be JSON string
            file_paths = json.loads(file_paths)

        source_image_ids = []
        for path in file_paths:
            img = self.analysis_db.get_image_file(path)
            if img:
                source_image_ids.append(img["id"])
                # Update image status to 'bundled'
                self.analysis_db.update_image_status(path, "bundled")
            else:
                logger.warning(f"Image file not found in database: {path}")

        # Compute PDF metadata
        file_hash = None
        file_size = None
        if os.path.exists(pdf_path):
            file_hash = MetadataDB.compute_file_hash(pdf_path)
            file_stats = os.stat(pdf_path)
            file_size = file_stats.st_size
        else:
            logger.warning(f"PDF path does not exist: {pdf_path}")

        pdf_filename = os.path.basename(pdf_path)

        # Register PDF in pdf_files table
        try:
            self.analysis_db.register_pdf_file(
                pdf_path=pdf_path,
                pdf_filename=pdf_filename,
                bundle_id=bundle_id,
                source_image_ids=source_image_ids,
                page_count=len(file_paths),
                file_hash=file_hash,
                file_size=file_size,
            )
            logger.info(
                f"Registered PDF: {pdf_filename} with {len(source_image_ids)} source images"
            )
        except Exception as e:
            logger.error(f"Failed to register PDF file: {str(e)}", exc_info=True)

        # Save PDF path to bundle
        self.analysis_db.update_bundle_pdf_path(bundle_id, pdf_path)

        # Update status to completed
        self.update_bundle_status(bundle_id, "completed", f"PDF generated: {pdf_filename}")

    def propose_output_filename(self, bundle: dict[str, Any]) -> str:
        """
        Generate proposed output filename for bundle based on metadata.

        Args:
            bundle: Bundle dictionary with metadata

        Returns:
            Proposed PDF filename (sanitized for filesystem)
        """
        company = bundle.get("company") or "Unknown"
        doc_type = bundle.get("document_type") or "Document"
        doc_date = bundle.get("document_date") or ""

        # Handle None values
        if company is None or company == "None":
            company = "Unknown"
        if doc_type is None or doc_type == "None":
            doc_type = "Document"

        # Sanitize for filesystem (remove special characters)
        safe_company = re.sub(r"[^\w\s-]", "", str(company)).strip().replace(" ", "_")
        safe_type = re.sub(r"[^\w\s-]", "", str(doc_type)).strip().replace(" ", "_")

        # Build filename
        if doc_date:
            safe_date = re.sub(r"[^\w-]", "", str(doc_date))
            return f"{safe_company}_{safe_type}_{safe_date}.pdf"
        else:
            return f"{safe_company}_{safe_type}.pdf"

    def accept_bundle(self, bundle_id: int) -> None:
        """Mark bundle as accepted"""
        self.update_bundle_status(bundle_id, "accepted", "User accepted suggestion")

    def reject_bundle(self, bundle_id: int) -> None:
        """Mark bundle as rejected"""
        self.update_bundle_status(bundle_id, "rejected", "User rejected suggestion")

    def modify_bundle(self, bundle_id: int, new_file_paths: list[str]) -> None:
        """Mark bundle as modified"""
        self.update_bundle_status(
            bundle_id, "modified", f"User modified bundle (now {len(new_file_paths)} files)"
        )

    def get_high_confidence_bundles(self, min_confidence: float = 0.8) -> list[dict[str, Any]]:
        """
        Get high-confidence bundle suggestions.

        Args:
            min_confidence: Minimum confidence threshold

        Returns:
            List of high-confidence bundles
        """
        return self.analysis_db.get_bundle_suggestions(min_confidence=min_confidence)

    def _is_bundle_complete(self, bundle: dict[str, Any]) -> bool:
        """
        Check if a bundle has all its pages.

        A bundle is complete if:
        - It's a single-page document (page 1 of 1)
        - OR it has all pages from 1 to total_pages

        Args:
            bundle: Bundle dictionary with analyses

        Returns:
            True if bundle is complete, False if incomplete
        """
        analyses = bundle.get("analyses", [])
        if not analyses:
            return False

        # Get page numbers from analyses
        page_numbers = []
        total_pages = None

        for analysis in analyses:
            page_num = analysis.get("page_number")
            total = analysis.get("total_pages")

            if page_num is not None:
                page_numbers.append(page_num)

            if total is not None:
                total_pages = total

        if not page_numbers or total_pages is None:
            return False

        # Single-page document ("1 of 1")
        if total_pages == 1 and 1 in page_numbers:
            return True

        # Multi-page document - check if we have all pages
        expected_pages = set(range(1, total_pages + 1))
        actual_pages = set(page_numbers)

        return expected_pages == actual_pages

    def _sort_bundles_by_completeness(self, bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Sort bundles: complete bundles first (by confidence),
        then incomplete bundles (by confidence).

        Args:
            bundles: List of bundle dicts with confidence_score

        Returns:
            Sorted list of bundles
        """
        complete_bundles = []
        incomplete_bundles = []

        for bundle in bundles:
            if self._is_bundle_complete(bundle):
                complete_bundles.append(bundle)
            else:
                incomplete_bundles.append(bundle)

        # Sort each group by confidence (descending)
        complete_bundles.sort(key=lambda b: b.get("confidence_score", 0.0), reverse=True)
        incomplete_bundles.sort(key=lambda b: b.get("confidence_score", 0.0), reverse=True)

        # Complete bundles first, incomplete last
        return complete_bundles + incomplete_bundles

    def convert_bundle_to_pdf(
        self,
        file_paths: list[str],
        output_path: str,
        metadata: dict[str, Any] | None = None,
        rotation_angle: int = 0,
    ) -> str:
        """
        Convert bundle of images to PDF.

        Args:
            file_paths: List of image file paths in order
            output_path: Output PDF file path
            metadata: Document metadata dict (optional)
            rotation_angle: Rotation to apply to all pages (0, 90, 180, 270)

        Returns:
            Path to created PDF file

        Raises:
            Exception: If PDF conversion fails
        """
        from PIL import Image

        images = []
        for file_path in file_paths:
            try:
                img = Image.open(file_path)

                # Apply rotation if needed
                if rotation_angle != 0:
                    img = img.rotate(-rotation_angle, expand=True)  # type: ignore[assignment]

                # Convert to RGB if needed (PDF requirement)
                if img.mode != "RGB":
                    img = img.convert("RGB")  # type: ignore[assignment]

                images.append(img)
            except Exception as e:
                raise Exception(f"Failed to load image {file_path}: {str(e)}") from e

        # Save as PDF
        if images:
            try:
                images[0].save(
                    output_path,
                    "PDF",
                    save_all=True,
                    append_images=images[1:],
                    resolution=100.0,
                    quality=95,
                )
            except Exception as e:
                raise Exception(f"Failed to save PDF: {str(e)}") from e
        else:
            raise Exception("No images to convert")

        return output_path

    def update_bundle_metadata(self, bundle_id: int, metadata: dict[str, Any]) -> None:
        """
        Update bundle metadata in database.

        Args:
            bundle_id: Bundle ID
            metadata: Updated metadata dictionary
        """
        # Get current bundle
        bundle = self.get_bundle_by_id(bundle_id)
        if not bundle:
            return

        # Update bundle_metadata field with new metadata
        updated_metadata = bundle.get("bundle_metadata", {})
        updated_metadata.update(metadata)

        # Save to database (this will require adding method to analysis_db)
        self.analysis_db.update_bundle_metadata(bundle_id, updated_metadata)


# Example usage
if __name__ == "__main__":
    import logging

    from db.analysis_db import AnalysisDB
    from services.logging_service import LoggingService, get_logger

    LoggingService().initialize(log_level=logging.DEBUG, console_output=True)
    _logger = get_logger()

    # Create instance
    analysis_db = AnalysisDB()
    service = BundlingService(analysis_db)

    # Test bundling (won't have data without actual analysis)
    _logger.info("Testing bundling service...")
    bundles = service.generate_bundle_recommendations()
    _logger.info(f"Generated {len(bundles)} bundle suggestions")

    for i, bundle in enumerate(bundles, 1):
        _logger.info(
            f"Bundle {i}: Files={len(bundle['file_paths'])}, "
            f"Company={bundle.get('company')}, Type={bundle.get('document_type')}, "
            f"Confidence={bundle['confidence_score']:.2f}"
        )

    # Cleanup
    analysis_db.close()
