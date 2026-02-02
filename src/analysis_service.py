"""
Analysis Service
Orchestrates automatic page analysis on startup with caching support.
"""

import os
import glob
import time
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

try:
    from src.analysis_db import AnalysisDB
    from src.metadata_db import MetadataDB
    from src.llm_providers.provider_factory import ProviderFactory
    from src.config_manager import ConfigManager
except ImportError:
    from analysis_db import AnalysisDB
    from metadata_db import MetadataDB
    from llm_providers.provider_factory import ProviderFactory
    from config_manager import ConfigManager


class AnalysisService:
    """Manages automatic startup analysis of document pages"""

    # Comprehensive analysis prompt
    DEFAULT_ANALYSIS_PROMPT = """Analyze this document page comprehensively.

Respond with ONLY valid JSON in this exact format:
{
  "document_type": "Invoice|Statement|Report|Letter|Contract|Receipt|Bill|Agreement|Form|Other",
  "company": "organization name or null",
  "document_date": "YYYY-MM-DD or null",
  "page_number": <integer or null>,
  "total_pages": <integer or null>,
  "belongs_to_same_doc": true or false,
  "confidence_score": <0.0 to 1.0>,
  "rotation_needed": true or false,
  "suggested_rotation": <0|90|180|270>,
  "rotation_confidence": "high|medium|low",
  "extracted_text_summary": "brief summary of key text",
  "additional": {}
}

Extraction Rules:
1. document_type: Classify the document (use one of the types listed above)
2. company: Extract company/organization name from headers, footers, logos
3. document_date: Primary document date (not print date) in YYYY-MM-DD format
4. page_number: Current page number if visible (from text like "Page 3")
5. total_pages: Total pages if indicated (from text like "Page 3 of 6")
6. belongs_to_same_doc: Always false for single-page analysis
7. confidence_score: 0.0 to 1.0 indicating extraction confidence
8. rotation_needed: Whether page appears to need rotation
9. suggested_rotation: Degrees to rotate (0, 90, 180, or 270)
10. rotation_confidence: Confidence in rotation suggestion
11. extracted_text_summary: Brief summary of key visible text (max 200 chars)
12. additional: Any other useful metadata (invoice #, account #, etc.)

Return ONLY the JSON object."""

    def __init__(
        self,
        config_manager: ConfigManager,
        analysis_db: AnalysisDB,
        metadata_db: MetadataDB
    ):
        """
        Initialize analysis service.

        Args:
            config_manager: Configuration manager instance
            analysis_db: Analysis database instance
            metadata_db: Metadata database instance
        """
        self.config = config_manager
        self.analysis_db = analysis_db
        self.metadata_db = metadata_db
        self.provider = None

    def _get_provider(self):
        """Get or create provider instance"""
        if self.provider is None:
            self.provider = ProviderFactory.create_from_config_manager(self.config)
        return self.provider

    def scan_all_directories(
        self,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        incremental: bool = True
    ) -> Dict[str, Any]:
        """
        Scan all configured source directories and analyze pages.

        Args:
            progress_callback: Optional callback(status_text, current, total)
            incremental: If True, skip already-analyzed files (cache-aware)

        Returns:
            Dictionary with analysis statistics
        """
        # Check if auto-analysis is enabled
        if not self.config.get_bool('AutoAnalysis', 'enabled', True):
            return {
                'total_files': 0,
                'analyzed': 0,
                'cached': 0,
                'errors': 0,
                'skipped': 0,
                'message': 'Auto-analysis disabled in settings'
            }

        directories = self.analysis_db.get_active_directories()
        if not directories:
            # Fall back to scan folder from DocumentProcessing
            scan_folder = self.config.get_setting('DocumentProcessing', 'scan_folder')
            if scan_folder and os.path.exists(scan_folder):
                directories = [scan_folder]
            else:
                return {
                    'total_files': 0,
                    'analyzed': 0,
                    'cached': 0,
                    'errors': 0,
                    'skipped': 0,
                    'message': 'No source directories configured'
                }

        # Get batch size from config
        batch_size = self.config.get_int('AutoAnalysis', 'batch_size', 10)

        stats = {
            'total_files': 0,
            'analyzed': 0,
            'cached': 0,
            'errors': 0,
            'skipped': 0,
            'processing_time_ms': 0
        }

        start_time = time.time()

        # Scan each directory
        for directory in directories:
            if not os.path.exists(directory):
                continue

            # Find all image files (PNG, JPG, JPEG)
            image_files = []
            for ext in ['*.png', '*.PNG', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG']:
                image_files.extend(glob.glob(os.path.join(directory, ext)))

            stats['total_files'] += len(image_files)

            # Process in batches
            for i in range(0, len(image_files), batch_size):
                batch = image_files[i:i + batch_size]

                for j, image_path in enumerate(batch):
                    current = i + j + 1

                    if progress_callback:
                        progress_callback(
                            f"Analyzing {os.path.basename(image_path)}...",
                            current,
                            stats['total_files']
                        )

                    # Analyze single page
                    result = self._analyze_single_page(image_path, incremental)

                    if result['cached']:
                        stats['cached'] += 1
                    elif result['success']:
                        stats['analyzed'] += 1
                    elif result['skipped']:
                        stats['skipped'] += 1
                    else:
                        stats['errors'] += 1

            # Update directory scan info
            self.analysis_db.update_directory_scan_info(directory, len(image_files))

        stats['processing_time_ms'] = int((time.time() - start_time) * 1000)

        return stats

    def _analyze_single_page(
        self,
        image_path: str,
        incremental: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze a single page with cache-aware processing.

        Args:
            image_path: Path to image file
            incremental: If True, use cached results if available

        Returns:
            Dictionary with result info
        """
        # Compute file hash
        file_hash = self.metadata_db.compute_file_hash(image_path)

        # Check if already analyzed (cache hit)
        if incremental:
            existing_analysis = self.analysis_db.get_analysis(image_path)
            if existing_analysis and existing_analysis['file_hash'] == file_hash:
                return {
                    'success': True,
                    'cached': True,
                    'skipped': False,
                    'analysis': existing_analysis
                }

        # File needs analysis
        try:
            provider = self._get_provider()

            # Perform analysis
            result = provider.analyze_images(
                image_paths=[image_path],
                prompt=self.DEFAULT_ANALYSIS_PROMPT
            )

            if not result['success']:
                return {
                    'success': False,
                    'cached': False,
                    'skipped': False,
                    'error': result['error']
                }

            # Save analysis to database
            self.analysis_db.save_analysis(
                file_path=image_path,
                file_hash=file_hash,
                provider_name=provider.provider_name,
                model_name=result['model_used'],
                analysis_data=result['metadata'],
                raw_response=result['response'],
                processing_time_ms=result['processing_time_ms']
            )

            # Also save to metadata_db for backward compatibility
            self.metadata_db.save_metadata(
                file_path=image_path,
                metadata=result['metadata'],
                model_used=result['model_used'],
                processing_time_ms=result['processing_time_ms']
            )

            return {
                'success': True,
                'cached': False,
                'skipped': False,
                'analysis': result['metadata']
            }

        except Exception as e:
            print(f"Error analyzing {image_path}: {e}")
            return {
                'success': False,
                'cached': False,
                'skipped': False,
                'error': str(e)
            }

    def analyze_specific_files(
        self,
        file_paths: List[str],
        force_reanalysis: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Analyze specific files (for manual triggering).

        Args:
            file_paths: List of file paths to analyze
            force_reanalysis: If True, re-analyze even if cached
            progress_callback: Optional progress callback

        Returns:
            Dictionary with analysis statistics
        """
        stats = {
            'total_files': len(file_paths),
            'analyzed': 0,
            'cached': 0,
            'errors': 0
        }

        for i, file_path in enumerate(file_paths):
            if progress_callback:
                progress_callback(
                    f"Analyzing {os.path.basename(file_path)}...",
                    i + 1,
                    stats['total_files']
                )

            result = self._analyze_single_page(
                file_path,
                incremental=not force_reanalysis
            )

            if result['cached']:
                stats['cached'] += 1
            elif result['success']:
                stats['analyzed'] += 1
            else:
                stats['errors'] += 1

        return stats

    def get_analysis_for_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        Get analysis results for specific files.

        Args:
            file_paths: List of file paths

        Returns:
            List of analysis dictionaries
        """
        results = []
        for file_path in file_paths:
            analysis = self.analysis_db.get_analysis(file_path)
            if analysis:
                results.append(analysis)
        return results


# Example usage
if __name__ == "__main__":
    try:
        from src.config_manager import ConfigManager
        from src.analysis_db import AnalysisDB
        from src.metadata_db import MetadataDB
    except ImportError:
        from config_manager import ConfigManager
        from analysis_db import AnalysisDB
        from metadata_db import MetadataDB

    # Create instances
    config = ConfigManager()
    analysis_db = AnalysisDB()
    metadata_db = MetadataDB()

    # Create service
    service = AnalysisService(config, analysis_db, metadata_db)

    # Test scan (won't actually analyze without valid images)
    def progress(status, current, total):
        print(f"[{current}/{total}] {status}")

    print("Testing analysis service...")
    stats = service.scan_all_directories(progress_callback=progress)
    print(f"Analysis complete: {stats}")

    # Cleanup
    analysis_db.close()
    metadata_db.close()
