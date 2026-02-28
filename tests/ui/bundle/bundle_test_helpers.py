"""Test helper utilities for bundle UI tests.

Provides factory functions for creating mock bundle data used in unit tests.
These factories were extracted from production code to keep fake data out of
the application binary.
"""


def create_mock_bundles() -> list:
    """Create mock bundle data with complete metadata.

    Returns a list of 7 bundles with varied page counts and metadata,
    suitable for testing bundle review workflows without a real database.
    """
    bundles = []
    companies = [
        "Acme Corporation",
        "TechCorp Industries",
        "Global Shipping LLC",
        "ABC Manufacturing",
    ]
    doc_types = ["Invoice", "Receipt", "Statement", "Contract"]

    for i in range(1, 8):
        # Make first bundle have 12 pages for demo
        num_pages = 12 if i == 1 else (i % 5) + 2

        company = companies[i % 4]
        doc_type = doc_types[i % 4]

        # Create analyses for each page
        analyses = []
        for p in range(num_pages):
            analyses.append(
                {
                    "document_type": doc_type,
                    "company": company,
                    "page_number": str(p + 1),
                    "total_pages": str(num_pages),
                    "rotation_needed": "none",
                    "confidence_score": 0.85 + (p * 0.01),
                    "tax_related": i % 3 == 0,
                    "analysis_id": f"analysis_{i:03d}_{p:03d}",
                    "provider": "Ollama",
                    "model": "qwen2.5-vl",
                    "processing_time": f"{1200 + (p * 100)}ms",
                    "analysis_date": f"2024-03-{15 + i:02d} 10:{30 + p:02d}:00",
                }
            )

        bundles.append(
            {
                "bundle_id": f"bundle_{i:03d}",
                "company": company,
                "document_type": doc_type,
                "document_date": f"2024-0{(i % 9) + 1}-15",
                "confidence_score": 0.95 - (i * 0.05),
                "file_paths": [f"mock_bundle_{i}_page_{p}.png" for p in range(1, num_pages + 1)],
                "analyses": analyses,
            }
        )
    return bundles
