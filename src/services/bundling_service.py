"""
Bundling Service
Generates intelligent document bundling recommendations based on analysis results.
"""

import os
from collections import defaultdict
from typing import Any, cast

from db.analysis_db import AnalysisDB


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

    def create_or_extend_manual_bundle(self, file_paths: list[str]) -> dict[str, Any]:
        """Manually bundle the given pages, applying the 0/1/>=2 existing-bundle rule.

        This is the data layer behind the Analyze list view's "Bundle" action. It
        requires no analysis — it works purely from registered ``image_files`` rows,
        so it functions when no LLM provider is available.

        Rule (over the *non-rejected* bundles the selected pages already belong to):
          * 0 distinct existing bundles  -> create a new ``'suggested'`` bundle
          * exactly 1 existing bundle    -> add the not-yet-member pages to it
          * 2+ distinct existing bundles -> abort as ambiguous (future work will ask
            which bundle wins)

        Rejected bundles are ignored so a dead bundle never blocks or captures a merge.

        Args:
            file_paths: Absolute paths of the selected pages.

        Returns:
            Outcome dict with keys:
              ``status``            -- "created" | "extended" | "ambiguous" | "error"
              ``bundle_id``         -- resulting bundle id, or None on ambiguous/error
              ``existing_bundle_ids`` -- sorted distinct non-rejected bundle ids found
              ``added_image_ids``   -- image ids newly added (extend case; [] otherwise)
              ``message``           -- human-readable summary for the caller/UI
        """
        # 1. Resolve selected paths to image ids, preserving selection order.
        resolved: list[tuple[str, int]] = []
        for path in file_paths:
            image_id = self.analysis_db.get_image_id(path)
            if image_id is not None:
                resolved.append((path, image_id))

        if not resolved:
            return {
                "status": "error",
                "bundle_id": None,
                "existing_bundle_ids": [],
                "added_image_ids": [],
                "message": "None of the selected pages are registered in the database.",
            }

        resolved_paths = [p for p, _ in resolved]
        resolved_ids = [iid for _, iid in resolved]

        # 2. Gather distinct existing (non-rejected) bundle ids across the selection.
        existing_bundle_ids: set[int] = set()
        for _, image_id in resolved:
            for bundle in self.analysis_db.get_bundles_for_image(image_id):
                if str(bundle.get("status")) == "rejected":
                    continue
                existing_bundle_ids.add(bundle["id"])

        distinct_ids = sorted(existing_bundle_ids)

        # 3a. Ambiguous: pages span two or more live bundles.
        if len(distinct_ids) >= 2:
            return {
                "status": "ambiguous",
                "bundle_id": None,
                "existing_bundle_ids": distinct_ids,
                "added_image_ids": [],
                "message": (
                    f"The selected pages already belong to {len(distinct_ids)} different "
                    "bundles. Merging separate bundles is not supported yet."
                ),
            }

        # 3b. None bundled: create a fresh suggested bundle with all resolved pages.
        if not distinct_ids:
            bundle_id = self.analysis_db.save_bundle_suggestion(
                file_paths=resolved_paths,
                bundle_metadata={"bundle_name": "Manual bundle"},
                confidence_score=1.0,
            )
            if bundle_id is None:
                return {
                    "status": "error",
                    "bundle_id": None,
                    "existing_bundle_ids": [],
                    "added_image_ids": [],
                    "message": "Failed to create the bundle.",
                }
            return {
                "status": "created",
                "bundle_id": bundle_id,
                "existing_bundle_ids": [],
                "added_image_ids": resolved_ids,
                "message": f"Created a new bundle with {len(resolved_paths)} page(s).",
            }

        # 3c. Exactly one existing bundle: add only the not-yet-member pages to it.
        target_id = distinct_ids[0]
        member_ids = {img["id"] for img in self.analysis_db.get_bundle_images(target_id)}
        to_add = [iid for iid in resolved_ids if iid not in member_ids]
        if to_add:
            self.analysis_db.add_images_to_bundle(target_id, to_add)
        return {
            "status": "extended",
            "bundle_id": target_id,
            "existing_bundle_ids": [target_id],
            "added_image_ids": to_add,
            "message": f"Added {len(to_add)} page(s) to the existing bundle.",
        }

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

        Args:
            bundle_id: Bundle ID
            pdf_path: Full path to generated PDF file
        """
        import os

        from services.logging_service import get_logger

        logger = get_logger()
        if not os.path.exists(pdf_path):
            logger.warning("PDF path does not exist: %s", pdf_path)

        # Save PDF path
        self.analysis_db.update_bundle_pdf_path(bundle_id, pdf_path)

        # Update status to completed
        self.update_bundle_status(
            bundle_id, "completed", f"PDF generated: {os.path.basename(pdf_path)}"
        )

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
    from db.analysis_db import AnalysisDB

    # Create instance
    analysis_db = AnalysisDB()
    service = BundlingService(analysis_db)

    # Test bundling (won't have data without actual analysis)
    print("Testing bundling service...")
    bundles = service.generate_bundle_recommendations()
    print(f"Generated {len(bundles)} bundle suggestions")

    for i, bundle in enumerate(bundles, 1):
        print(f"\nBundle {i}:")
        print(f"  Files: {len(bundle['file_paths'])}")
        print(f"  Company: {bundle.get('company')}")
        print(f"  Type: {bundle.get('document_type')}")
        print(f"  Confidence: {bundle['confidence_score']:.2f}")

    # Cleanup
    analysis_db.close()
