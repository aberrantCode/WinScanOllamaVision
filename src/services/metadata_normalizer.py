"""Metadata normalization service for transforming raw LLM output into consistent format."""

from datetime import datetime
from typing import Any


class MetadataNormalizer:
    """Normalizes metadata from raw LLM output to application format."""

    # Commonly used acronyms that should be fully uppercase
    # Note: "inc", "corp", "ltd" are legal suffixes (title case), but "llc" is an acronym
    ACRONYMS = {"ibm", "nasa", "irs", "usa", "uk", "eu", "fbi", "cia", "un", "llc"}

    # Rotation mapping from string to degrees
    ROTATION_MAP = {
        "none": 0,
        "no": 0,
        "0": 0,
        "90_cw": 90,
        "90": 90,
        "90_ccw": 270,
        "270": 270,
        "180": 180,
    }

    def normalize(self, raw_metadata: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize all metadata fields.

        Transformations:
        - company: "acme corp" → "Acme Corp"
        - document_type: "invoice" → "Invoice"
        - document_date: "01/15/2024" → "2024-01-15T00:00:00Z"
        - rotation_needed: "90_cw" → 90

        Args:
            raw_metadata: Raw metadata from LLM response

        Returns:
            Normalized metadata dictionary
        """
        return {
            "company": self.normalize_company(raw_metadata.get("company")),
            "document_type": self.normalize_document_type(raw_metadata.get("document_type")),
            "document_date": self.normalize_date(raw_metadata.get("document_date")),
            "rotation": self.normalize_rotation(raw_metadata.get("rotation_needed")),
            "page_number": self.normalize_page_number(raw_metadata.get("page_number")),
            "total_pages": self.normalize_page_number(raw_metadata.get("total_pages")),
            "belongs_to_same_doc": self.normalize_boolean(raw_metadata.get("belongs_to_same_doc")),
            "confidence_score": self.normalize_confidence(raw_metadata.get("confidence_score")),
            "tax_related": self.normalize_boolean(raw_metadata.get("tax_related")),
        }

    def normalize_company(self, company: Any) -> str | None:
        """
        Title case with acronym preservation.

        Examples:
        - "acme corp" → "Acme Corp"
        - "ibm" → "IBM"
        - "nasa research inc" → "NASA Research Inc"

        Args:
            company: Raw company name

        Returns:
            Normalized company name or None
        """
        if not company:
            return None

        company_str = str(company).strip()
        if not company_str:
            return None

        words = company_str.split()
        normalized_words = []

        for word in words:
            word_lower = word.lower()
            # Check if it's a known acronym
            if word_lower in self.ACRONYMS:
                normalized_words.append(word_lower.upper())
            else:
                # Title case with special handling for hyphenated words
                if "-" in word:
                    parts = word.split("-")
                    normalized_words.append("-".join(part.capitalize() for part in parts))
                else:
                    normalized_words.append(word.capitalize())

        return " ".join(normalized_words)

    def normalize_document_type(self, doc_type: Any) -> str | None:
        """
        Title case standardization.

        Examples:
        - "invoice" → "Invoice"
        - "tax document" → "Tax Document"

        Args:
            doc_type: Raw document type

        Returns:
            Normalized document type or None
        """
        if not doc_type:
            return None

        doc_type_str = str(doc_type).strip()
        if not doc_type_str:
            return None

        return doc_type_str.title()

    def normalize_date(self, date_value: Any) -> str | None:
        """
        Parse various formats and return UTC ISO 8601.

        Supported formats:
        - MM/DD/YYYY
        - DD/MM/YYYY
        - YYYY-MM-DD
        - ISO 8601 variants

        Returns:
        - "YYYY-MM-DDTHH:MM:SSZ" (UTC)

        Args:
            date_value: Raw date value

        Returns:
            ISO 8601 formatted date or None
        """
        if not date_value:
            return None

        date_str = str(date_value).strip()
        if not date_str:
            return None

        # Try common date formats
        formats_to_try = [
            "%Y-%m-%d",  # 2024-01-15
            "%Y-%m-%dT%H:%M:%S",  # 2024-01-15T00:00:00
            "%Y-%m-%dT%H:%M:%SZ",  # 2024-01-15T00:00:00Z
            "%Y-%m-%dT%H:%M:%S.%f",  # 2024-01-15T00:00:00.000
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 2024-01-15T00:00:00.000Z
            "%m/%d/%Y",  # 01/15/2024 (US format)
            "%d/%m/%Y",  # 15/01/2024 (European format)
            "%Y/%m/%d",  # 2024/01/15
            "%B %d, %Y",  # January 15, 2024
            "%d %B %Y",  # 15 January 2024
        ]

        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(date_str, fmt)
                # Return in UTC ISO 8601 format
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue

        # If all formats fail, return None
        return None

    def normalize_rotation(self, rotation: Any) -> int:
        """
        Convert rotation to integer degrees.

        Examples:
        - "90_cw" → 90
        - "90_ccw" → 270
        - "180" → 180
        - "none" → 0

        Args:
            rotation: Raw rotation value

        Returns:
            Rotation in degrees (0, 90, 180, or 270)
        """
        if rotation is None:
            return 0

        # If already an integer, validate and return
        if isinstance(rotation, int):
            return rotation if rotation in {0, 90, 180, 270} else 0

        # Convert to string and normalize
        rotation_str = str(rotation).lower().strip()

        # Try exact match
        if rotation_str in self.ROTATION_MAP:
            return self.ROTATION_MAP[rotation_str]

        # Try to parse as integer
        try:
            rotation_int = int(rotation_str)
            return rotation_int if rotation_int in {0, 90, 180, 270} else 0
        except ValueError:
            return 0

    def normalize_boolean(self, value: Any) -> bool:
        """
        Convert fuzzy boolean values.

        Examples:
        - "true", "yes", "y", "1" → True
        - "false", "no", "n", "0" → False

        Args:
            value: Raw boolean value

        Returns:
            Boolean value
        """
        if isinstance(value, bool):
            return value

        if value is None:
            return False

        value_str = str(value).lower().strip()
        return value_str in {"true", "yes", "y", "1", "t"}

    def normalize_page_number(self, page: Any) -> int | None:
        """
        Validate positive integer for page numbers.

        Args:
            page: Raw page number

        Returns:
            Validated page number or None
        """
        if page is None:
            return None

        try:
            page_int = int(page)
            return page_int if page_int > 0 else None
        except (ValueError, TypeError):
            return None

    def normalize_confidence(self, confidence: Any) -> float | None:
        """
        Normalize confidence score to float between 0.0 and 1.0.

        Args:
            confidence: Raw confidence value

        Returns:
            Confidence score (0.0-1.0) or None
        """
        if confidence is None:
            return None

        try:
            confidence_float = float(confidence)
            # Clamp between 0.0 and 1.0
            return max(0.0, min(1.0, confidence_float))
        except (ValueError, TypeError):
            return None
