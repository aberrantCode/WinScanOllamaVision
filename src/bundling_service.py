"""
Bundling Service
Generates intelligent document bundling recommendations based on analysis results.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
import os

try:
    from src.analysis_db import AnalysisDB
except ImportError:
    from analysis_db import AnalysisDB


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
        file_paths: Optional[List[str]] = None,
        directory: Optional[str] = None,
        min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
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
            analyses = self.analysis_db.get_analyzed_pages(directory=directory)

        if not analyses:
            return []

        # Group by explicit page numbers first
        bundles_by_page_numbers = self._group_by_page_numbers(analyses)

        # Group remaining files by metadata
        remaining_analyses = [
            a for a in analyses
            if a['file_path'] not in [f for bundle in bundles_by_page_numbers for f in bundle['file_paths']]
        ]

        bundles_by_metadata = self._group_by_metadata(remaining_analyses)

        # Combine all bundles
        all_bundles = bundles_by_page_numbers + bundles_by_metadata

        # Calculate confidence scores
        scored_bundles = []
        for bundle in all_bundles:
            confidence = self._calculate_bundle_confidence(bundle)
            if confidence >= min_confidence:
                bundle['confidence_score'] = confidence
                scored_bundles.append(bundle)

        # Sort by confidence (highest first)
        scored_bundles.sort(key=lambda x: x['confidence_score'], reverse=True)

        # Save bundles to database
        for bundle in scored_bundles:
            bundle_id = self.analysis_db.save_bundle_suggestion(
                file_paths=bundle['file_paths'],
                bundle_metadata=bundle,
                confidence_score=bundle['confidence_score']
            )
            # Attach the database ID to the bundle dict for caller convenience
            bundle['id'] = bundle_id

        return scored_bundles

    def _group_by_page_numbers(self, analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            if not analysis.get('page_number'):
                continue

            key = (
                analysis.get('company', '').lower() if analysis.get('company') else '',
                analysis.get('document_type', '').lower() if analysis.get('document_type') else '',
                analysis.get('document_date', '') if analysis.get('document_date') else ''
            )

            groups[key].append(analysis)

        # Create bundles from groups with 2+ pages
        for key, group in groups.items():
            if len(group) >= 2:
                # Sort by page number
                group.sort(key=lambda x: x.get('page_number', 0))

                company, doc_type, doc_date = key

                bundles.append({
                    'file_paths': [a['file_path'] for a in group],
                    'company': company or None,
                    'document_type': doc_type or None,
                    'document_date': doc_date or None,
                    'total_pages': len(group),
                    'grouping_method': 'explicit_page_numbers',
                    'analyses': group
                })

        return bundles

    def _group_by_metadata(self, analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            # Create key from metadata
            key = (
                analysis.get('company', '').lower() if analysis.get('company') else '',
                analysis.get('document_type', '').lower() if analysis.get('document_type') else '',
                analysis.get('document_date', '') if analysis.get('document_date') else ''
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
                group.sort(key=lambda x: os.path.basename(x['file_path']))

                bundles.append({
                    'file_paths': [a['file_path'] for a in group],
                    'company': company or None,
                    'document_type': doc_type or None,
                    'document_date': doc_date or None,
                    'total_pages': len(group),
                    'grouping_method': 'metadata_matching',
                    'analyses': group
                })

        return bundles

    def _calculate_bundle_confidence(self, bundle: Dict[str, Any]) -> float:
        """
        Calculate confidence score for a bundle.

        Args:
            bundle: Bundle dictionary with analyses

        Returns:
            Confidence score (0.0 to 1.0)
        """
        analyses = bundle.get('analyses', [])
        if not analyses:
            return 0.0

        confidence = 0.0
        max_confidence = 1.0

        # Factor 1: Grouping method (40% of score)
        if bundle['grouping_method'] == 'explicit_page_numbers':
            confidence += 0.4
        elif bundle['grouping_method'] == 'metadata_matching':
            confidence += 0.2

        # Factor 2: Metadata completeness (30% of score)
        metadata_count = sum([
            1 if bundle.get('company') else 0,
            1 if bundle.get('document_type') else 0,
            1 if bundle.get('document_date') else 0
        ])
        confidence += (metadata_count / 3) * 0.3

        # Factor 3: Page number continuity (20% of score)
        if bundle['grouping_method'] == 'explicit_page_numbers':
            page_numbers = sorted([a.get('page_number', 0) for a in analyses if a.get('page_number')])
            if len(page_numbers) >= 2:
                # Check if continuous (1,2,3,4) or has gaps
                expected = list(range(page_numbers[0], page_numbers[0] + len(page_numbers)))
                if page_numbers == expected:
                    confidence += 0.2  # Perfect continuity
                else:
                    # Partial continuity
                    gaps = sum(1 for i in range(len(page_numbers) - 1) if page_numbers[i+1] - page_numbers[i] > 1)
                    confidence += max(0, 0.2 - (gaps * 0.05))

        # Factor 4: Individual analysis confidence (10% of score)
        avg_analysis_confidence = sum(
            a.get('confidence_score', 0.5) for a in analyses
        ) / len(analyses)
        confidence += avg_analysis_confidence * 0.1

        # Normalize to 0.0-1.0 range
        return min(max(confidence, 0.0), max_confidence)

    def get_bundle_by_id(self, bundle_id: int) -> Optional[Dict[str, Any]]:
        """
        Get bundle suggestion by ID.

        Args:
            bundle_id: Bundle ID from database

        Returns:
            Bundle dictionary or None
        """
        bundles = self.analysis_db.get_bundle_suggestions()
        for bundle in bundles:
            if bundle['id'] == bundle_id:
                return bundle
        return None

    def update_bundle_status(
        self,
        bundle_id: int,
        status: str,
        user_action: Optional[str] = None
    ) -> None:
        """
        Update bundle status after user interaction.

        Args:
            bundle_id: Bundle ID
            status: New status (accepted, rejected, modified, completed)
            user_action: Description of user action
        """
        self.analysis_db.update_bundle_status(bundle_id, status, user_action)

    def accept_bundle(self, bundle_id: int) -> None:
        """Mark bundle as accepted"""
        self.update_bundle_status(bundle_id, 'accepted', 'User accepted suggestion')

    def reject_bundle(self, bundle_id: int) -> None:
        """Mark bundle as rejected"""
        self.update_bundle_status(bundle_id, 'rejected', 'User rejected suggestion')

    def modify_bundle(self, bundle_id: int, new_file_paths: List[str]) -> None:
        """Mark bundle as modified"""
        self.update_bundle_status(
            bundle_id,
            'modified',
            f'User modified bundle (now {len(new_file_paths)} files)'
        )

    def get_high_confidence_bundles(
        self,
        min_confidence: float = 0.8
    ) -> List[Dict[str, Any]]:
        """
        Get high-confidence bundle suggestions.

        Args:
            min_confidence: Minimum confidence threshold

        Returns:
            List of high-confidence bundles
        """
        return self.analysis_db.get_bundle_suggestions(min_confidence=min_confidence)


# Example usage
if __name__ == "__main__":
    from analysis_db import AnalysisDB

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
